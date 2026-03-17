"""
tools/products.py

Registers product and inventory tools.

Tools:
  - get_products(stop_id)
      Returns every item on the manifest for a stop grouped by section_tag,
      including all fields needed to drive the mobile app UI.

  - reconcile_inventory(stop_id, scanned_barcodes, counted_items)
      Compares driver-scanned barcodes and manually counted items against the
      expected manifest for a stop, classifying each row as complete or
      missing based on its item_type (scan / count / scan_and_count).
"""

from mcp_server.database.connection import get_db


def register(mcp):
    """Attach all product tools to the FastMCP instance."""

    @mcp.tool()
    def get_products(stop_id: int) -> dict:
        """
        Fetch all products/items on the manifest for a stop, grouped by section.

        Args:
            stop_id: The integer primary key of the stop.

        Returns:
            On success:
                {
                  "stop_id": int,
                  "count":   int,
                  "sections": {
                    "cig_tob": [
                      {
                        "id":           int,
                        "barcode":      str,
                        "name":         str,
                        "section_tag":  str,
                        "item_type":    str,   # scan|count|scan_and_count
                        "quantity":     int,
                        "required_tag": str,   # required_photo|required_no_photo|not_required
                        "icon_tag":     str    # cig|tob|ice_cream|fridge|totes|paper_box
                      }
                    ],
                    "totes": [...],
                    ...
                  }
                }
            On failure:
                { "error": str }
        """
        with get_db() as conn:
            stop = conn.execute(
                "SELECT id FROM stops WHERE id = ?", (stop_id,)
            ).fetchone()

            if stop is None:
                return {"error": f"No stop found with id {stop_id}"}

            rows = conn.execute(
                """
                SELECT id, barcode, name, section_tag, item_type,
                       quantity, required_tag, icon_tag
                FROM products
                WHERE stop_id = ?
                ORDER BY section_tag, barcode
                """,
                (stop_id,),
            ).fetchall()

        sections: dict = {}
        for row in rows:
            tag = row["section_tag"]
            if tag not in sections:
                sections[tag] = []
            sections[tag].append({
                "id":           row["id"],
                "barcode":      row["barcode"],
                "name":         row["name"],
                "section_tag":  row["section_tag"],
                "item_type":    row["item_type"],
                "quantity":     row["quantity"],
                "required_tag": row["required_tag"],
                "icon_tag":     row["icon_tag"],
            })

        return {
            "stop_id":  stop_id,
            "count":    len(rows),
            "sections": sections,
        }

    @mcp.tool()
    def reconcile_inventory(
        stop_id: int,
        scanned_barcodes: list[str],
        counted_items: list[dict] = None,
    ) -> dict:
        """
        Compare driver scan/count data against the expected manifest for a stop.

        Completion rules by item_type:
          scan          → barcode must appear in scanned_barcodes
          count         → barcode must appear in counted_items with count_entered > 0
          scan_and_count → barcode in scanned_barcodes AND in counted_items
                           with count_entered > 0

        Args:
            stop_id:          The integer primary key of the stop.
            scanned_barcodes: List of barcode strings scanned by the driver.
                              e.g. ["10001", "10002"]
            counted_items:    List of dicts with barcode and count_entered.
                              e.g. [{"barcode": "10010", "count_entered": 2}]
                              Empty list if nothing counted yet.

        Returns:
            On success:
                {
                  "stop_id": int,
                  "summary": {
                    "total_expected":          int,
                    "total_complete":          int,
                    "total_missing":           int,
                    "required_photo_missing":  int,
                    "required_no_photo_missing": int,
                    "not_required_missing":    int
                  },
                  "complete": [
                    { "barcode": str, "name": str, "required_tag": str }
                  ],
                  "missing": [
                    {
                      "barcode":        str,
                      "name":           str,
                      "required_tag":   str,
                      "item_type":      str,
                      "missing_reason": str  # not_scanned|not_counted|scanned_not_counted
                    }
                  ],
                  "unrecognised_barcodes": [str]
                }
            On failure:
                { "error": str }
        """
        with get_db() as conn:
            stop = conn.execute(
                "SELECT id FROM stops WHERE id = ?", (stop_id,)
            ).fetchone()

            if stop is None:
                return {"error": f"No stop found with id {stop_id}"}

            rows = conn.execute(
                "SELECT id, barcode, name, section_tag, item_type, required_tag "
                "FROM products WHERE stop_id = ?",
                (stop_id,),
            ).fetchall()

        # Build fast lookup sets/dicts
        scanned_set: set[str] = set(scanned_barcodes)

        # counted_map: barcode → count_entered (only entries with count_entered > 0)
        counted_map: dict[str, int] = {}
        for entry in (counted_items or []):
            bc = str(entry.get("barcode", ""))
            cnt = int(entry.get("count_entered", 0))
            if cnt > 0:
                counted_map[bc] = cnt

        # All barcodes that exist in the DB for this stop
        db_barcodes: set[str] = {row["barcode"] for row in rows}

        complete: list[dict] = []
        missing:  list[dict] = []

        for row in rows:
            bc       = row["barcode"]
            itype    = row["item_type"]
            req_tag  = row["required_tag"]

            if itype == "scan":
                is_complete    = bc in scanned_set
                missing_reason = "not_scanned"

            elif itype == "count":
                is_complete    = bc in counted_map
                missing_reason = "not_counted"

            else:  # scan_and_count
                in_scanned = bc in scanned_set
                in_counted = bc in counted_map
                is_complete = in_scanned and in_counted
                if not in_scanned:
                    missing_reason = "not_scanned"
                else:
                    missing_reason = "scanned_not_counted"

            if is_complete:
                complete.append({
                    "barcode":      bc,
                    "name":         row["name"],
                    "required_tag": req_tag,
                })
            else:
                missing.append({
                    "barcode":        bc,
                    "name":           row["name"],
                    "required_tag":   req_tag,
                    "item_type":      itype,
                    "missing_reason": missing_reason,
                })

        # Barcodes the driver scanned that don't belong to this stop
        unrecognised_barcodes = [
            bc for bc in scanned_barcodes if bc not in db_barcodes
        ]

        # Summary counts by required_tag for missing items
        rp_missing  = sum(1 for m in missing if m["required_tag"] == "required_photo")
        rnp_missing = sum(1 for m in missing if m["required_tag"] == "required_no_photo")
        nr_missing  = sum(1 for m in missing if m["required_tag"] == "not_required")

        return {
            "stop_id": stop_id,
            "summary": {
                "total_expected":            len(rows),
                "total_complete":            len(complete),
                "total_missing":             len(missing),
                "required_photo_missing":    rp_missing,
                "required_no_photo_missing": rnp_missing,
                "not_required_missing":      nr_missing,
            },
            "complete":              complete,
            "missing":               missing,
            "unrecognised_barcodes": unrecognised_barcodes,
        }
