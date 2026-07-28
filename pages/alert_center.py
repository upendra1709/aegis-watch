import streamlit as st
import pandas as pd

from utils.data_utils import log_activity, get_machine_info, get_latest_reading
from utils.model_utils import predict_health
from utils.browser_actions import trigger_voice, queue_voice_alerts, stop_voice
from utils.voice_alerts import build_voice_script
from alert_engine import get_active_alerts, get_alert_history


def _machine_name(machine_id):
    info = get_machine_info(machine_id)
    return info["name"] if info else machine_id


def _to_rows(alerts):
    rows = []
    for a in alerts:
        rows.append({
            "time": a["start_time"][:16].replace("T", " "),
            "machine": _machine_name(a["machine_id"]),
            "state": a["state"],
            "root_cause": a["root_cause"],
            "recommendation": a["recommendation"],
            "status": a["status"],
        })
    return rows


def render():
    st.markdown("<div class='aw-title'>Alert Center</div>", unsafe_allow_html=True)
    st.markdown("<div class='aw-sub'>Live, stateful alerts from the alert engine — no duplicate re-alerts, full history</div>", unsafe_allow_html=True)

    active_alerts = get_active_alerts()
    critical_alerts = [a for a in active_alerts if a["state"] == "Critical"]
    warning_alerts = [a for a in active_alerts if a["state"] == "Warning"]
    history = get_alert_history()
    resolved = [a for a in history if a["status"] != "ACTIVE"]

    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title' style='color:#ef4444;'>🚨 Critical Alerts</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='aw-kpi-value' style='color:#ef4444;'>{len(critical_alerts)}</div>", unsafe_allow_html=True)
    with c2:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title' style='color:#f59e0b;'>⚠️ Warning Alerts</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='aw-kpi-value' style='color:#f59e0b;'>{len(warning_alerts)}</div>", unsafe_allow_html=True)
    with c3:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title' style='color:#22c55e;'>✅ Resolved Alerts</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='aw-kpi-value' style='color:#22c55e;'>{len(resolved)}</div>", unsafe_allow_html=True)

    st.write("")

    if critical_alerts:
        st.error(f"🛑 EMERGENCY NOTIFICATION: {len(critical_alerts)} machine(s) in critical condition — immediate attention required.")

    with st.container(border=True):
        st.markdown("<div class='aw-card-title'>Active Alerts</div>", unsafe_allow_html=True)
        if active_alerts:
            st.dataframe(pd.DataFrame(_to_rows(active_alerts)), use_container_width=True, hide_index=True)
        else:
            st.markdown("<span class='aw-muted'>No active alerts.</span>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("<div class='aw-card-title'>Resolved / Alert History</div>", unsafe_allow_html=True)
        if resolved:
            st.dataframe(pd.DataFrame(_to_rows(resolved)), use_container_width=True, hide_index=True)
        else:
            st.markdown("<span class='aw-muted'>No resolved alerts yet.</span>", unsafe_allow_html=True)

    st.write("")
    st.markdown("<div class='aw-card-title'>Notification Channels</div>", unsafe_allow_html=True)
    n1, n2, n3, n4 = st.columns(4)
    with n1:
        if st.button("📧 Send Email Alert", use_container_width=True):
            st.info("Simulated — connect to an email/SMTP service to actually send.")
    with n2:
        if st.button("📱 SMS Alert (placeholder)", use_container_width=True):
            st.info("Simulated — connect to an SMS gateway (e.g. Twilio) to actually send.")
    with n3:
        if st.button("🎙️ AI Voice Alert", use_container_width=True):
            if critical_alerts:
                # Full diagnostic script per active CRITICAL alert, most
                # severe (highest failure probability) first, queued so
                # several machines don't talk over each other.
                enriched = []
                for a in critical_alerts:
                    reading = get_latest_reading(a["machine_id"])
                    if reading is None:
                        continue
                    health = predict_health(reading)
                    enriched.append((health["failure_probability"], a, health))
                enriched.sort(key=lambda t: t[0], reverse=True)

                scripts = [
                    build_voice_script(_machine_name(a["machine_id"]), a["machine_id"], health)
                    for _, a, health in enriched
                ]
                st.session_state["voice_queue_now"] = scripts
                log_activity("VOICE_ALARM", detail=f"{len(scripts)} critical alert(s) announced")
            elif warning_alerts:
                a = warning_alerts[0]
                st.session_state["voice_now"] = (
                    f"Warning. {_machine_name(a['machine_id'])} health score has dropped. Please review."
                )
            else:
                st.session_state["voice_now"] = "All machines are currently healthy. No active alerts."
    with n4:
        if st.button("🔇 Stop Voice Alert", use_container_width=True):
            st.session_state["voice_stop_now"] = True

    if st.session_state.get("voice_now"):
        trigger_voice(st.session_state["voice_now"])
        st.session_state["voice_now"] = None
    if st.session_state.get("voice_queue_now"):
        queue_voice_alerts(st.session_state["voice_queue_now"])
        st.session_state["voice_queue_now"] = None
    if st.session_state.get("voice_stop_now"):
        stop_voice()
        st.session_state["voice_stop_now"] = False
