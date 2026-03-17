"""
tools/driver.py

Registers the driver-related MCP tools.

Tools:
  - get_driver_profile(driver_id)
      Returns the driver's name, experience level, and new-driver flag.
      The AI uses this at the start of a session to tailor its guidance
      (e.g. extra prompts for new drivers, streamlined flow for seniors).
"""

from mcp_server.database.connection import get_db


def register(mcp):
    """Attach all driver tools to the FastMCP instance."""

    @mcp.tool()
    def get_driver_profile(driver_id: int) -> dict:
        """
        Fetch the profile for a single driver.

        Args:
            driver_id: The integer primary key of the driver.

        Returns:
            On success:
                {
                  "id":               int,
                  "name":             str,
                  "experience_level": str,   # 'junior' | 'mid' | 'senior'
                  "is_new_driver":    bool
                }
            On failure:
                { "error": str }
        """
        with get_db() as conn:
            row = conn.execute(
                "SELECT id, name, experience_level, is_new_driver "
                "FROM drivers WHERE id = ?",
                (driver_id,),
            ).fetchone()

        if row is None:
            return {"error": f"No driver found with id {driver_id}"}

        return {
            "id":               row["id"],
            "name":             row["name"],
            "experience_level": row["experience_level"],
            "is_new_driver":    bool(row["is_new_driver"]),  # convert 0/1 → bool
        }

    @mcp.tool()
    def get_driver_by_name(name: str) -> dict:
        """
        Fetch the profile for a driver by name (case-insensitive partial match).

        Returns the first matching driver or {"error": str} if not found.
        """
        with get_db() as conn:
            row = conn.execute(
                "SELECT id, name, experience_level, is_new_driver "
                "FROM drivers WHERE LOWER(name) LIKE LOWER(?)",
                (f"%{name}%",),
            ).fetchone()

        if row is None:
            return {"error": f"No driver found with name '{name}'"}

        return {
            "id":               row["id"],
            "name":             row["name"],
            "experience_level": row["experience_level"],
            "is_new_driver":    bool(row["is_new_driver"]),
        }
