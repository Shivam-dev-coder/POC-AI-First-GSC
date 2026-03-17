"""
database/connection.py

Handles SQLite connection setup and database initialisation.

Responsibilities:
  - Load DATABASE_URL from .env
  - Drop and recreate all tables on every startup (POC only — production
    would use proper migrations such as Alembic)
  - Seed the database with test data on every startup
  - Expose get_db() for use by all tool modules
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv

# Anchor .env resolution to this file's location so it works regardless
# of the working directory the orchestrator uses to spawn the server process.
#   connection.py  →  mcp_server/database/
#   .parent        →  mcp_server/
#   .parent        →  gsc-ai-backend/   (project root, where .env lives)
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=_ENV_PATH, verbose=False)

# If DATABASE_URL is a relative path, resolve it against the project root
# so the .db file always ends up in gsc-ai-backend/ regardless of CWD.
_raw_url = os.getenv("DATABASE_URL", "gsc_poc.db")
DATABASE_URL = str(
    _PROJECT_ROOT / _raw_url if not Path(_raw_url).is_absolute() else _raw_url
)


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

@contextmanager
def get_db():
    """
    Context manager that yields a SQLite connection.

    Row factory is set to sqlite3.Row so columns can be accessed
    by name (e.g. row["name"]) as well as by index.

    Usage:
        with get_db() as conn:
            rows = conn.execute("SELECT * FROM drivers").fetchall()
    """
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

# NOTE (POC only): Tables are dropped and recreated on every startup so the
# schema always matches this file. In production, use database migrations
# (e.g. Alembic) instead of dropping tables.

_CREATE_DRIVERS = """
CREATE TABLE IF NOT EXISTS drivers (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT    NOT NULL,
    experience_level TEXT    NOT NULL,  -- 'junior' | 'mid' | 'senior'
    is_new_driver    INTEGER NOT NULL DEFAULT 0  -- SQLite boolean: 0 = false, 1 = true
);
"""

_CREATE_STOPS = """
CREATE TABLE IF NOT EXISTS stops (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    stop_number INTEGER NOT NULL,
    name        TEXT    NOT NULL,
    address     TEXT    NOT NULL,
    lat         REAL    NOT NULL,
    lng         REAL    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'pending'
                CHECK(status IN ('pending', 'in_progress', 'completed'))
);
"""

_CREATE_PRODUCTS = """
CREATE TABLE IF NOT EXISTS products (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    stop_id      INTEGER NOT NULL REFERENCES stops(id),
    barcode      TEXT    NOT NULL UNIQUE,
    name         TEXT    NOT NULL,
    section_tag  TEXT    NOT NULL
                 CHECK(section_tag IN ('cig_tob','totes','boxes','returns','ice_cream','fridge')),
    item_type    TEXT    NOT NULL
                 CHECK(item_type IN ('count','scan','scan_and_count')),
    quantity     INTEGER NOT NULL DEFAULT 1,
    required_tag TEXT    NOT NULL DEFAULT 'not_required'
                 CHECK(required_tag IN ('required_photo','required_no_photo','not_required')),
    icon_tag     TEXT    NOT NULL DEFAULT 'paper_box'
                 CHECK(icon_tag IN ('cig','tob','ice_cream','fridge','totes','paper_box'))
);
"""

_CREATE_ROUTES = """
CREATE TABLE IF NOT EXISTS routes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    route_name   TEXT    NOT NULL,
    driver_id    INTEGER NOT NULL REFERENCES drivers(id),
    route_status TEXT    NOT NULL DEFAULT 'pending'
                 CHECK(route_status IN ('pending', 'in_progress', 'completed'))
);
"""

# route_stops replaces the old manifest table.
# The UNIQUE constraint enforces that a stop cannot appear twice in one route.
_CREATE_ROUTE_STOPS = """
CREATE TABLE IF NOT EXISTS route_stops (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id INTEGER NOT NULL REFERENCES routes(id),
    stop_id  INTEGER NOT NULL REFERENCES stops(id),
    sequence INTEGER NOT NULL,
    UNIQUE(route_id, stop_id)
);
"""


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

# (id, name, experience_level, is_new_driver)
_SEED_DRIVERS = [
    (1, "Marcus Webb",  "senior", 0),
    (2, "Priya Sharma", "mid",    0),
    (3, "Jordan Lee",   "junior", 1),  # <-- new driver flag
]

# (id, stop_number, name, address, lat, lng, status)
_SEED_STOPS = [
    (1,  1,  "Pink City Kirana Store",      "Johari Bazaar, Jaipur 302003",          26.9239, 75.8267, "pending"),
    (2,  2,  "Hawa Mahal Convenience",      "Hawa Mahal Road, Jaipur 302002",        26.9239, 75.8267, "pending"),
    (3,  3,  "MI Road General Store",       "MI Road, Jaipur 302001",                26.9196, 75.8235, "pending"),
    (4,  4,  "Sindhi Camp Supermart",       "Sindhi Camp, Jaipur 302001",            26.9194, 75.7957, "pending"),
    (5,  5,  "Vaishali Nagar Daily Needs",  "Vaishali Nagar, Jaipur 302021",         26.9145, 75.7390, "pending"),
    (6,  6,  "Mansarovar General Store",    "Mansarovar, Jaipur 302020",             26.8574, 75.7575, "pending"),
    (7,  7,  "Tonk Road Convenience",       "Tonk Road, Jaipur 302015",              26.8768, 75.8167, "pending"),
    (8,  8,  "Malviya Nagar Superstore",    "Malviya Nagar, Jaipur 302017",          26.8629, 75.8282, "pending"),
    (9,  9,  "Jagatpura Quick Stop",        "Jagatpura, Jaipur 302025",              26.8400, 75.8560, "pending"),
    (10, 10, "Sanganer News & Grocery",     "Sanganer, Jaipur 302029",               26.7924, 75.8274, "pending"),
    (11, 11, "Muhana Market Store",         "Muhana Mandi, Jaipur 302029",           26.7856, 75.8456, "pending"),
    (12, 12, "Pratap Nagar Kirana",         "Pratap Nagar, Jaipur 302033",           26.8235, 75.8890, "pending"),
    (13, 13, "Sitapura Industrial Canteen", "Sitapura, Jaipur 302022",               26.7987, 75.8762, "pending"),
    (14, 14, "Durgapura Convenience Store", "Durgapura, Jaipur 302018",              26.8547, 75.8074, "pending"),
    (15, 15, "Sodala General Store",        "Sodala, Jaipur 302006",                 26.9023, 75.7712, "pending"),
    (16, 16, "Shastri Nagar Daily Mart",    "Shastri Nagar, Jaipur 302016",          26.9312, 75.7824, "pending"),
    (17, 17, "Jhotwara Road Store",         "Jhotwara, Jaipur 302012",               26.9567, 75.7934, "pending"),
    (18, 18, "Nirman Nagar Quick Mart",     "Nirman Nagar, Jaipur 302019",           26.9089, 75.7456, "pending"),
    (19, 19, "Vidhyadhar Nagar Store",      "Vidhyadhar Nagar, Jaipur 302023",       26.9478, 75.8123, "pending"),
    (20, 20, "Civil Lines Convenience",     "Civil Lines, Jaipur 302006",            26.9378, 75.7989, "pending"),
]

# (stop_id, barcode, name, section_tag, item_type, quantity, required_tag, icon_tag)
# Every product row has a unique barcode starting at 10001, incrementing by 1.
# quantity is always 1 — multiple units of the same SKU each get their own row.
_SEED_PRODUCTS = [
    # ── Stop 1: Pink City Kirana Store ──────────────────────────────────────
    # cig_tob
    (1, "10001", "Marlboro Red 20s",           "cig_tob", "scan",          1, "required_no_photo", "cig"),
    (1, "10002", "Marlboro Red 20s",           "cig_tob", "scan",          1, "required_no_photo", "cig"),
    (1, "10003", "Marlboro Red 20s",           "cig_tob", "scan",          1, "required_no_photo", "cig"),
    (1, "10004", "Lambert & Butler King Size", "cig_tob", "scan",          1, "required_no_photo", "cig"),
    (1, "10005", "Lambert & Butler King Size", "cig_tob", "scan",          1, "required_no_photo", "cig"),
    (1, "10006", "Amber Leaf 50g Pouch",       "cig_tob", "scan",          1, "required_no_photo", "tob"),
    (1, "10007", "Amber Leaf 50g Pouch",       "cig_tob", "scan",          1, "required_no_photo", "tob"),
    (1, "10008", "Richmond Superkings",        "cig_tob", "scan",          1, "required_no_photo", "cig"),
    (1, "10009", "Richmond Superkings",        "cig_tob", "scan",          1, "required_no_photo", "cig"),
    # totes
    (1, "10010", "Soft Drinks Tote A",         "totes",   "count",         1, "required_no_photo", "totes"),
    (1, "10011", "Confectionery Tote B",        "totes",   "count",         1, "required_no_photo", "totes"),
    # boxes
    (1, "10012", "Crisps Assorted Box x12",    "boxes",   "scan_and_count", 1, "required_no_photo", "paper_box"),
    (1, "10013", "Water Bottle Box x6",         "boxes",   "scan_and_count", 1, "required_no_photo", "paper_box"),
    # returns
    (1, "10014", "Empty Crate Return",          "returns", "scan",          1, "not_required",      "paper_box"),
    (1, "10015", "Empty Crate Return",          "returns", "scan",          1, "not_required",      "paper_box"),
    (1, "10016", "Damaged Tray Return",         "returns", "scan",          1, "not_required",      "paper_box"),

    # ── Stop 2: Hawa Mahal Convenience ──────────────────────────────────────
    # cig_tob
    (2, "10017", "Marlboro Gold 20s",           "cig_tob", "scan",          1, "required_no_photo", "cig"),
    (2, "10018", "Marlboro Gold 20s",           "cig_tob", "scan",          1, "required_no_photo", "cig"),
    (2, "10019", "Marlboro Gold 20s",           "cig_tob", "scan",          1, "required_no_photo", "cig"),
    (2, "10020", "Camel Blue 20s",              "cig_tob", "scan",          1, "required_no_photo", "cig"),
    (2, "10021", "Camel Blue 20s",              "cig_tob", "scan",          1, "required_no_photo", "cig"),
    (2, "10022", "Pall Mall Red 20s",           "cig_tob", "scan",          1, "required_no_photo", "cig"),
    (2, "10023", "Pall Mall Red 20s",           "cig_tob", "scan",          1, "required_no_photo", "cig"),
    # totes
    (2, "10024", "Snack Tote C",                "totes",   "count",         1, "required_no_photo", "totes"),
    (2, "10025", "Juice Tote D",                "totes",   "count",         1, "required_no_photo", "totes"),
    # fridge
    (2, "10026", "Coca Cola 500ml",             "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),
    (2, "10027", "Coca Cola 500ml",             "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),
    (2, "10028", "Fanta Orange 500ml",          "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),
    (2, "10029", "Fanta Orange 500ml",          "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),
    # returns
    (2, "10030", "Empty Bottle Crate",          "returns", "scan",          1, "not_required",      "paper_box"),
    (2, "10031", "Empty Bottle Crate",          "returns", "scan",          1, "not_required",      "paper_box"),

    # ── Stop 3: MI Road General Store ───────────────────────────────────────
    # cig_tob
    (3, "10032", "Camel Blue 20s",              "cig_tob", "scan",          1, "required_no_photo", "cig"),
    (3, "10033", "Camel Blue 20s",              "cig_tob", "scan",          1, "required_no_photo", "cig"),
    (3, "10034", "Amber Leaf 30g Pouch",        "cig_tob", "scan",          1, "required_no_photo", "tob"),
    (3, "10035", "Amber Leaf 30g Pouch",        "cig_tob", "scan",          1, "required_no_photo", "tob"),
    # boxes
    (3, "10036", "Juice Box x12",              "boxes",   "scan_and_count", 1, "required_no_photo", "paper_box"),
    (3, "10037", "Snack Box x6",               "boxes",   "scan_and_count", 1, "required_no_photo", "paper_box"),
    # ice_cream
    (3, "10038", "Magnum Classic",             "ice_cream", "scan_and_count", 1, "required_photo",  "ice_cream"),
    (3, "10039", "Magnum Classic",             "ice_cream", "scan_and_count", 1, "required_photo",  "ice_cream"),
    (3, "10040", "Cornetto Vanilla",           "ice_cream", "scan_and_count", 1, "required_photo",  "ice_cream"),
    (3, "10041", "Cornetto Vanilla",           "ice_cream", "scan_and_count", 1, "required_photo",  "ice_cream"),
    # fridge
    (3, "10042", "Red Bull 250ml",             "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),
    (3, "10043", "Red Bull 250ml",             "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),
    (3, "10044", "Monster Energy",             "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),
    (3, "10045", "Monster Energy",             "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),

    # ── Stop 4: Sindhi Camp Supermart ────────────────────────────────────────
    (4, "10046", "Marlboro Red 20s",           "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (4, "10047", "Marlboro Red 20s",           "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (4, "10048", "Lambert & Butler King Size", "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (4, "10049", "Amber Leaf 50g Pouch",       "cig_tob", "scan",           1, "required_no_photo", "tob"),
    (4, "10050", "Soft Drinks Tote A",         "totes",   "count",          1, "required_no_photo", "totes"),
    (4, "10051", "Snack Tote B",               "totes",   "count",          1, "required_no_photo", "totes"),
    (4, "10052", "Crisps Assorted Box x12",    "boxes",   "scan_and_count", 1, "required_no_photo", "paper_box"),
    (4, "10053", "Empty Crate Return",         "returns", "scan",           1, "not_required",      "paper_box"),

    # ── Stop 5: Vaishali Nagar Daily Needs ───────────────────────────────────
    (5, "10054", "Camel Blue 20s",             "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (5, "10055", "Camel Blue 20s",             "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (5, "10056", "Pall Mall Red 20s",          "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (5, "10057", "Pall Mall Red 20s",          "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (5, "10058", "Juice Tote D",               "totes",   "count",          1, "required_no_photo", "totes"),
    (5, "10059", "Confectionery Tote E",       "totes",   "count",          1, "required_no_photo", "totes"),
    (5, "10060", "Coca Cola 500ml",            "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),
    (5, "10061", "Coca Cola 500ml",            "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),
    (5, "10062", "Empty Bottle Crate",         "returns", "scan",           1, "not_required",      "paper_box"),

    # ── Stop 6: Mansarovar General Store ─────────────────────────────────────
    (6, "10063", "Marlboro Gold 20s",          "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (6, "10064", "Marlboro Gold 20s",          "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (6, "10065", "Richmond Superkings",        "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (6, "10066", "Richmond Superkings",        "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (6, "10067", "Snack Tote F",               "totes",   "count",          1, "required_no_photo", "totes"),
    (6, "10068", "Magnum Classic",             "ice_cream", "scan_and_count", 1, "required_photo",  "ice_cream"),
    (6, "10069", "Magnum Classic",             "ice_cream", "scan_and_count", 1, "required_photo",  "ice_cream"),
    (6, "10070", "Empty Crate Return",         "returns", "scan",           1, "not_required",      "paper_box"),

    # ── Stop 7: Tonk Road Convenience ────────────────────────────────────────
    (7, "10071", "Camel Blue 20s",             "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (7, "10072", "Camel Blue 20s",             "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (7, "10073", "Amber Leaf 50g Pouch",       "cig_tob", "scan",           1, "required_no_photo", "tob"),
    (7, "10074", "Soft Drinks Tote G",         "totes",   "count",          1, "required_no_photo", "totes"),
    (7, "10075", "Juice Tote H",               "totes",   "count",          1, "required_no_photo", "totes"),
    (7, "10076", "Red Bull 250ml",             "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),
    (7, "10077", "Red Bull 250ml",             "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),
    (7, "10078", "Crisps Assorted Box x12",    "boxes",   "scan_and_count", 1, "required_no_photo", "paper_box"),

    # ── Stop 8: Malviya Nagar Superstore ─────────────────────────────────────
    (8, "10079", "Marlboro Red 20s",           "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (8, "10080", "Marlboro Red 20s",           "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (8, "10081", "Marlboro Red 20s",           "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (8, "10082", "Pall Mall Red 20s",          "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (8, "10083", "Pall Mall Red 20s",          "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (8, "10084", "Mixed Tote I",               "totes",   "count",          1, "required_no_photo", "totes"),
    (8, "10085", "Fanta Orange 500ml",         "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),
    (8, "10086", "Fanta Orange 500ml",         "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),
    (8, "10087", "Empty Crate Return",         "returns", "scan",           1, "not_required",      "paper_box"),

    # ── Stop 9: Jagatpura Quick Stop ─────────────────────────────────────────
    (9, "10088", "Lambert & Butler King Size", "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (9, "10089", "Lambert & Butler King Size", "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (9, "10090", "Richmond Superkings",        "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (9, "10091", "Confectionery Tote J",       "totes",   "count",          1, "required_no_photo", "totes"),
    (9, "10092", "Snack Tote K",               "totes",   "count",          1, "required_no_photo", "totes"),
    (9, "10093", "Water Bottle Box x6",        "boxes",   "scan_and_count", 1, "required_no_photo", "paper_box"),
    (9, "10094", "Cornetto Vanilla",           "ice_cream", "scan_and_count", 1, "required_photo",  "ice_cream"),
    (9, "10095", "Cornetto Vanilla",           "ice_cream", "scan_and_count", 1, "required_photo",  "ice_cream"),

    # ── Stop 10: Sanganer News & Grocery ─────────────────────────────────────
    (10, "10096", "Marlboro Gold 20s",         "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (10, "10097", "Marlboro Gold 20s",         "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (10, "10098", "Camel Blue 20s",            "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (10, "10099", "Camel Blue 20s",            "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (10, "10100", "Juice Tote L",              "totes",   "count",          1, "required_no_photo", "totes"),
    (10, "10101", "Monster Energy",            "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),
    (10, "10102", "Monster Energy",            "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),
    (10, "10103", "Empty Bottle Crate",        "returns", "scan",           1, "not_required",      "paper_box"),

    # ── Stop 11: Muhana Market Store ─────────────────────────────────────────
    (11, "10104", "Amber Leaf 30g Pouch",      "cig_tob", "scan",           1, "required_no_photo", "tob"),
    (11, "10105", "Amber Leaf 30g Pouch",      "cig_tob", "scan",           1, "required_no_photo", "tob"),
    (11, "10106", "Pall Mall Red 20s",         "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (11, "10107", "Pall Mall Red 20s",         "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (11, "10108", "Soft Drinks Tote M",        "totes",   "count",          1, "required_no_photo", "totes"),
    (11, "10109", "Confectionery Tote N",      "totes",   "count",          1, "required_no_photo", "totes"),
    (11, "10110", "Snack Box x6",              "boxes",   "scan_and_count", 1, "required_no_photo", "paper_box"),
    (11, "10111", "Damaged Tray Return",       "returns", "scan",           1, "not_required",      "paper_box"),

    # ── Stop 12: Pratap Nagar Kirana ─────────────────────────────────────────
    (12, "10112", "Marlboro Red 20s",          "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (12, "10113", "Marlboro Red 20s",          "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (12, "10114", "Richmond Superkings",       "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (12, "10115", "Richmond Superkings",       "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (12, "10116", "Snack Tote O",              "totes",   "count",          1, "required_no_photo", "totes"),
    (12, "10117", "Magnum Classic",            "ice_cream", "scan_and_count", 1, "required_photo",  "ice_cream"),
    (12, "10118", "Magnum Classic",            "ice_cream", "scan_and_count", 1, "required_photo",  "ice_cream"),
    (12, "10119", "Coca Cola 500ml",           "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),
    (12, "10120", "Coca Cola 500ml",           "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),

    # ── Stop 13: Sitapura Industrial Canteen ─────────────────────────────────
    (13, "10121", "Camel Blue 20s",            "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (13, "10122", "Camel Blue 20s",            "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (13, "10123", "Lambert & Butler King Size","cig_tob", "scan",           1, "required_no_photo", "cig"),
    (13, "10124", "Juice Tote P",              "totes",   "count",          1, "required_no_photo", "totes"),
    (13, "10125", "Mixed Tote Q",              "totes",   "count",          1, "required_no_photo", "totes"),
    (13, "10126", "Crisps Assorted Box x12",   "boxes",   "scan_and_count", 1, "required_no_photo", "paper_box"),
    (13, "10127", "Juice Box x12",             "boxes",   "scan_and_count", 1, "required_no_photo", "paper_box"),
    (13, "10128", "Empty Crate Return",        "returns", "scan",           1, "not_required",      "paper_box"),

    # ── Stop 14: Durgapura Convenience Store ─────────────────────────────────
    (14, "10129", "Marlboro Gold 20s",         "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (14, "10130", "Marlboro Gold 20s",         "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (14, "10131", "Amber Leaf 50g Pouch",      "cig_tob", "scan",           1, "required_no_photo", "tob"),
    (14, "10132", "Amber Leaf 50g Pouch",      "cig_tob", "scan",           1, "required_no_photo", "tob"),
    (14, "10133", "Soft Drinks Tote R",        "totes",   "count",          1, "required_no_photo", "totes"),
    (14, "10134", "Fanta Orange 500ml",        "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),
    (14, "10135", "Fanta Orange 500ml",        "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),
    (14, "10136", "Red Bull 250ml",            "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),
    (14, "10137", "Empty Bottle Crate",        "returns", "scan",           1, "not_required",      "paper_box"),

    # ── Stop 15: Sodala General Store ────────────────────────────────────────
    (15, "10138", "Pall Mall Red 20s",         "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (15, "10139", "Pall Mall Red 20s",         "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (15, "10140", "Richmond Superkings",       "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (15, "10141", "Richmond Superkings",       "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (15, "10142", "Confectionery Tote S",      "totes",   "count",          1, "required_no_photo", "totes"),
    (15, "10143", "Juice Tote T",              "totes",   "count",          1, "required_no_photo", "totes"),
    (15, "10144", "Cornetto Vanilla",          "ice_cream", "scan_and_count", 1, "required_photo",  "ice_cream"),
    (15, "10145", "Cornetto Vanilla",          "ice_cream", "scan_and_count", 1, "required_photo",  "ice_cream"),
    (15, "10146", "Empty Crate Return",        "returns", "scan",           1, "not_required",      "paper_box"),

    # ── Stop 16: Shastri Nagar Daily Mart ────────────────────────────────────
    (16, "10147", "Marlboro Red 20s",          "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (16, "10148", "Marlboro Red 20s",          "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (16, "10149", "Marlboro Red 20s",          "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (16, "10150", "Amber Leaf 50g Pouch",      "cig_tob", "scan",           1, "required_no_photo", "tob"),
    (16, "10151", "Amber Leaf 50g Pouch",      "cig_tob", "scan",           1, "required_no_photo", "tob"),
    (16, "10152", "Soft Drinks Tote U",        "totes",   "count",          1, "required_no_photo", "totes"),
    (16, "10153", "Snack Tote V",              "totes",   "count",          1, "required_no_photo", "totes"),
    (16, "10154", "Coca Cola 500ml",           "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),
    (16, "10155", "Coca Cola 500ml",           "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),
    (16, "10156", "Empty Crate Return",        "returns", "scan",           1, "not_required",      "paper_box"),

    # ── Stop 17: Jhotwara Road Store ─────────────────────────────────────────
    (17, "10157", "Camel Blue 20s",            "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (17, "10158", "Camel Blue 20s",            "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (17, "10159", "Lambert & Butler King Size","cig_tob", "scan",           1, "required_no_photo", "cig"),
    (17, "10160", "Lambert & Butler King Size","cig_tob", "scan",           1, "required_no_photo", "cig"),
    (17, "10161", "Confectionery Tote W",      "totes",   "count",          1, "required_no_photo", "totes"),
    (17, "10162", "Crisps Assorted Box x12",   "boxes",   "scan_and_count", 1, "required_no_photo", "paper_box"),
    (17, "10163", "Water Bottle Box x6",       "boxes",   "scan_and_count", 1, "required_no_photo", "paper_box"),
    (17, "10164", "Monster Energy",            "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),
    (17, "10165", "Monster Energy",            "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),

    # ── Stop 18: Nirman Nagar Quick Mart ─────────────────────────────────────
    (18, "10166", "Marlboro Gold 20s",         "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (18, "10167", "Marlboro Gold 20s",         "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (18, "10168", "Pall Mall Red 20s",         "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (18, "10169", "Pall Mall Red 20s",         "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (18, "10170", "Soft Drinks Tote X",        "totes",   "count",          1, "required_no_photo", "totes"),
    (18, "10171", "Juice Tote Y",              "totes",   "count",          1, "required_no_photo", "totes"),
    (18, "10172", "Magnum Classic",            "ice_cream", "scan_and_count", 1, "required_photo",  "ice_cream"),
    (18, "10173", "Magnum Classic",            "ice_cream", "scan_and_count", 1, "required_photo",  "ice_cream"),
    (18, "10174", "Damaged Tray Return",       "returns", "scan",           1, "not_required",      "paper_box"),

    # ── Stop 19: Vidhyadhar Nagar Store ──────────────────────────────────────
    (19, "10175", "Richmond Superkings",       "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (19, "10176", "Richmond Superkings",       "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (19, "10177", "Amber Leaf 30g Pouch",      "cig_tob", "scan",           1, "required_no_photo", "tob"),
    (19, "10178", "Amber Leaf 30g Pouch",      "cig_tob", "scan",           1, "required_no_photo", "tob"),
    (19, "10179", "Snack Tote Z",              "totes",   "count",          1, "required_no_photo", "totes"),
    (19, "10180", "Confectionery Tote AA",     "totes",   "count",          1, "required_no_photo", "totes"),
    (19, "10181", "Fanta Orange 500ml",        "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),
    (19, "10182", "Fanta Orange 500ml",        "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),
    (19, "10183", "Coca Cola 500ml",           "fridge",  "scan_and_count", 1, "required_photo",    "fridge"),
    (19, "10184", "Empty Crate Return",        "returns", "scan",           1, "not_required",      "paper_box"),

    # ── Stop 20: Civil Lines Convenience ─────────────────────────────────────
    (20, "10185", "Marlboro Red 20s",          "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (20, "10186", "Marlboro Red 20s",          "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (20, "10187", "Camel Blue 20s",            "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (20, "10188", "Camel Blue 20s",            "cig_tob", "scan",           1, "required_no_photo", "cig"),
    (20, "10189", "Juice Tote BB",             "totes",   "count",          1, "required_no_photo", "totes"),
    (20, "10190", "Snack Box x6",              "boxes",   "scan_and_count", 1, "required_no_photo", "paper_box"),
    (20, "10191", "Crisps Assorted Box x12",   "boxes",   "scan_and_count", 1, "required_no_photo", "paper_box"),
    (20, "10192", "Cornetto Vanilla",          "ice_cream", "scan_and_count", 1, "required_photo",  "ice_cream"),
    (20, "10193", "Cornetto Vanilla",          "ice_cream", "scan_and_count", 1, "required_photo",  "ice_cream"),
    (20, "10194", "Empty Bottle Crate",        "returns", "scan",           1, "not_required",      "paper_box"),
]

# (id, route_name, driver_id, route_status)
_SEED_ROUTES = [
    (1, "Jaipur North Route",   1, "pending"),
    (2, "Jaipur Central Route", 2, "pending"),
    (3, "Jaipur South Route",   3, "pending"),
]

# (route_id, stop_id, sequence)
_SEED_ROUTE_STOPS = [
    # Route 1 — Jaipur North Route (Marcus Webb, driver 1)
    (1, 16, 1),
    (1, 17, 2),
    (1, 18, 3),
    (1, 19, 4),
    (1, 20, 5),
    (1, 15, 6),
    (1,  4, 7),

    # Route 2 — Jaipur Central Route (Priya Sharma, driver 2)
    (2,  1, 1),
    (2,  2, 2),
    (2,  3, 3),
    (2,  5, 4),
    (2,  6, 5),
    (2,  7, 6),
    (2, 14, 7),

    # Route 3 — Jaipur South Route (Jordan Lee, driver 3)
    (3,  8, 1),
    (3,  9, 2),
    (3, 10, 3),
    (3, 11, 4),
    (3, 12, 5),
    (3, 13, 6),
]


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def init_db():
    """
    Drop and recreate all tables, then seed with test data.

    POC NOTE: Tables are dropped on every startup so the schema always
    matches this file. This means all data resets on restart — acceptable
    for a POC. In production, use migrations (e.g. Alembic) instead.

    Called once at startup from server.py.
    """
    with get_db() as conn:
        # Drop all tables in reverse dependency order before recreating.
        # This ensures the schema is always in sync with the definitions above.
        conn.execute("DROP TABLE IF EXISTS route_stops")
        conn.execute("DROP TABLE IF EXISTS manifest")   # old table — clean up if present
        conn.execute("DROP TABLE IF EXISTS routes")
        conn.execute("DROP TABLE IF EXISTS products")
        conn.execute("DROP TABLE IF EXISTS stops")
        conn.execute("DROP TABLE IF EXISTS drivers")

        # Recreate in dependency order
        conn.execute(_CREATE_DRIVERS)
        conn.execute(_CREATE_STOPS)
        conn.execute(_CREATE_PRODUCTS)
        conn.execute(_CREATE_ROUTES)
        conn.execute(_CREATE_ROUTE_STOPS)

        # Seed — always runs because tables were just dropped
        conn.executemany(
            "INSERT INTO drivers (id, name, experience_level, is_new_driver) VALUES (?,?,?,?)",
            _SEED_DRIVERS,
        )
        conn.executemany(
            "INSERT INTO stops (id, stop_number, name, address, lat, lng, status) VALUES (?,?,?,?,?,?,?)",
            _SEED_STOPS,
        )
        conn.executemany(
            "INSERT INTO products (stop_id, barcode, name, section_tag, item_type, quantity, required_tag, icon_tag) "
            "VALUES (?,?,?,?,?,?,?,?)",
            _SEED_PRODUCTS,
        )
        conn.executemany(
            "INSERT INTO routes (id, route_name, driver_id, route_status) VALUES (?,?,?,?)",
            _SEED_ROUTES,
        )
        conn.executemany(
            "INSERT INTO route_stops (route_id, stop_id, sequence) VALUES (?,?,?)",
            _SEED_ROUTE_STOPS,
        )
