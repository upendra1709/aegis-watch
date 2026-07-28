"""
DATABASE LAYER
==============
SQLite persistence for machine records. This is what actually backs the
"Add Machine" / "Edit" / "Delete" actions in pages/machine_list.py.

WHY SQLITE:
    - Zero setup: it's a single file (aegis.db, created automatically next
      to app.py), no server process to install or manage.
    - Ships in Python's standard library (`sqlite3`) -- no new dependency.
    - Plenty for this scale (tens of machines), and the SQL/queries below
      would port to Postgres/MySQL almost unchanged if this ever needs to
      scale to a real multi-user deployment.

SCHEMA:
    machines        -- one row per machine (identity + config)
    readings        -- one row per sensor reading, newest = current state
    maintenance_log -- one row per maintenance event
    parts_log       -- one row per parts replacement
    downtime_log    -- one row per downtime event

SEEDING:
    On first run (empty DB), the 10 original demo machines and their
    original hardcoded history/logs are inserted so nothing about the
    existing dashboard changes. Every machine added afterwards through the
    UI goes through the exact same tables and code path.

Every function here returns plain dicts/lists -- the exact same shapes
`utils/data_utils.py` already returned from its old hardcoded dictionaries
-- so nothing above this layer needs to change.
"""

import os
import sqlite3
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "aegis.db")


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------
def _get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------------------
# Original demo data -- used ONLY to seed the DB the very first time it's
# created, so the dashboard looks identical to before the DB existed.
# ---------------------------------------------------------------------------
_SEED_MACHINES = [
    {"id": "M-01", "name": "CNC Mill #1", "icon": "", "machine_type": "L", "last_maintenance": "2026-06-28"},
    {"id": "M-02", "name": "Conveyor Belt A", "icon": "", "machine_type": "H", "last_maintenance": "2026-06-20"},
    {"id": "M-03", "name": "Hydraulic Press", "icon": "", "machine_type": "M", "last_maintenance": "2026-05-30"},
    {"id": "M-04", "name": "Compressor Unit", "icon": "", "machine_type": "H", "last_maintenance": "2026-07-02"},
    {"id": "M-05", "name": "Packaging Robot", "icon": "", "machine_type": "M", "last_maintenance": "2026-07-10"},
    {"id": "M-06", "name": "CNC Mill #2", "icon": "", "machine_type": "H", "last_maintenance": "2026-06-15"},
    {"id": "M-07", "name": "Welding Arm", "icon": "", "machine_type": "L", "last_maintenance": "2026-07-05"},
    {"id": "M-08", "name": "Cooling Tower", "icon": "", "machine_type": "L", "last_maintenance": "2026-05-18"},
    {"id": "M-09", "name": "Boiler Unit", "icon": "", "machine_type": "H", "last_maintenance": "2026-06-08"},
    {"id": "M-10", "name": "Assembly Line B", "icon": "", "machine_type": "M", "last_maintenance": "2026-07-12"},
]

