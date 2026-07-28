"""
MODEL LAYER
===========
Loads and runs the user's actual trained artifacts:

  - machine_failure_model.pkl   XGBoost binary failure classifier (10 engineered features)
  - failure_mode_model.pkl      Multi-output RandomForest -> which failure mode (TWF/HDF/PWF/OSF/RNF)
  - type_mapping.pkl            {"L": 0, "M": 1, "H": 2}
  - feature_columns.pkl         exact column order the models were trained on
  - evaluation_metrics.pkl      real accuracy/precision/recall/F1/ROC/confusion-matrix/feature
                                 importance computed against the held-out test split of
                                 ai4i2020_10k.csv at training time (used by the Analytics page)

All feature engineering, the root-cause rule engine, remaining-useful-life estimate,
maintenance-window recommendation, and repair knowledge base below are ported 1:1 from
`aegis_ml_model_reviewed.ipynb` (Steps 12, 12b, 12c, 13, 15). Nothing here is invented --
every formula and threshold matches the notebook exactly.
"""

import os
import numpy as np
import pandas as pd
import joblib

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

MODEL_PATH = os.path.join(BASE_DIR, "machine_failure_model.pkl")
MODE_MODEL_PATH = os.path.join(BASE_DIR, "failure_mode_model.pkl")
TYPE_MAPPING_PATH = os.path.join(BASE_DIR, "type_mapping.pkl")
FEATURE_COLS_PATH = os.path.join(BASE_DIR, "feature_columns.pkl")
METRICS_PATH = os.path.join(BASE_DIR, "evaluation_metrics.pkl")

for path, label in [
    (MODEL_PATH, "machine_failure_model.pkl"),
    (MODE_MODEL_PATH, "failure_mode_model.pkl"),
    (TYPE_MAPPING_PATH, "type_mapping.pkl"),
    (FEATURE_COLS_PATH, "feature_columns.pkl"),
]:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Required model artifact '{label}' not found at {path}. "
            "The app requires all four trained artifacts to be present in the project root."
        )

model = joblib.load(MODEL_PATH)
mode_model = joblib.load(MODE_MODEL_PATH)
TYPE_MAPPING = joblib.load(TYPE_MAPPING_PATH)
FEATURE_COLS = joblib.load(FEATURE_COLS_PATH)

FAILURE_MODE_COLS = ["TWF", "HDF", "PWF", "OSF", "RNF"]

_eval = joblib.load(METRICS_PATH) if os.path.exists(METRICS_PATH) else None

# ---------------------------------------------------------------------------
# Step 12 -- Root-cause rule engine (grounded in documented dataset thresholds)
# ---------------------------------------------------------------------------
TYPE_OVERSTRAIN_THRESHOLD = {0: 11000, 1: 12000, 2: 13000}  # L, M, H


def diagnose_root_causes(type_code, air_temp, process_temp, rpm, torque, wear):
    causes = []
    temp_diff = process_temp - air_temp
    power_w = torque * rpm * (2 * np.pi / 60)
    wear_torque = wear * torque

    if temp_diff < 8.6 and rpm < 1380:
        causes.append("Heat Dissipation Risk \u2014 insufficient cooling/airflow at low speed")

    if power_w < 3500:
        causes.append("Power Failure Risk \u2014 motor under-loaded")
    elif power_w > 9000:
        causes.append("Power Failure Risk \u2014 motor overloaded")

    threshold = TYPE_OVERSTRAIN_THRESHOLD.get(type_code, 12000)
    if wear_torque > threshold:
        causes.append("Overstrain Risk \u2014 excess mechanical strain on a worn tool")

    if 200 <= wear <= 240:
        causes.append("Tool Wear Risk \u2014 tool wear in the known failure range")
    elif wear > 240:
        causes.append("Tool Wear Risk \u2014 tool significantly overdue for replacement")

    if not causes:
        causes.append("No dominant sensor-based cause detected \u2014 if failure risk is still "
                       "high, consider Random Failure (inherently unpredictable, ~0.1% baseline)")

    return causes


# ---------------------------------------------------------------------------
# Step 12b -- Remaining Useful Time estimate
# ---------------------------------------------------------------------------
def estimate_remaining_operating_time(type_code, torque, wear):
    TOOL_WEAR_FAILURE_THRESHOLD_MIN = 200

    remaining_to_wear_failure = max(TOOL_WEAR_FAILURE_THRESHOLD_MIN - wear, 0)

    overstrain_threshold = TYPE_OVERSTRAIN_THRESHOLD.get(type_code, 12000)
    if torque > 0:
        wear_at_overstrain = overstrain_threshold / torque
        remaining_to_overstrain = max(wear_at_overstrain - wear, 0)
    else:
        remaining_to_overstrain = float("inf")

    return min(remaining_to_wear_failure, remaining_to_overstrain)


def format_rul(remaining_minutes):
    if remaining_minutes == float("inf"):
        return "Not estimable from wear-based factors alone"
    elif remaining_minutes <= 0:
        return "Already at/beyond estimated wear-based failure threshold"
    else:
        return f"~{remaining_minutes:.0f} more minutes of operation (at current torque)"


