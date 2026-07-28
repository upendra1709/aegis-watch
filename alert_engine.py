"""
alert_engine.py
----------------------------------------------------------------------
MODULE 2: Industrial-Grade Alert Management Engine -- INTEGRATED with
Aegis Watch and wired directly to the REAL trained model
(utils/model_utils.py -> machine_failure_model.pkl / failure_mode_model.pkl).

Solves the "alerting again and again" problem by turning raw, noisy,
continuous ML predictions into a clean, stateful alert lifecycle:

  1. Machine states          Healthy / Warning / Critical
  2. State-change detection  -> alert ONLY on a state transition
  3. Cooldown                -> active alert just gets "touched", not duplicated
  4. Consecutive validation  -> 3 consecutive cycles required before any
                                 state change is confirmed (kills false alarms)
  5. Escalation               -> exactly one alert per transition
  6. Auto-resolution          -> back to Healthy closes the alert + logs duration
  7. Alert history             -> every alert (active or resolved) is kept
  8. Dashboard query helpers   -> ready-made functions for the UI

This is genuinely new capability -- previously (utils/data_utils.py ->
get_recent_alerts()) the app just recomputed "is anything currently
Warning/Critical" from scratch on every Streamlit rerun, with no
persistence, no history, and no protection against the same condition
re-alerting every few seconds. This module replaces that.

INTEGRATION (already done)
---------------------------
  - predict_failure_probability()  -> calls utils.model_utils.predict_health(),
                                        i.e. the same trained XGBoost model
                                        used everywhere else in the app.
  - get_root_cause()               -> pulled straight from that same
                                        prediction's root-cause field.
  - get_recommendation()           -> pulled from the same prediction's
                                        repair-action + maintenance-window
                                        fields.

HOW TO RUN
----------
Standalone:
    python alert_engine.py

Inside Streamlit (background thread) -- already wired up in app.py:
    from alert_engine import start_alert_engine_thread
    if "alert_engine_started" not in st.session_state:
        start_alert_engine_thread()
        st.session_state.alert_engine_started = True
----------------------------------------------------------------------
"""

import time
import threading
from datetime import datetime

from db_manager import get_connection, init_db
from utils.model_utils import predict_health

CYCLE_SECONDS = 3          # how often the engine evaluates each machine
CONSECUTIVE_REQUIRED = 3   # cycles a new state must persist before it's confirmed

# 3-tier states, matching the rest of the UI (styles/theme.py STATUS_COLOR
# and utils/model_utils.predict_health()'s "status" field, which already
# folds the model's "High Risk" tier into "Critical" for display purposes).
STATE_ORDER = ["Healthy", "Warning", "Critical"]

# Caches the full diagnostic dict from the most recent predict_health()
# call per machine, so a confirmed transition can reuse the already-computed
# root cause / recommendation instead of re-running the model.
_LAST_HEALTH = {}


# ----------------------------------------------------------------------
# Data access helpers
# ----------------------------------------------------------------------

def _get_machine_ids():
    with get_connection() as conn:
        rows = conn.execute("SELECT id FROM machines ORDER BY id").fetchall()
    return [r["id"] for r in rows]


def get_latest_reading(machine_id: str):
    """Latest sensor reading for a machine, including its type -- ready
    to hand straight to utils.model_utils.predict_health()."""
    with get_connection() as conn:
        reading_row = conn.execute(
            """SELECT air_temp, process_temp, rpm, torque, tool_wear
               FROM readings WHERE machine_id = ? ORDER BY reading_id DESC LIMIT 1""",
            (machine_id,),
        ).fetchone()
        machine_row = conn.execute(
            "SELECT machine_type FROM machines WHERE id = ?", (machine_id,)
        ).fetchone()
    if reading_row is None or machine_row is None:
        return None
    reading = dict(reading_row)
    reading["type"] = machine_row["machine_type"]
    return reading


# ----------------------------------------------------------------------
# Model integration -- wired to the real trained model
# ----------------------------------------------------------------------

def predict_failure_probability(machine_id: str, reading: dict) -> float:
    """Runs the real trained model (utils.model_utils.predict_health) and
    returns P(failure) in [0, 1]. Caches the full diagnostic result so
    get_root_cause()/get_recommendation() below don't need to re-run it."""
    health = predict_health(reading)
    _LAST_HEALTH[machine_id] = health
    return health["failure_probability"] / 100.0


