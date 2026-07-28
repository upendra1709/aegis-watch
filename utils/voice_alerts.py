"""
AI VOICE ALERT ENGINE
======================================================================
Turns the model's live diagnostic output (utils/model_utils.predict_health)
into a professional, spoken industrial-monitoring-assistant announcement --
and decides WHEN to speak using the same alert-lifecycle data the Alert
Center already relies on (alert_engine.get_active_alerts()), so a machine
is only announced once per confirmed critical episode, not on every rerun.

Nothing here is hardcoded per machine. Every sentence is assembled from
whatever the model/root-cause engine/RUL estimator/repair knowledge base
actually returned for that machine's latest reading.

Used by: pages/home.py, pages/alert_center.py (and any other page that
wants the same "queue newest-critical-first, don't repeat" behaviour --
just call speak_new_critical_alerts(critical_results)).
----------------------------------------------------------------------
"""

import streamlit as st

from utils.browser_actions import queue_voice_alerts


# ----------------------------------------------------------------------
# 1. Priority level -- derived from the model's own failure probability,
#    not a separate hardcoded judgement call.
# ----------------------------------------------------------------------
def _priority_level(probability: float) -> str:
    if probability >= 95:
        return "Priority one, emergency"
    elif probability >= 85:
        return "Priority two, urgent"
    else:
        return "Priority three, high"


# ----------------------------------------------------------------------
# 2. Worker-friendly instructions -- generic categories keyed off whatever
#    the root-cause engine / repair knowledge base already flagged for
#    THIS reading (utils/model_utils.py: diagnose_root_causes / REPAIR_KB),
#    not a fixed script per machine.
# ----------------------------------------------------------------------
def _worker_instructions(health: dict) -> list:
    cause = (health.get("root_cause") or "").lower()
    part = (health.get("likely_damaged_part") or "").lower()
    lines = []

    if "heat dissipation" in cause or "cooling" in part:
        lines += [
            "Check the cooling system and airflow around the machine.",
            "Reduce machine load until temperatures return to normal.",
        ]
    if "power failure" in cause or "motor" in part or "drive" in part:
        lines += [
            "Check the motor load and drive settings.",
            "Do not increase speed or load any further.",
        ]
    if "overstrain" in cause or "spindle" in part:
        lines += [
            "Reduce load immediately.",
            "Inspect the tool and spindle for wear or damage.",
        ]
    if "tool wear" in cause or "cutting tool" in part:
        lines += [
            "Inspect the cutting tool for wear.",
            "Replace or resharpen the tool before continuing operation.",
        ]

    if not lines:
        lines = [
            "Stop the machine safely and perform a full manual inspection.",
            "Do not continue production until the machine is cleared by maintenance.",
        ]
    return lines


# ----------------------------------------------------------------------
# 3. Full spoken script for one machine, built entirely from live data.
# ----------------------------------------------------------------------
def build_voice_script(machine_name: str, machine_id: str, health: dict) -> str:
    probability = health["failure_probability"]
    score = health["health_score"]
    root_cause = health["root_cause"]
    part = health["likely_damaged_part"]
    action = health["suggested_repair_action"]
    window = health["optimal_maintenance_time"]
    repair_hrs = health.get("estimated_repair_duration_hrs")
    rul = health["remaining_useful_life"]
    priority = _priority_level(probability)
    worker_lines = _worker_instructions(health)

    sentences = [
        "Warning. Critical machine detected.",
        f"Machine {machine_name}, I D {machine_id}.",
        f"Failure risk {probability:.0f} percent. Health score {score:.0f} out of 100.",
        f"{priority}.",
        f"Root cause: {root_cause}.",
        f"Likely affected component: {part}.",
        f"Estimated remaining safe operating time: {rul}.",
        f"Recommended action: {action}.",
    ]

    sentences.append("Immediate worker instructions.")
    sentences.extend(worker_lines)

    sentences.append(f"Maintenance window: {window}.")
    if repair_hrs and str(repair_hrs).upper() != "N/A":
        sentences.append(f"Estimated repair time: approximately {repair_hrs} hours.")

    sentences.append("Please notify the maintenance department immediately.")
    return " ".join(sentences)


# ----------------------------------------------------------------------
# 4. Decide what's NEW and speak only that -- most severe first, queued
#    (never overlapping, never re-announcing an already-spoken alert).
# ----------------------------------------------------------------------
def speak_new_critical_alerts(critical_results: list) -> list:
    """
    critical_results: list of {"machine": {...}, "health": {...}} dicts
    (already filtered to status == "Critical") for the current rerun.

    Speaks a full diagnostic announcement for every critical machine that
    hasn't been announced yet for its CURRENT confirmed-critical episode,
    most-severe (highest failure probability) first, queued so multiple
    machines never talk over each other.

    Dedup is keyed on the alert engine's own alert_id (alert_engine.py),
    which already only mints a new id on a genuine state transition into
    Critical -- so a machine that stays Critical isn't re-announced every
    few seconds, but a NEW machine going critical, or the same machine
    resolving and later going critical again, always gets a fresh alert_id
    and is announced.

    Returns the untouched critical_results list, so callers can reuse it
    for a banner without recomputing anything.
    """
    if not critical_results:
        return critical_results

    from alert_engine import get_active_alerts

    active_alerts = get_active_alerts()
    alert_id_by_machine = {
        a["machine_id"]: a["alert_id"] for a in active_alerts if a["state"] == "Critical"
    }

    if "spoken_alert_ids" not in st.session_state:
        st.session_state.spoken_alert_ids = set()

    unspoken = [
        r for r in critical_results
        if alert_id_by_machine.get(r["machine"]["id"]) is not None
        and alert_id_by_machine[r["machine"]["id"]] not in st.session_state.spoken_alert_ids
    ]

    # 7. Multiple critical machines -> most critical (highest failure
    # probability) announced first.
    unspoken.sort(key=lambda r: r["health"]["failure_probability"], reverse=True)

    if unspoken:
        scripts = [
            build_voice_script(r["machine"]["name"], r["machine"]["id"], r["health"])
            for r in unspoken
        ]
        queue_voice_alerts(scripts)
        for r in unspoken:
            st.session_state.spoken_alert_ids.add(alert_id_by_machine[r["machine"]["id"]])

    return critical_results