# ---------------------------------------------------------------------------
# Step 12c -- Optimal maintenance window
# ---------------------------------------------------------------------------
def recommend_maintenance_window(risk_level, remaining_minutes):
    if risk_level in ("Critical", "High Risk"):
        return "Immediate \u2014 do not continue operating, repair now"
    if remaining_minutes == float("inf"):
        return "No wear-driven urgency detected \u2014 follow standard maintenance schedule"
    if remaining_minutes <= 0:
        return "Overdue \u2014 schedule maintenance as soon as possible"
    buffer_minutes = remaining_minutes * 0.75
    return f"Schedule within the next ~{buffer_minutes:.0f} minutes of operation"


# ---------------------------------------------------------------------------
# Step 13 -- Cost & repair-time knowledge base
# ---------------------------------------------------------------------------
REPAIR_KB = {
    "Tool Wear":        {"time_hrs": "1-2",   "cost_tier": "Low ($)",            "action": "Replace or resharpen the tool", "part": "Cutting tool"},
    "Heat Dissipation": {"time_hrs": "3-4",   "cost_tier": "Medium ($$)",        "action": "Inspect cooling system / airflow", "part": "Cooling/ventilation system"},
    "Power":            {"time_hrs": "4-6",   "cost_tier": "Medium-High ($$$)", "action": "Check motor load / drive settings", "part": "Motor/drive unit"},
    "Overstrain":       {"time_hrs": "4-6",   "cost_tier": "Medium-High ($$$)", "action": "Reduce load, replace worn tool", "part": "Tool + spindle/drive train"},
    "Random":           {"time_hrs": "varies","cost_tier": "Varies",             "action": "Manual inspection recommended", "part": "Unknown \u2014 inspect fully"},
}


def lookup_repair_info(cause_text):
    for key in REPAIR_KB:
        if key.lower() in cause_text.lower():
            return REPAIR_KB[key]
    return REPAIR_KB["Random"]


MODE_KEYWORDS = {
    "HDF": "Heat Dissipation", "PWF": "Power Failure",
    "OSF": "Overstrain", "TWF": "Tool Wear",
}


# ---------------------------------------------------------------------------
# Step 15 -- End-to-end inference pipeline (identical to the notebook)
# ---------------------------------------------------------------------------
def predict_machine_health(type_letter, air_temp, process_temp, rpm, torque, wear):
    type_letter = str(type_letter).strip().upper()
    if type_letter not in TYPE_MAPPING:
        raise ValueError(f"type_letter must be one of {list(TYPE_MAPPING.keys())}, got {type_letter!r}")
    for name, val in [("air_temp", air_temp), ("process_temp", process_temp),
                       ("rpm", rpm), ("torque", torque), ("wear", wear)]:
        if not isinstance(val, (int, float)) or val < 0:
            raise ValueError(f"{name} must be a non-negative number, got {val}")

    type_code = TYPE_MAPPING[type_letter]

    temp_diff = process_temp - air_temp
    power_w = torque * rpm * (2 * np.pi / 60)
    wear_torque = wear * torque
    heat_load = process_temp * torque

    row = pd.DataFrame([{
        "Type": type_code,
        "Air_temperature_K": air_temp,
        "Process_temperature_K": process_temp,
        "Rotational_speed_rpm": rpm,
        "Torque_Nm": torque,
        "Tool_wear_min": wear,
        "Temp_Difference": temp_diff,
        "Power_W": power_w,
        "Wear_Torque": wear_torque,
        "Heat_Load": heat_load,
    }])[FEATURE_COLS]

    failure_prob = float(model.predict_proba(row)[0][1]) * 100
    health_score = 100 - failure_prob

    if failure_prob < 30:
        risk = "Healthy"
    elif failure_prob < 60:
        risk = "Warning"
    elif failure_prob < 80:
        risk = "High Risk"
    else:
        risk = "Critical"

    causes = diagnose_root_causes(type_code, air_temp, process_temp, rpm, torque, wear)

    mode_pred = mode_model.predict(row)[0]
    likely_modes = [c for c, flag in zip(FAILURE_MODE_COLS, mode_pred) if flag == 1]

    primary_cause = None
    cause_confidence = "Rule-based only (not corroborated by trained model)"
    for mode in likely_modes:
        keyword = MODE_KEYWORDS.get(mode)
        if keyword:
            match = next((c for c in causes if keyword in c), None)
            if match:
                primary_cause = match
                cause_confidence = "Confirmed by both rule engine and trained ML model"
                break
    if primary_cause is None:
        primary_cause = causes[0]

    uncorroborated_low_risk = (risk == "Healthy" and not likely_modes)

    if risk == "Healthy":
        if likely_modes:
            root_cause_display = f"Early indicator only (current risk is low): {primary_cause}"
        else:
            root_cause_display = "No significant risk indicators detected -- operating within normal parameters"
    elif cause_confidence.startswith("Rule-based only"):
        root_cause_display = f"{primary_cause} (not yet confirmed by the diagnostic model)"
    else:
        root_cause_display = primary_cause

    remaining_minutes = estimate_remaining_operating_time(type_code, torque, wear)
    rul_display = format_rul(remaining_minutes)
    maintenance_window = recommend_maintenance_window(risk, remaining_minutes)

    if uncorroborated_low_risk:
        repair_info = {
            "part": "None -- no risk factor confirmed by the model",
            "action": "No immediate action required -- continue routine monitoring",
            "time_hrs": "N/A",
            "cost_tier": "N/A",
        }
        maintenance_window = "Routine monitoring -- no immediate maintenance required (model-assessed risk is low)"
        rul_display = f"Wear-based indicator only, not corroborated by the model: {rul_display}"
    else:
        repair_info = lookup_repair_info(primary_cause)

    return {
        "failure_probability": round(failure_prob, 2),
        "health_score": round(health_score, 2),
        "risk_level": risk,
        "root_cause": root_cause_display,
        "cause_confidence": cause_confidence,
        "all_detected_causes": causes,
        "likely_failure_modes": likely_modes if likely_modes else ["None flagged"],
        "likely_damaged_part": repair_info["part"],
        "suggested_repair_action": repair_info["action"],
        "optimal_maintenance_time": maintenance_window,
        "estimated_repair_duration_hrs": repair_info["time_hrs"],
        "estimated_cost_tier": repair_info["cost_tier"],
        "remaining_useful_life": rul_display,
        "remaining_minutes_raw": remaining_minutes,
    }