def _state_for(machine_id: str) -> str:
    """3-tier UI state ('Healthy'/'Warning'/'Critical') for the most
    recently cached prediction of this machine."""
    return _LAST_HEALTH[machine_id]["status"]


def get_root_cause(machine_id: str, state: str, reading: dict) -> str:
    health = _LAST_HEALTH.get(machine_id)
    if health:
        return health["root_cause"]
    return f"Root cause analysis pending for {machine_id} ({state})"


def get_recommendation(machine_id: str, state: str, root_cause: str) -> str:
    health = _LAST_HEALTH.get(machine_id)
    if health:
        return f"{health['suggested_repair_action']} -- {health['optimal_maintenance_time']}"
    return f"Inspect {machine_id} -- recommendation pending"


# ----------------------------------------------------------------------
# Machine status / alert row helpers
# ----------------------------------------------------------------------

def _get_or_create_status_row(conn, machine_id):
    row = conn.execute(
        "SELECT * FROM machine_status WHERE machine_id = ?", (machine_id,)
    ).fetchone()
    if row is None:
        conn.execute(
            """INSERT INTO machine_status (machine_id, current_state, last_updated)
               VALUES (?, 'Healthy', ?)""",
            (machine_id, datetime.now().isoformat()),
        )
        row = conn.execute(
            "SELECT * FROM machine_status WHERE machine_id = ?", (machine_id,)
        ).fetchone()
    return dict(row)


def _get_active_alert(conn, machine_id):
    row = conn.execute(
        """SELECT * FROM alerts WHERE machine_id = ? AND status = 'ACTIVE'
           ORDER BY alert_id DESC LIMIT 1""",
        (machine_id,),
    ).fetchone()
    return dict(row) if row else None


# ----------------------------------------------------------------------
# 6. Alert resolution / 5. Escalation / 2. State-change / 3. Cooldown
# ----------------------------------------------------------------------

def _close_alert(conn, alert, reason="RESOLVED"):
    now = datetime.now()
    start = datetime.fromisoformat(alert["start_time"])
    duration = (now - start).total_seconds()
    conn.execute(
        """UPDATE alerts SET resolved_time = ?, duration_seconds = ?,
           status = ?, last_updated = ? WHERE alert_id = ?""",
        (now.isoformat(), duration, reason, now.isoformat(), alert["alert_id"]),
    )


def _open_alert(conn, machine_id, state, root_cause, recommendation):
    now = datetime.now().isoformat()
    conn.execute(
        """INSERT INTO alerts
           (machine_id, state, start_time, last_updated, root_cause,
            recommendation, status)
           VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE')""",
        (machine_id, state, now, now, root_cause, recommendation),
    )


def _touch_active_alert(conn, alert):
    """Cooldown: same state persists -> just bump last_updated, no new alert."""
    conn.execute(
        "UPDATE alerts SET last_updated = ? WHERE alert_id = ?",
        (datetime.now().isoformat(), alert["alert_id"]),
    )


def _handle_confirmed_transition(conn, machine_id, old_state, new_state, reading):
    """Called only once a state change has survived CONSECUTIVE_REQUIRED
    cycles. Exactly one alert action happens per transition."""
    active_alert = _get_active_alert(conn, machine_id)

    if new_state == "Healthy":
        # 6. Auto-resolution
        if active_alert:
            _close_alert(conn, active_alert, reason="RESOLVED")
        return

    # Any transition into/within an abnormal state: close the previous
    # active alert (if any -- e.g. escalating Warning -> Critical) and
    # open exactly one new alert for the new state.
    if active_alert:
        _close_alert(conn, active_alert, reason="ESCALATED" if
                     STATE_ORDER.index(new_state) > STATE_ORDER.index(old_state)
                     else "SUPERSEDED")

    root_cause = get_root_cause(machine_id, new_state, reading)
    recommendation = get_recommendation(machine_id, new_state, root_cause)
    _open_alert(conn, machine_id, new_state, root_cause, recommendation)


# ----------------------------------------------------------------------
# 4. Consecutive prediction validation + main per-machine cycle
# ----------------------------------------------------------------------

