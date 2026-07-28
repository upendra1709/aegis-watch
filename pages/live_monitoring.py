import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

from utils.data_utils import list_machines
from alert_engine import get_all_machine_status, get_latest_reading
from styles.theme import status_badge_html, STATUS_COLOR

try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False


def render():
    st.markdown("<div class='aw-title'>Live Monitoring</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='aw-sub'>Live sensor feed from the background simulator, scored by the trained model every 3s</div>",
        unsafe_allow_html=True,
    )

    if HAS_AUTOREFRESH:
        st_autorefresh(interval=3000, key="live_monitor_refresh")
    else:
        st.warning("Install `streamlit-autorefresh` for automatic live updates: `pip install streamlit-autorefresh`")

    st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

    machines = {m["id"]: m for m in list_machines()}
    statuses = {s["machine_id"]: s for s in get_all_machine_status()}

    cols = st.columns(3)
    scores = []
    for i, machine_id in enumerate(sorted(machines.keys())):
        m = machines[machine_id]
        status = statuses.get(machine_id)
        reading = get_latest_reading(machine_id)

        if status is None or status.get("health_score") is None or reading is None:
            with cols[i % 3]:
                with st.container(border=True):
                    st.markdown(f"<div class='aw-card-title'>{m['icon']} {m['name']}</div>", unsafe_allow_html=True)
                    st.markdown("<span class='aw-muted'>Waiting for the first simulated reading...</span>", unsafe_allow_html=True)
            continue

        state = status["current_state"]
        score = status["health_score"]
        scores.append(score)
        color = STATUS_COLOR.get(state, "#9aa2b1")

        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"<div class='aw-card-title'>{m['icon']} {m['name']}</div>", unsafe_allow_html=True)
                st.markdown(status_badge_html(state), unsafe_allow_html=True)
                st.markdown(
                    f"<div class='aw-kpi-value' style='font-size:24px; color:{color}; margin-top:6px;'>{score}/100</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"<div class='aw-muted' style='line-height:1.8; margin-top:4px;'>"
                    f"🌡️ {reading['air_temp']:.1f}K &nbsp; 🔥 {reading['process_temp']:.1f}K &nbsp; "
                    f"⚙️ {reading['rpm']:.0f} RPM<br>🔧 {reading['torque']:.1f} Nm &nbsp; 🛠️ {reading['tool_wear']:.0f} min",
                    unsafe_allow_html=True,
                )
                if status.get("current_alert"):
                    st.markdown(
                        f"<div class='aw-muted' style='margin-top:6px; color:{color};'>⚠ {status['current_alert']['root_cause']}</div>",
                        unsafe_allow_html=True,
                    )

    st.write("")
    with st.container(border=True):
        st.markdown("<div class='aw-card-title'>Live Fleet Average Health</div>", unsafe_allow_html=True)
        avg = sum(scores) / len(scores) if scores else 0
        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=avg,
            number={"font": {"color": "white"}},
            gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#3b82f6"}},
        ))
        fig.update_layout(height=220, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)",
                           font=dict(color="#cbd5e1"))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
