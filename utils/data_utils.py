"""
DATA LAYER
==========
Machine identities and sensor readings are now persisted in a real SQLite
database (utils/db_utils.py / aegis.db) instead of the hardcoded dicts this
file used to contain. The database is seeded on first run with the same 10
demo machines and history that used to live here, so nothing about the
dashboard's appearance changes.

Every function below keeps the EXACT same name, signature, and return shape
it always had ({"type","air_temp","process_temp","rpm","torque","tool_wear"}
for readings, etc.) -- that's what lets every page (home, machine_list,
machine_detail, analytics, reports, live_monitoring) keep working completely
unchanged. This file is now just a thin pass-through to db_utils, plus the
alert-derivation logic that was always here.

Add / Edit / Delete Machine now write to the database via
db_utils.add_machine() / update_machine() / delete_machine() -- wired up in
pages/machine_list.py.
"""

from datetime import datetime, timedelta

from utils import db_utils
from utils.db_utils import (
    DEFAULT_READING_BY_TYPE, CATEGORY_ICONS,
    add_machine, update_machine, delete_machine,
    log_activity, get_recent_activity,
)

PLANT_NAME = "Aegis Industrial Plant — Unit 4"
COMPANY_NAME = "Aegis Watch Industries"
AI_MODEL_VERSION = "AEGIS XGBoost v1 (trained on ai4i2020_10k.csv)"
LAST_MODEL_UPDATE = "2026-07-23"

# Make sure the DB (and its schema + seed data) exists before anything
# tries to read from it. Safe to call on every import -- it's a no-op if
# the tables already exist.
db_utils.init_db()


def list_machines():
    return db_utils.list_machines()


def get_machine_history(machine_id: str, hours: int = None):
    """Returns a pandas DataFrame with a 'timestamp' column plus the same
    sensor columns as before -- unchanged shape for every page that consumes it."""
    import pandas as pd

    readings = db_utils.get_machine_history(machine_id)
    now = datetime.now()
    n = len(readings)
    timestamps = [now - timedelta(hours=(n - 1 - i)) for i in range(n)]
    df = pd.DataFrame(readings)
    df.insert(0, "timestamp", timestamps)
    return df


def get_latest_reading(machine_id: str) -> dict:
    return db_utils.get_latest_reading(machine_id)


def get_machine_info(machine_id: str) -> dict:
    return db_utils.get_machine_info(machine_id)


def get_maintenance_history(machine_id: str):
    return db_utils.get_maintenance_history(machine_id)


def get_parts_history(machine_id: str):
    return db_utils.get_parts_history(machine_id)


def get_downtime_history(machine_id: str):
    return db_utils.get_downtime_history(machine_id)


def get_recent_alerts():
    """Alert feed derived from real model predictions on each machine's latest reading."""
    from utils.model_utils import predict_health
    alerts = []
    now = datetime.now()
    machines = list_machines()
    for i, m in enumerate(machines):
        latest = get_latest_reading(m["id"])
        if not latest:
            continue
        health = predict_health(latest)
        if health["status"] in ("Warning", "Critical"):
            alerts.append({
                "time": (now - timedelta(minutes=15 * i)).strftime("%Y-%m-%d %H:%M"),
                "machine": m["name"],
                "severity": health["status"],
                "message": f"{m['name']} health score dropped to {health['score']}/100 -- {health['root_cause']}",
            })
    return alerts


def get_resolved_alerts():
    return [
        {"time": "2026-07-19 08:12", "machine": "Compressor Unit", "message": "Airflow warning auto-resolved after recalibration"},
        {"time": "2026-07-17 14:40", "machine": "Welding Arm", "message": "Tool wear warning cleared after replacement"},
    ]