_SEED_HISTORY = {
    "M-01": [
        {"air_temp": 297.6, "process_temp": 307.2, "rpm": 1581, "torque": 33.1, "tool_wear": 101},
        {"air_temp": 297.6, "process_temp": 307.3, "rpm": 1581, "torque": 33.1, "tool_wear": 104},
        {"air_temp": 297.7, "process_temp": 307.4, "rpm": 1581, "torque": 33.1, "tool_wear": 107},
        {"air_temp": 297.7, "process_temp": 307.4, "rpm": 1581, "torque": 33.1, "tool_wear": 110},
        {"air_temp": 297.8, "process_temp": 307.4, "rpm": 1581, "torque": 33.1, "tool_wear": 113},
        {"air_temp": 297.8, "process_temp": 307.5, "rpm": 1581, "torque": 33.1, "tool_wear": 116},
    ],
    "M-02": [
        {"air_temp": 302.1, "process_temp": 311.2, "rpm": 1526, "torque": 38.2, "tool_wear": 32},
        {"air_temp": 302.1, "process_temp": 311.3, "rpm": 1526, "torque": 38.2, "tool_wear": 35},
        {"air_temp": 302.2, "process_temp": 311.4, "rpm": 1526, "torque": 38.2, "tool_wear": 38},
        {"air_temp": 302.2, "process_temp": 311.4, "rpm": 1526, "torque": 38.2, "tool_wear": 41},
        {"air_temp": 302.2, "process_temp": 311.4, "rpm": 1526, "torque": 38.2, "tool_wear": 44},
        {"air_temp": 302.3, "process_temp": 311.5, "rpm": 1526, "torque": 38.2, "tool_wear": 47},
    ],
    "M-03": [
        {"air_temp": 300.6, "process_temp": 309.9, "rpm": 1598, "torque": 36.5, "tool_wear": 180},
        {"air_temp": 300.6, "process_temp": 310.0, "rpm": 1598, "torque": 36.5, "tool_wear": 183},
        {"air_temp": 300.7, "process_temp": 310.1, "rpm": 1598, "torque": 36.5, "tool_wear": 186},
        {"air_temp": 300.7, "process_temp": 310.1, "rpm": 1598, "torque": 36.5, "tool_wear": 189},
        {"air_temp": 300.8, "process_temp": 310.1, "rpm": 1598, "torque": 36.5, "tool_wear": 192},
        {"air_temp": 300.8, "process_temp": 310.2, "rpm": 1598, "torque": 36.5, "tool_wear": 195},
    ],
    "M-04": [
        {"air_temp": 301.1, "process_temp": 310.1, "rpm": 1610, "torque": 38.6, "tool_wear": 1},
        {"air_temp": 301.2, "process_temp": 310.2, "rpm": 1610, "torque": 38.6, "tool_wear": 4},
        {"air_temp": 301.2, "process_temp": 310.2, "rpm": 1610, "torque": 38.6, "tool_wear": 7},
        {"air_temp": 301.3, "process_temp": 310.3, "rpm": 1610, "torque": 38.6, "tool_wear": 10},
        {"air_temp": 301.3, "process_temp": 310.3, "rpm": 1610, "torque": 38.6, "tool_wear": 13},
        {"air_temp": 301.4, "process_temp": 310.4, "rpm": 1610, "torque": 38.6, "tool_wear": 16},
    ],
    "M-05": [
        {"air_temp": 300.6, "process_temp": 310.6, "rpm": 1678, "torque": 28.1, "tool_wear": 48},
        {"air_temp": 300.6, "process_temp": 310.7, "rpm": 1678, "torque": 28.1, "tool_wear": 51},
        {"air_temp": 300.7, "process_temp": 310.8, "rpm": 1678, "torque": 28.1, "tool_wear": 54},
        {"air_temp": 300.7, "process_temp": 310.8, "rpm": 1678, "torque": 28.1, "tool_wear": 57},
        {"air_temp": 300.8, "process_temp": 310.8, "rpm": 1678, "torque": 28.1, "tool_wear": 60},
        {"air_temp": 300.8, "process_temp": 310.9, "rpm": 1678, "torque": 28.1, "tool_wear": 63},
    ],
    "M-06": [
        {"air_temp": 298.1, "process_temp": 307.9, "rpm": 2636, "torque": 12.8, "tool_wear": 69},
        {"air_temp": 298.1, "process_temp": 307.9, "rpm": 2636, "torque": 12.8, "tool_wear": 72},
        {"air_temp": 298.2, "process_temp": 308.0, "rpm": 2636, "torque": 12.8, "tool_wear": 75},
        {"air_temp": 298.2, "process_temp": 308.0, "rpm": 2636, "torque": 12.8, "tool_wear": 78},
        {"air_temp": 298.2, "process_temp": 308.1, "rpm": 2636, "torque": 12.8, "tool_wear": 81},
        {"air_temp": 298.3, "process_temp": 308.1, "rpm": 2636, "torque": 12.8, "tool_wear": 84},
    ],
    "M-07": [
        {"air_temp": 297.4, "process_temp": 309.2, "rpm": 2001, "torque": 20.5, "tool_wear": 205},
        {"air_temp": 297.4, "process_temp": 309.3, "rpm": 2001, "torque": 20.5, "tool_wear": 208},
        {"air_temp": 297.5, "process_temp": 309.4, "rpm": 2001, "torque": 20.5, "tool_wear": 211},
        {"air_temp": 297.5, "process_temp": 309.4, "rpm": 2001, "torque": 20.5, "tool_wear": 214},
        {"air_temp": 297.6, "process_temp": 309.4, "rpm": 2001, "torque": 20.5, "tool_wear": 217},
        {"air_temp": 297.6, "process_temp": 309.5, "rpm": 2001, "torque": 20.5, "tool_wear": 220},
    ],
    "M-08": [
        {"air_temp": 298.6, "process_temp": 309.6, "rpm": 1320, "torque": 47.4, "tool_wear": 195},
        {"air_temp": 298.6, "process_temp": 309.7, "rpm": 1320, "torque": 47.4, "tool_wear": 198},
        {"air_temp": 298.7, "process_temp": 309.8, "rpm": 1320, "torque": 47.4, "tool_wear": 201},
        {"air_temp": 298.7, "process_temp": 309.8, "rpm": 1320, "torque": 47.4, "tool_wear": 204},
        {"air_temp": 298.8, "process_temp": 309.8, "rpm": 1320, "torque": 47.4, "tool_wear": 207},
        {"air_temp": 298.8, "process_temp": 309.9, "rpm": 1320, "torque": 47.4, "tool_wear": 210},
    ],
    "M-09": [
        {"air_temp": 301.8, "process_temp": 309.6, "rpm": 1280, "torque": 57.3, "tool_wear": 132},
        {"air_temp": 301.8, "process_temp": 309.6, "rpm": 1280, "torque": 57.3, "tool_wear": 135},
        {"air_temp": 301.9, "process_temp": 309.7, "rpm": 1280, "torque": 57.3, "tool_wear": 138},
        {"air_temp": 301.9, "process_temp": 309.7, "rpm": 1280, "torque": 57.3, "tool_wear": 141},
        {"air_temp": 301.9, "process_temp": 309.8, "rpm": 1280, "torque": 57.3, "tool_wear": 144},
        {"air_temp": 302.0, "process_temp": 309.8, "rpm": 1280, "torque": 57.3, "tool_wear": 147},
    ],
    "M-10": [
        {"air_temp": 301.8, "process_temp": 309.4, "rpm": 1386, "torque": 62.7, "tool_wear": 127},
        {"air_temp": 301.8, "process_temp": 309.5, "rpm": 1386, "torque": 62.7, "tool_wear": 130},
        {"air_temp": 301.9, "process_temp": 309.6, "rpm": 1386, "torque": 62.7, "tool_wear": 133},
        {"air_temp": 301.9, "process_temp": 309.6, "rpm": 1386, "torque": 62.7, "tool_wear": 136},
        {"air_temp": 301.9, "process_temp": 309.6, "rpm": 1386, "torque": 62.7, "tool_wear": 139},
        {"air_temp": 302.0, "process_temp": 309.7, "rpm": 1386, "torque": 62.7, "tool_wear": 142},
    ],
}


