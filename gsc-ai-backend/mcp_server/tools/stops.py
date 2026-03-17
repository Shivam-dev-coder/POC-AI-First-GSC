"""
tools/stops.py

Registers stop-related MCP tools.

Tools:
  - get_route_for_driver(driver_id)
      Returns the full route assigned to a driver — route metadata plus
      all stops in delivery sequence. Used immediately after driver login
      so the app can display the complete route without a second request.

  - get_stop_details(stop_id)
      Returns the full detail for a single stop. Used when the AI needs
      to focus on one location (e.g. to confirm GPS proximity before delivery).

  - get_route_summary(route_id, driver_id)
      Calculates aggregate route statistics plus an ordered coordinate list.
      Used when the driver opens the full-route map view.

  - get_next_stop(route_id)
      Finds the first pending stop in sequence order for a route.
      Used when the driver opens the single-stop map view.
"""

from mcp_server.database.connection import get_db


def register(mcp):
    """Attach all stop tools to the FastMCP instance."""

    @mcp.tool()
    def get_route_for_driver(driver_id: int) -> dict:
        """
        Fetch the route and ordered stop list assigned to a driver.

        Joins routes → route_stops → stops to return route metadata and
        all stops in their delivery sequence.

        Args:
            driver_id: The integer primary key of the driver.

        Returns:
            On success (route found):
                {
                  "route_id":     int,
                  "route_name":   str,
                  "route_status": str,   # 'pending' | 'in_progress' | 'completed'
                  "stops": [
                    {
                      "id":          int,
                      "stop_number": int,
                      "sequence":    int,   # position in this route (1 = first)
                      "name":        str,
                      "address":     str,
                      "lat":         float,
                      "lng":         float,
                      "status":      str    # 'pending' | 'in_progress' | 'completed'
                    },
                    ...
                  ]
                }
            On success (no route assigned):
                { "route_id": null, "route_name": null, "route_status": null, "stops": [] }
            On failure:
                { "error": str }
        """
        with get_db() as conn:
            # Verify driver exists
            driver = conn.execute(
                "SELECT id FROM drivers WHERE id = ?", (driver_id,)
            ).fetchone()

            if driver is None:
                return {"error": f"No driver found with id {driver_id}"}

            # Fetch route assigned to this driver
            route = conn.execute(
                "SELECT id, route_name, route_status FROM routes WHERE driver_id = ?",
                (driver_id,),
            ).fetchone()

            if route is None:
                return {
                    "route_id":     None,
                    "route_name":   None,
                    "route_status": None,
                    "stops":        [],
                }

            route_id     = route["id"]
            route_name   = route["route_name"]
            route_status = route["route_status"]

            # Fetch all stops for this route in sequence order
            rows = conn.execute(
                """
                SELECT
                    s.id          AS id,
                    s.stop_number AS stop_number,
                    s.name        AS name,
                    s.address     AS address,
                    s.lat         AS lat,
                    s.lng         AS lng,
                    s.status      AS status,
                    rs.sequence   AS sequence
                FROM route_stops rs
                JOIN stops s ON s.id = rs.stop_id
                WHERE rs.route_id = ?
                ORDER BY rs.sequence ASC
                """,
                (route_id,),
            ).fetchall()

        return {
            "route_id":     route_id,
            "route_name":   route_name,
            "route_status": route_status,
            "stops": [
                {
                    "id":          row["id"],
                    "stop_number": row["stop_number"],
                    "sequence":    row["sequence"],
                    "name":        row["name"],
                    "address":     row["address"],
                    "lat":         row["lat"],
                    "lng":         row["lng"],
                    "status":      row["status"],
                }
                for row in rows
            ],
        }

    @mcp.tool()
    def get_stop_details(stop_id: int) -> dict:
        """
        Fetch the full details for a single stop.

        Args:
            stop_id: The integer primary key of the stop.

        Returns:
            On success:
                {
                  "id":      int,
                  "name":    str,
                  "address": str,
                  "lat":     float,
                  "lng":     float,
                  "status":  str   # 'pending' | 'in_progress' | 'completed'
                }
            On failure:
                { "error": str }
        """
        with get_db() as conn:
            row = conn.execute(
                "SELECT id, name, address, lat, lng, status "
                "FROM stops WHERE id = ?",
                (stop_id,),
            ).fetchone()

        if row is None:
            return {"error": f"No stop found with id {stop_id}"}

        return {
            "id":      row["id"],
            "name":    row["name"],
            "address": row["address"],
            "lat":     row["lat"],
            "lng":     row["lng"],
            "status":  row["status"],
        }

    @mcp.tool()
    def get_route_summary(route_id: int, driver_id: int) -> dict:
        """
        Calculate aggregate statistics for a route and return an ordered list
        of stop coordinates. Used for the full-route map view.

        Args:
            route_id:  The integer primary key of the route.
            driver_id: Verified against the route so a driver cannot query
                       another driver's route.

        Returns:
            On success:
                {
                  "route_id":         int,
                  "route_name":       str,
                  "total_stops":      int,
                  "completed_stops":  int,
                  "remaining_stops":  int,
                  "stops_coordinates": [
                    { "sequence": int, "stop_id": int, "name": str,
                      "lat": float, "lng": float, "status": str }
                  ]
                }
            On failure:
                { "error": str }
        """
        with get_db() as conn:
            # Verify the route belongs to this driver
            route = conn.execute(
                "SELECT id, route_name FROM routes WHERE id = ? AND driver_id = ?",
                (route_id, driver_id),
            ).fetchone()

            if route is None:
                return {"error": f"No route found with id {route_id} for driver {driver_id}"}

            # Aggregate counts: total, completed, remaining
            counts = conn.execute(
                """
                SELECT
                    COUNT(rs.id)                                                  AS total_stops,
                    SUM(CASE WHEN s.status = 'completed' THEN 1 ELSE 0 END)      AS completed_stops,
                    SUM(CASE WHEN s.status != 'completed' THEN 1 ELSE 0 END)     AS remaining_stops
                FROM route_stops rs
                JOIN stops s ON s.id = rs.stop_id
                WHERE rs.route_id = ?
                """,
                (route_id,),
            ).fetchone()

            # Ordered coordinate list for distance / map rendering
            rows = conn.execute(
                """
                SELECT rs.sequence, s.id AS stop_id, s.name,
                       s.lat, s.lng, s.status
                FROM route_stops rs
                JOIN stops s ON s.id = rs.stop_id
                WHERE rs.route_id = ?
                ORDER BY rs.sequence ASC
                """,
                (route_id,),
            ).fetchall()

        return {
            "route_id":        route["id"],
            "route_name":      route["route_name"],
            "total_stops":     counts["total_stops"]     or 0,
            "completed_stops": counts["completed_stops"] or 0,
            "remaining_stops": counts["remaining_stops"] or 0,
            "stops_coordinates": [
                {
                    "sequence": row["sequence"],
                    "stop_id":  row["stop_id"],
                    "name":     row["name"],
                    "lat":      row["lat"],
                    "lng":      row["lng"],
                    "status":   row["status"],
                }
                for row in rows
            ],
        }

    @mcp.tool()
    def get_next_stop(route_id: int) -> dict:
        """
        Find the next pending stop in sequence order for a route.
        Used when the driver opens the single-stop map view so the AI knows
        which location to focus on.

        Args:
            route_id: The integer primary key of the route.

        Returns:
            Next pending stop found:
                {
                  "stop_id":     int,
                  "stop_number": int,
                  "sequence":    int,
                  "name":        str,
                  "address":     str,
                  "lat":         float,
                  "lng":         float,
                  "status":      str,
                  "is_last_stop": bool   # true if this is the final stop in the route
                }
            No pending stops remaining:
                { "stop_id": null, "name": null, "is_last_stop": false,
                  "message": "All stops completed" }
            Failure:
                { "error": str }
        """
        with get_db() as conn:
            # Total stop count for is_last_stop calculation
            total_row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM route_stops WHERE route_id = ?",
                (route_id,),
            ).fetchone()
            total_stops = total_row["cnt"] if total_row else 0

            # First pending stop in sequence
            row = conn.execute(
                """
                SELECT s.id AS stop_id, s.stop_number, s.name, s.address,
                       s.lat, s.lng, s.status, rs.sequence
                FROM route_stops rs
                JOIN stops s ON s.id = rs.stop_id
                WHERE rs.route_id = ? AND s.status != 'completed'
                ORDER BY rs.sequence ASC
                LIMIT 1
                """,
                (route_id,),
            ).fetchone()

        if row is None:
            return {
                "stop_id":     None,
                "name":        None,
                "is_last_stop": False,
                "message":     "All stops completed",
            }

        return {
            "stop_id":     row["stop_id"],
            "stop_number": row["stop_number"],
            "sequence":    row["sequence"],
            "name":        row["name"],
            "address":     row["address"],
            "lat":         row["lat"],
            "lng":         row["lng"],
            "status":      row["status"],
            "is_last_stop": row["sequence"] == total_stops,
        }
