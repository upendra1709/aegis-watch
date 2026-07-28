import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from utils.data_utils import (
    get_machine_history, get_latest_reading, get_machine_info,
    get_maintenance_history, get_parts_history, get_downtime_history,
    log_activity,
)
from utils.model_utils import predict_health
from utils.browser_actions import trigger_print, trigger_voice
from components.widgets import gauge_chart, _hex_to_rgba
from styles.theme import status_badge_html, STATUS_COLOR


def render(machine_id, go_back):
    info = get_machine_info(machine_id)
    df = get_machine_history(machine_id)
    latest = df.iloc[-1].to_dict()
    health = predict_health(latest)
    color = STATUS_COLOR[health["status"]]
    fail_prob = health["failure_probability"]
    rul = health["remaining_useful_life"]
    cause = health["root_cause"]
    likely_part = health["likely_damaged_part"]
    severity = health["risk_level"]

    st.markdown("<div class='aw-secondary-btn'>", unsafe_allow_html=True)
    st.button("← Back to My Machines", on_click=go_back)
    st.markdown("</div>", unsafe_allow_html=True)

    top = st.columns([3, 1])
    with top[0]:
        st.markdown(f"<div class='aw-title'>{info.get('icon','⚙️')} {info['name']}</div>", unsafe_allow_html=True)
        st.markdown(status_badge_html(health["status"]), unsafe_allow_html=True)
    with top[1]:
        st.markdown(f"<div class='aw-muted' style='text-align:right;'>Last Maintenance</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='text-align:right; font-weight:700;'>{info['last_maintenance']}</div>", unsafe_allow_html=True)

    if health["status"] == "Critical":
        st.error("🛑 EMERGENCY SHUTDOWN WARNING — this machine shows critical failure indicators. Recommend immediate inspection.")

    st.write("")

    # ---- Gauges ----
    g1, g2 = st.columns(2)
    with g1:
        with st.container(border=True):
            st.plotly_chart(gauge_chart(health["score"], "Health Score"), use_container_width=True, config={"displayModeBar": False})
    with g2:
        with st.container(border=True):
            st.plotly_chart(gauge_chart(fail_prob, "Failure Probability", ), use_container_width=True, config={"displayModeBar": False})

    # ---- Current sensor values ----
    st.markdown("<div class='aw-card-title'>Current Sensor Values</div>", unsafe_allow_html=True)
    s1, s2, s3, s4, s5, s6 = st.columns(6)
    for col, label, value in [
        (s1, "Air Temp", f"{latest['air_temp']:.1f} K"),
        (s2, "Process Temp", f"{latest['process_temp']:.1f} K"),
        (s3, "Type", f"{latest['type']}"),
        (s4, "RPM", f"{latest['rpm']:.0f}"),
        (s5, "Torque", f"{latest.get('torque', 0):.0f} Nm"),
        (s6, "Tool Wear", f"{latest.get('tool_wear', 0):.0f} min"),
    ]:
        with col:
            with st.container(border=True):
                st.markdown(f"<div class='aw-kpi-label'>{label}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:20px; font-weight:800;'>{value}</div>", unsafe_allow_html=True)

    st.write("")

    # ---- Health timeline ----
    with st.container(border=True):
        st.markdown("<div class='aw-card-title'>Health Timeline</div>", unsafe_allow_html=True)
        scores = [predict_health(row)["score"] for _, row in df.iterrows()]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["timestamp"], y=scores, mode="lines+markers",
                                  line=dict(color=color, width=3), fill="tozeroy",
                                  fillcolor=_hex_to_rgba(color)))
        fig.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10),
                           paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                           font=dict(color="#cbd5e1"), yaxis=dict(range=[0, 100], gridcolor="rgba(255,255,255,0.06)"),
                           xaxis=dict(gridcolor="rgba(255,255,255,0.06)"))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ---- AI Prediction / RCA ----
    a1, a2 = st.columns(2)
    with a1:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title'> AI Prediction</div>", unsafe_allow_html=True)
            st.markdown(f"""
            - **Failure Probability:** {fail_prob}%
            - **Health Score:** {health['score']}/100
            - **Remaining Useful Life:** {rul}
            - **Model Confidence:** {health['cause_confidence']}
            """)
    with a2:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title'> Root Cause Analysis</div>", unsafe_allow_html=True)
            st.markdown(f"""
            - **Likely Cause:** {cause}
            - **Likely Damaged Part:** {likely_part}
            - **Risk Level:** {severity}
            - **Recommended Action:** {health['suggested_repair_action']}
            - **Maintenance Window:** {health['optimal_maintenance_time']}
            """)

    st.write("")

    # ---- Report actions ----
    with st.container(border=True):
        st.markdown("<div class='aw-card-title'> Report Actions</div>", unsafe_allow_html=True)
        report_df = pd.concat([df, pd.DataFrame({"predicted_score": scores})], axis=1)
        r1, r2, r3, r4, r5 = st.columns(5)
        with r1:
            st.download_button("⬇ Download CSV", report_df.to_csv(index=False),
                                file_name=f"{machine_id}_report.csv", mime="text/csv", use_container_width=True)
        with r2:
            if st.button("📧 Email Report", use_container_width=True):
                st.info("Simulated — connect to an email service (e.g. SMTP/SendGrid) to actually send.")
        with r3:
            if st.button("🖨️ Print Report", use_container_width=True):
                st.session_state["print_now"] = True
                log_activity("PRINT_REPORT", machine_id=machine_id)
        with r4:
            if st.button("📷 Live Camera", use_container_width=True):
                st.info("Simulated placeholder — connect an RTSP/IP camera feed here.")
        with r5:
            if st.button("🎙️ Voice Assistant", use_container_width=True):
                st.session_state["voice_now"] = (
                    f"{info['name']}. Status {health['status']}. "
                    f"Health score {health['score']} out of 100. "
                    f"Failure probability {fail_prob} percent. "
                    f"Likely cause: {cause}. "
                    f"Recommended action: {health['suggested_repair_action']}."
                )
                log_activity("VOICE_ASSISTANT", machine_id=machine_id)

        # Fire the print/voice trigger exactly once, right after the click
        # that requested it -- then clear the flag so it doesn't replay on
        # unrelated reruns (e.g. clicking a different button afterwards).
        if st.session_state.get("print_now"):
            trigger_print()
            st.session_state["print_now"] = False
        if st.session_state.get("voice_now"):
            trigger_voice(st.session_state["voice_now"])
            st.session_state["voice_now"] = None

    st.write("")

    # ---- History tables ----
    h1, h2, h3 = st.columns(3)
    with h1:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title'>🛠️ Maintenance History</div>", unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(get_maintenance_history(machine_id)), use_container_width=True, hide_index=True)
    with h2:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title'>🔩 Parts Replacement History</div>", unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(get_parts_history(machine_id)), use_container_width=True, hide_index=True)
    with h3:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title'>⏱️ Downtime History</div>", unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(get_downtime_history(machine_id)), use_container_width=True, hide_index=True)