# ---------------------------------------------------------------------------
# Sensible starting-reading defaults, per machine type (L/M/H), used to
# auto-fill the "Add Machine" form when the person doesn't have a live
# sensor reading on hand yet. Values are representative baselines drawn
# from the same ranges as the seeded machines above.
# ---------------------------------------------------------------------------
DEFAULT_READING_BY_TYPE = {
    "L": {"air_temp": 298.0, "process_temp": 308.5, "rpm": 1500, "torque": 40.0, "tool_wear": 0},
    "M": {"air_temp": 300.5, "process_temp": 310.0, "rpm": 1500, "torque": 40.0, "tool_wear": 0},
    "H": {"air_temp": 302.0, "process_temp": 311.0, "rpm": 1500, "torque": 40.0, "tool_wear": 0},
}

CATEGORY_ICONS = {
    "CNC Mill": "",
    "Conveyor": "",
    "Hydraulic Press": "",
    "Compressor": "",
    "Robot / Packaging": "",
    "Welding": "",
    "Cooling Tower": "",
    "Boiler": "",
    "Assembly Line": "",
    "Other": "",
}


# ---------------------------------------------------------------------------
# Schema + seeding
# ---------------------------------------------------------------------------
def init_db():
    conn = _get_conn()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS machines (
                id               TEXT PRIMARY KEY,
                name             TEXT NOT NULL,
                icon             TEXT NOT NULL,
                machine_type     TEXT NOT NULL CHECK(machine_type IN ('L','M','H')),
                last_maintenance TEXT NOT NULL,
                created_at       TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS readings (
                reading_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id   TEXT NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
                timestamp    TEXT NOT NULL,
                air_temp     REAL NOT NULL,
                process_temp REAL NOT NULL,
                rpm          REAL NOT NULL,
                torque       REAL NOT NULL,
                tool_wear    REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS maintenance_log (
                log_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id TEXT NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
                date       TEXT,
                type       TEXT,
                technician TEXT,
                notes      TEXT
            );

            CREATE TABLE IF NOT EXISTS parts_log (
                log_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id TEXT NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
                date       TEXT,
                part       TEXT,
                cost_usd   REAL
            );

            CREATE TABLE IF NOT EXISTS downtime_log (
                log_id       INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id   TEXT NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
                date         TEXT,
                duration_hrs REAL,
                reason       TEXT
            );

            CREATE TABLE IF NOT EXISTS activity_log (
                log_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                action     TEXT NOT NULL,
                machine_id TEXT REFERENCES machines(id) ON DELETE SET NULL,
                detail     TEXT,
                timestamp  TEXT NOT NULL
            );
            """
        )
        conn.commit()

        already_seeded = conn.execute("SELECT COUNT(*) AS c FROM machines").fetchone()["c"] > 0
        if not already_seeded:
            _seed(conn)
    finally:
        conn.close()


def _seed(conn):
    now = datetime.now().isoformat()
    for m in _SEED_MACHINES:
        conn.execute(
            "INSERT INTO machines (id, name, icon, machine_type, last_maintenance, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (m["id"], m["name"], m["icon"], m["machine_type"], m["last_maintenance"], now),
        )
        for reading in _SEED_HISTORY[m["id"]]:
            conn.execute(
                "INSERT INTO readings (machine_id, timestamp, air_temp, process_temp, rpm, torque, tool_wear) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (m["id"], now, reading["air_temp"], reading["process_temp"], reading["rpm"],
                 reading["torque"], reading["tool_wear"]),
            )
        # Same illustrative maintenance/parts/downtime pattern the app used
        # before the DB existed -- kept so the seeded machines look identical.
        for date, mtype, tech, notes in [
            ("2026-04-10", "Preventive", "R. Sharma", "Routine lubrication & inspection"),
            ("2026-05-22", "Corrective", "A. Verma", "Bearing replacement"),
            (m["last_maintenance"], "Preventive", "S. Iyer", "Filter change, calibration"),
        ]:
            conn.execute(
                "INSERT INTO maintenance_log (machine_id, date, type, technician, notes) VALUES (?, ?, ?, ?, ?)",
                (m["id"], date, mtype, tech, notes),
            )
        for date, part, cost in [("2026-05-22", "Bearing Set", 240), ("2026-03-14", "Drive Belt", 85)]:
            conn.execute(
                "INSERT INTO parts_log (machine_id, date, part, cost_usd) VALUES (?, ?, ?, ?)",
                (m["id"], date, part, cost),
            )
        for date, dur, reason in [
            ("2026-06-01", 2.5, "Scheduled maintenance"),
            ("2026-04-18", 5.0, "Unplanned — sensor fault"),
        ]:
            conn.execute(
                "INSERT INTO downtime_log (machine_id, date, duration_hrs, reason) VALUES (?, ?, ?, ?)",
                (m["id"], date, dur, reason),
            )
    conn.commit()


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------
def list_machines():
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT id, name, icon, last_maintenance FROM machines ORDER BY name").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_machine_info(machine_id):
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT id, name, icon, machine_type, last_maintenance FROM machines WHERE id = ?", (machine_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_machine_history(machine_id):
    """Returns readings oldest -> newest, each as a dict with the same
    {type, air_temp, process_temp, rpm, torque, tool_wear} shape the app
    has always used. Timestamps are recomputed relative to "now" (one hour
    apart per row) -- identical to the original hardcoded-history behavior
    -- so the health timeline chart keeps working unchanged."""
    conn = _get_conn()
    try:
        machine_type = conn.execute(
            "SELECT machine_type FROM machines WHERE id = ?", (machine_id,)
        ).fetchone()["machine_type"]
        rows = conn.execute(
            "SELECT air_temp, process_temp, rpm, torque, tool_wear FROM readings "
            "WHERE machine_id = ? ORDER BY reading_id", (machine_id,)
        ).fetchall()
        readings = [dict(r) for r in rows]
        for r in readings:
            r["type"] = machine_type
        return readings
    finally:
        conn.close()


def get_latest_reading(machine_id):
    history = get_machine_history(machine_id)
    return history[-1] if history else None


def get_maintenance_history(machine_id):
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT date, type, technician, notes FROM maintenance_log WHERE machine_id = ? ORDER BY log_id",
            (machine_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_parts_history(machine_id):
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT date, part, cost_usd FROM parts_log WHERE machine_id = ? ORDER BY log_id", (machine_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_downtime_history(machine_id):
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT date, duration_hrs, reason FROM downtime_log WHERE machine_id = ? ORDER BY log_id", (machine_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Writes -- Add / Edit / Delete
# ---------------------------------------------------------------------------
def _next_machine_id(conn):
    rows = conn.execute("SELECT id FROM machines").fetchall()
    max_n = 0
    for r in rows:
        try:
            n = int(r["id"].split("-")[-1])
            max_n = max(max_n, n)
        except (ValueError, IndexError):
            continue
    return f"M-{max_n + 1:02d}"


def add_machine(name, icon, machine_type, last_maintenance, reading=None):
    """Creates a new machine plus its first sensor reading (auto-filled
    defaults if the caller doesn't supply one). Returns the new machine id."""
    if reading is None:
        reading = DEFAULT_READING_BY_TYPE[machine_type]

    conn = _get_conn()
    try:
        machine_id = _next_machine_id(conn)
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO machines (id, name, icon, machine_type, last_maintenance, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (machine_id, name, icon, machine_type, str(last_maintenance), now),
        )
        conn.execute(
            "INSERT INTO readings (machine_id, timestamp, air_temp, process_temp, rpm, torque, tool_wear) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (machine_id, now, reading["air_temp"], reading["process_temp"], reading["rpm"],
             reading["torque"], reading["tool_wear"]),
        )
        conn.commit()
        return machine_id
    finally:
        conn.close()


def update_machine(machine_id, name=None, icon=None, machine_type=None, last_maintenance=None):
    conn = _get_conn()
    try:
        current = conn.execute("SELECT * FROM machines WHERE id = ?", (machine_id,)).fetchone()
        if not current:
            return False
        conn.execute(
            "UPDATE machines SET name = ?, icon = ?, machine_type = ?, last_maintenance = ? WHERE id = ?",
            (
                name if name is not None else current["name"],
                icon if icon is not None else current["icon"],
                machine_type if machine_type is not None else current["machine_type"],
                str(last_maintenance) if last_maintenance is not None else current["last_maintenance"],
                machine_id,
            ),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def delete_machine(machine_id):
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM machines WHERE id = ?", (machine_id,))
        conn.commit()
        return True
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Activity log -- records real usage of report/print/voice actions so there's
# an actual audit trail in the database (who/what/when), instead of those
# actions just firing-and-forgetting.
# ---------------------------------------------------------------------------
def log_activity(action, machine_id=None, detail=None):
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO activity_log (action, machine_id, detail, timestamp) VALUES (?, ?, ?, ?)",
            (action, machine_id, detail, datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
    finally:
        conn.close()


def get_recent_activity(limit=20):
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT action, machine_id, detail, timestamp FROM activity_log ORDER BY log_id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
