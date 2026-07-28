"""
db_manager.py
----------------------------------------------------------------------
Shared SQLite database layer used by BOTH new backend modules:
    - sensor_simulator.py
    - alert_engine.py

INTEGRATED VERSION -- adapted to Aegis Watch
----------------------------------------------------------------------
Rather than opening a second, separate database file, this now points
at the SAME database the rest of the app already uses
(`utils/db_utils.py` -> aegis.db) and reuses its `machines` / `readings`
tables directly. That means:

    - sensor_simulator.py writes into the EXISTING `readings` table,
      using the EXISTING machine ids (M-01..M-10) -- so every page that
      already reads from db_utils (Home, My Machines, Machine Detail,
      Reports, Live Monitoring) automatically starts showing real,
      continuously-evolving live data with zero changes needed there.

    - alert_engine.py adds two NEW tables (`machine_status`, `alerts`)
      alongside the existing ones, giving the app a real, persistent
      alert lifecycle (state-change detection, cooldown, escalation,
      auto-resolution, history) instead of the old "recompute from
      scratch every rerun" alert derivation in utils/data_utils.py.

Nothing about the original schema is touched -- these tables are purely
additive.
----------------------------------------------------------------------
"""

import sqlite3
import threading
from contextlib import contextmanager

from utils.db_utils import DB_PATH
from utils.db_utils import init_db as init_machines_db

# SQLite handles concurrent writes poorly -> serialize writes with a lock.
# Simulator (writer) and Alert Engine (reader/writer) run on separate
# background threads, so this matters.
_lock = threading.Lock()


@contextmanager
def get_connection():
    """Context-managed SQLite connection, thread-safe for simultaneous
    simulator + alert-engine + Streamlit UI access. Points at the same
    aegis.db file used everywhere else in the app."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        with _lock:
            yield conn
            conn.commit()
    finally:
        conn.close()


def init_db():
    """Create all required tables if they don't already exist. Safe to
    call every time the app starts."""
    # 0) Make sure the existing machines/readings/logs schema (+ seed
    #    data) is in place first -- sensor_simulator and alert_engine
    #    both depend on the `machines` and `readings` tables it creates.
    init_machines_db()

    with get_connection() as conn:
        cur = conn.cursor()

        # 1) One row per machine: its CURRENT confirmed state + the
        #    in-progress "pending" state used for consecutive-cycle
        #    validation (see alert_engine.py). This is what the
        #    dashboard reads for "Machine Status".
        cur.execute("""
            CREATE TABLE IF NOT EXISTS machine_status (
                machine_id          TEXT PRIMARY KEY,
                current_state       TEXT DEFAULT 'Healthy',
                pending_state       TEXT,
                consecutive_count   INTEGER DEFAULT 0,
                health_score        REAL,
                failure_probability REAL,
                last_updated        TEXT
            )
        """)

        # 2) Alert lifecycle: one row per alert (open or resolved).
        #    Only ONE row per machine can have status='ACTIVE' at a time.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id         INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id       TEXT NOT NULL,
                state            TEXT NOT NULL,
                start_time       TEXT NOT NULL,
                last_updated     TEXT NOT NULL,
                resolved_time    TEXT,
                duration_seconds REAL,
                root_cause       TEXT,
                recommendation   TEXT,
                status           TEXT DEFAULT 'ACTIVE'  -- ACTIVE | RESOLVED | ESCALATED | SUPERSEDED
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_machine_status
            ON alerts(machine_id, status)
        """)

    print(f"[db_manager] Database ready at '{DB_PATH}'")


if __name__ == "__main__":
    init_db()