# ---------------------------------------------------------------------------
# Streamlit-facing wrapper -- keeps the same {"score", "status"} contract the
# existing pages already use, and additionally exposes the full diagnostic
# report so machine_detail.py can show root cause / RUL / repair guidance.
#
# `latest_reading` must contain: type, air_temp, process_temp, rpm, torque, tool_wear
# ---------------------------------------------------------------------------
def predict_health(latest_reading: dict) -> dict:
    result = predict_machine_health(
        type_letter=latest_reading["type"],
        air_temp=float(latest_reading["air_temp"]),
        process_temp=float(latest_reading["process_temp"]),
        rpm=float(latest_reading["rpm"]),
        torque=float(latest_reading["torque"]),
        wear=float(latest_reading["tool_wear"]),
    )
    # The rest of the UI (badges, KPI cards) only understands 3 tiers.
    # "High Risk" is folded into "Critical" for status/color purposes only --
    # the true 4-tier risk_level is still available in the full result below
    # for the detailed diagnostic report.
    ui_status = "Critical" if result["risk_level"] in ("Critical", "High Risk") else result["risk_level"]

    merged = dict(result)
    merged["score"] = result["health_score"]
    merged["status"] = ui_status
    return merged


# ---------------------------------------------------------------------------
# Real evaluation metrics from training on the user's dataset (Analytics page).
# Falls back to None if evaluation_metrics.pkl wasn't generated.
# ---------------------------------------------------------------------------
if _eval is not None:
    MODEL_METRICS = {
        "accuracy": _eval["metrics"]["accuracy"],
        "precision": _eval["metrics"]["precision"],
        "recall": _eval["metrics"]["recall"],
        "f1_score": _eval["metrics"]["f1_score"],
        "roc_auc": _eval["metrics"]["roc_auc"],
        "ai_confidence_avg": _eval["metrics"]["cv_f1_mean"],
    }
    CONFUSION_MATRIX = _eval["confusion_matrix"]
    FEATURE_IMPORTANCE = _eval["feature_importance"]
    ROC_CURVE = _eval["roc_curve"]
    FAILURE_MODE_COUNTS = _eval["failure_mode_counts"]
    DATASET_INFO = {"n_rows": _eval["n_rows"], "failure_rate": _eval["failure_rate"]}
else:
    MODEL_METRICS = {"accuracy": None, "precision": None, "recall": None, "f1_score": None,
                      "roc_auc": None, "ai_confidence_avg": None}
    CONFUSION_MATRIX = {"labels": ["Healthy", "Failure"], "matrix": [[0, 0], [0, 0]]}
    FEATURE_IMPORTANCE = {"features": FEATURE_COLS, "importance": [0] * len(FEATURE_COLS)}
    ROC_CURVE = {"fpr": [0, 1], "tpr": [0, 1], "auc": None}
    FAILURE_MODE_COUNTS = {c: 0 for c in FAILURE_MODE_COLS}
    DATASET_INFO = {"n_rows": None, "failure_rate": None}

# Monthly/yearly failure-trend charts on the Analytics page are illustrative --
# the AI4I dataset has no timestamps, so no real time series can be derived
# from it. Left as clearly-labeled placeholders (see pages/analytics.py).
MONTHLY_FAILURE_TREND = {
    "months": ["Feb", "Mar", "Apr", "May", "Jun", "Jul"],
    "failures": [6, 4, 7, 3, 5, 2],
}
YEARLY_FAILURE_TREND = {
    "years": ["2022", "2023", "2024", "2025", "2026"],
    "failures": [58, 49, 41, 33, 22],
}