def process_machine(machine_id: str):
    """Runs ONE evaluation cycle for one machine. Safe to call on any
    schedule -- all confirmed state lives in SQLite, not in memory, so
    this can also be triggered directly for testing."""
    reading = get_latest_reading(machine_id)
    if reading is None:
        return  # simulator hasn't produced data yet

    probability = predict_failure_probability(machine_id, reading)
    raw_state = _state_for(machine_id)
    health_score = _LAST_HEALTH[machine_id]["health_score"]
    now = datetime.now().isoformat()

    with get_connection() as conn:
        status = _get_or_create_status_row(conn, machine_id)
        current_state = status["current_state"]

        if raw_state == current_state:
            # 2. No state change -> no new alert. Reset any pending
            # transition and just heartbeat the active alert (cooldown).
            conn.execute(
                """UPDATE machine_status
                   SET pending_state = NULL, consecutive_count = 0,
                       health_score = ?, failure_probability = ?, last_updated = ?
                   WHERE machine_id = ?""",
                (health_score, probability, now, machine_id),
            )
            active_alert = _get_active_alert(conn, machine_id)
            if active_alert:
                _touch_active_alert(conn, active_alert)  # 3. cooldown
            return

        # raw_state differs from confirmed current_state
        if status["pending_state"] == raw_state:
            consecutive_count = status["consecutive_count"] + 1
        else:
            consecutive_count = 1  # new candidate state, restart counter

        if consecutive_count >= CONSECUTIVE_REQUIRED:
            # 4. Confirmed after N consecutive cycles -> apply transition
            _handle_confirmed_transition(conn, machine_id, current_state, raw_state, reading)
            conn.execute(
                """UPDATE machine_status
                   SET current_state = ?, pending_state = NULL, consecutive_count = 0,
                       health_score = ?, failure_probability = ?, last_updated = ?
                   WHERE machine_id = ?""",
                (raw_state, health_score, probability, now, machine_id),
            )
        else:
            # Not yet confirmed -- update the tentative numbers only,
            # do NOT alert on a single (or double) abnormal reading.
            conn.execute(
                """UPDATE machine_status
                   SET pending_state = ?, consecutive_count = ?,
                       health_score = ?, failure_probability = ?, last_updated = ?
                   WHERE machine_id = ?""",
                (raw_state, consecutive_count, health_score, probability, now, machine_id),
            )


def run_alert_engine(stop_event: threading.Event = None):
    """Main loop -- evaluates every machine every CYCLE_SECONDS."""
    init_db()
    machine_ids = _get_machine_ids()
    print(f"[alert_engine] Started, evaluating {len(machine_ids)} machines every {CYCLE_SECONDS}s ...")
    while stop_event is None or not stop_event.is_set():
        for machine_id in _get_machine_ids():
            process_machine(machine_id)
        time.sleep(CYCLE_SECONDS)


def start_alert_engine_thread():
    """Run the alert engine in a background daemon thread (use inside
    Streamlit so it doesn't block the UI). Returns (thread, stop_event)."""
    stop_event = threading.Event()
    thread = threading.Thread(target=run_alert_engine, args=(stop_event,), daemon=True)
    thread.start()
    return thread, stop_event


# ----------------------------------------------------------------------
# 8. Dashboard output -- ready-made query helpers.
# Import these directly into the Streamlit pages; no redesign needed.
# ----------------------------------------------------------------------

def get_machine_status(machine_id: str):
    """Current Status / Health Score / Failure Probability / Last Updated
    / Current Alert for ONE machine."""
    with get_connection() as conn:
        status_row = conn.execute(
            "SELECT * FROM machine_status WHERE machine_id = ?", (machine_id,)
        ).fetchone()
        alert_row = conn.execute(
            """SELECT * FROM alerts WHERE machine_id = ? AND status = 'ACTIVE'
               ORDER BY alert_id DESC LIMIT 1""",
            (machine_id,),
        ).fetchone()

    status = dict(status_row) if status_row else {
        "machine_id": machine_id, "current_state": "Unknown",
        "health_score": None, "failure_probability": None, "last_updated": None,
    }
    status["current_alert"] = dict(alert_row) if alert_row else None
    return status


def get_all_machine_status():
    """Status for every machine -- drop straight into a dashboard table."""
    return [get_machine_status(mid) for mid in _get_machine_ids()]


def get_active_alerts():
    """All currently active alerts across every machine."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM alerts WHERE status = 'ACTIVE' ORDER BY start_time DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_alert_history(machine_id: str = None, limit: int = 50):
    """Full alert history (active + resolved), optionally filtered to one
    machine. Used for the 'Alert History' / 'Resolved Alerts' views."""
    with get_connection() as conn:
        if machine_id:
            rows = conn.execute(
                """SELECT * FROM alerts WHERE machine_id = ?
                   ORDER BY start_time DESC LIMIT ?""",
                (machine_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM alerts ORDER BY start_time DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    run_alert_engine()
