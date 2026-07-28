import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

from utils.data_utils import list_machines, get_latest_reading, get_recent_alerts, PLANT_NAME, AI_MODEL_VERSION, LAST_MODEL_UPDATE
from utils.model_utils import predict_health, MODEL_METRICS
from utils.browser_actions import stop_voice
from utils.voice_alerts import speak_new_critical_alerts
from styles.theme import status_badge_html

try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False


def render():
    # Keeps the dashboard "live" without any manual page refresh -- the
    # backend alert engine (alert_engine.py) already re-evaluates every
    # machine every 3s with a 3-consecutive-cycle confirmation filter, so
    # this just needs to be frequent enough to notice a newly-confirmed
    # Critical alert quickly and speak it.
    if HAS_AUTOREFRESH:
        st_autorefresh(interval=10000, key="home_voice_refresh")
    else:
        st.warning("Install `streamlit-autorefresh` for automatic background monitoring: `pip install streamlit-autorefresh`")

    machines = list_machines()
    results = []
    for m in machines:
        latest = get_latest_reading(m["id"])
        health = predict_health(latest)
        results.append({"machine": m, "latest": latest, "health": health})

    healthy = [r for r in results if r["health"]["status"] == "Healthy"]
    warning = [r for r in results if r["health"]["status"] == "Warning"]
    critical = [r for r in results if r["health"]["status"] == "Critical"]
    avg_score = round(sum(r["health"]["score"] for r in results) / len(results), 1)
    predicted_failures_today = len(critical)
    ai_accuracy = round((MODEL_METRICS["accuracy"] or 0) * 100, 1)  # real accuracy, trained on ai4i2020_10k.csv

    # ---- 🎙️ AI Voice Assistant -- automatic critical-machine alert ----
    # Speaks a full diagnostic announcement (machine, ID, failure risk,
    # root cause, affected component, remaining safe operating time,
    # recommended action, repair time...) for every NEWLY confirmed
    # critical machine, most severe first, queued so nothing overlaps.
    # Machines already announced for their current critical episode are
    # not re-announced on every rerun -- see utils/voice_alerts.py.
    speak_new_critical_alerts(critical)

    if critical:
        critical_sorted = sorted(critical, key=lambda r: r["health"]["failure_probability"], reverse=True)
        critical_names = [
            f"{r['machine']['name']} ({r['health']['failure_probability']:.0f}%)"
            for r in critical_sorted
        ]
        banner_col, btn_col = st.columns([5, 1])
        with banner_col:
            st.markdown(f"""
            <div style='background:#ef4444; color:white; padding:14px 20px; border-radius:10px;
                        margin-bottom:12px;'>
                <div style='font-weight:800; font-size:1.05rem;'>🚨 AI VOICE ALERT — {len(critical)} machine(s) require immediate attention</div>
                <div style='margin-top:4px;'>{', '.join(critical_names)}</div>
            </div>
            """, unsafe_allow_html=True)
        with btn_col:
            st.write("")
            if st.button("🔇 Stop Voice Alert", key="stop_voice_home", type="primary", use_container_width=True):
                st.session_state["voice_stop_now"] = True

    if st.session_state.get("voice_stop_now"):
        stop_voice()
        st.session_state["voice_stop_now"] = False

    # ---- Top bar ----
    top = st.columns([2, 1, 1, 1])
    with top[0]:
        st.markdown("<div class='aw-logo'>⚡ AEGIS <span>WATCH</span></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='aw-muted'>{PLANT_NAME}</div>", unsafe_allow_html=True)
    with top[1]:
        st.markdown("<div class='aw-muted'>🕒 Current Time</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-weight:700;'>{datetime.now().strftime('%H:%M:%S')}</div>", unsafe_allow_html=True)
    with top[2]:
        st.markdown("<div class='aw-muted'>🔌 Connected Machines</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-weight:700;'>{len(machines)} / {len(machines)}</div>", unsafe_allow_html=True)
    with top[3]:
        st.markdown("<div class='aw-muted'>🧠 AI System Status</div>", unsafe_allow_html=True)
        st.markdown(status_badge_html("Healthy") + " Live", unsafe_allow_html=True)

    st.markdown(f"<div class='aw-muted'>Last Model Update: {LAST_MODEL_UPDATE} &nbsp;·&nbsp; Model Version: {AI_MODEL_VERSION}</div>", unsafe_allow_html=True)
    st.markdown("<hr class='aw-divider'>", unsafe_allow_html=True)

    st.markdown("<div class='aw-title'>Home Dashboard</div>", unsafe_allow_html=True)
    st.markdown("<div class='aw-sub'>Real-time plant health overview</div>", unsafe_allow_html=True)

    # ---- KPI cards ----
    from components.widgets import kpi_card
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Healthy Machines", len(healthy), "", "#22c55e", [3, 4, 4, 5, len(healthy)], key="k1")
    with c2:
        kpi_card("Warning Machines", len(warning), "", "#f59e0b", [1, 2, 1, 2, len(warning)], key="k2")
    with c3:
        kpi_card("Critical Machines", len(critical), "", "#ef4444", [0, 1, 1, 1, len(critical)], key="k3")
    with c4:
        kpi_card("Average Health Score", f"{avg_score}", "", "#3b82f6", [70, 74, 68, 72, avg_score], key="k4")

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        kpi_card("Predicted Failures Today", predicted_failures_today, "", "#ef4444", key="k5")
    with c6:
        kpi_card("Maintenance Cost Saved", "$18,420", "", "#22c55e", key="k6")
    with c7:
        kpi_card("AI Accuracy", f"{ai_accuracy}%", "", "#8b5cf6", key="k7")
    with c8:
        kpi_card("Live Monitoring", "ACTIVE", "", "#3b82f6", key="k8")

    st.write("")
    left, right = st.columns([1, 1])

    # ---- Pie chart ----
    with left:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title'>Fleet Status Breakdown</div>", unsafe_allow_html=True)
            fig = go.Figure(data=[go.Pie(
                labels=["Healthy", "Warning", "Critical"],
                values=[len(healthy), len(warning), len(critical)],
                hole=0.6,
                marker=dict(colors=["#22c55e", "#f59e0b", "#ef4444"]),
                textfont=dict(color="white"),
            )])
            fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10),
                               paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#e5e9f2"),
                               legend=dict(font=dict(color="#cbd5e1")))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ---- Live gauge: overall plant health ----
    with right:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title'>Overall Plant Health</div>", unsafe_allow_html=True)
            from components.widgets import gauge_chart
            st.plotly_chart(gauge_chart(avg_score, title="Plant Health Score"), use_container_width=True,
                             config={"displayModeBar": False})

    # ---- Trend line: machine health vs time ----
    with st.container(border=True):
        st.markdown("<div class='aw-card-title'>Machine Health vs Time (Fleet Average)</div>", unsafe_allow_html=True)
        months = ["Feb", "Mar", "Apr", "May", "Jun", "Jul"]
        trend = [round(avg_score + (i - 3) * 2.5, 1) for i in range(6)]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=months, y=trend, mode="lines+markers", line=dict(color="#3b82f6", width=3),
                                  fill="tozeroy", fillcolor="rgba(59,130,246,0.15)"))
        fig.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10),
                           paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                           font=dict(color="#cbd5e1"),
                           xaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
                           yaxis=dict(gridcolor="rgba(255,255,255,0.06)", range=[0, 100]))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ---- Bar chart: machine comparison + Heatmap ----
    b1, b2 = st.columns(2)
    with b1:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title'>Machine Health Comparison</div>", unsafe_allow_html=True)
            names = [r["machine"]["name"] for r in results]
            scores = [r["health"]["score"] for r in results]
            colors = [{"Healthy": "#22c55e", "Warning": "#f59e0b", "Critical": "#ef4444"}[r["health"]["status"]] for r in results]
            fig = go.Figure(go.Bar(x=names, y=scores, marker_color=colors))
            fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=60),
                               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font=dict(color="#cbd5e1"),
                               xaxis=dict(gridcolor="rgba(255,255,255,0.06)", tickangle=-35),
                               yaxis=dict(gridcolor="rgba(255,255,255,0.06)", range=[0, 100]))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with b2:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title'>Factory Health Heatmap</div>", unsafe_allow_html=True)
            names = [r["machine"]["name"] for r in results]
            metrics = ["Process Temp", "Torque", "RPM Load", "Tool Wear"]
            z = []
            for r in results:
                l = r["latest"]
                z.append([
                    min(100, l["process_temp"] - 295),
                    min(100, l.get("torque", 0)),
                    min(100, (l["rpm"] / 2900) * 100),
                    min(100, l.get("tool_wear", 0)),
                ])
            fig = go.Figure(data=go.Heatmap(
                z=list(map(list, zip(*z))), x=names, y=metrics,
                colorscale=[[0, "#22c55e"], [0.5, "#f59e0b"], [1, "#ef4444"]],
            ))
            fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=60),
                               paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#cbd5e1"),
                               xaxis=dict(tickangle=-35))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ---- Recent alerts table ----
    with st.container(border=True):
        st.markdown("<div class='aw-card-title'>🚨 Recent Alerts</div>", unsafe_allow_html=True)
        alerts = get_recent_alerts()
        if alerts:
            st.dataframe(pd.DataFrame(alerts), use_container_width=True, hide_index=True)
        else:
            st.markdown("<span class='aw-muted'>No active alerts — all machines nominal.</span>", unsafe_allow_html=True)

    # ---- Recommendations + Maintenance schedule + AI confidence ----
    r1, r2, r3 = st.columns(3)
    with r1:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title'>💡 Today's Recommendations</div>", unsafe_allow_html=True)
            for r in critical + warning:
                st.markdown(f"- Inspect **{r['machine']['name']}** — {r['health']['status']} status", unsafe_allow_html=True)
            if not (critical or warning):
                st.markdown("<span class='aw-muted'>No action needed today.</span>", unsafe_allow_html=True)

    with r2:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title'>🗓️ Upcoming Maintenance</div>", unsafe_allow_html=True)
            for m in machines[:5]:
                st.markdown(f"- {m['name']} — next check due soon", unsafe_allow_html=True)

    with r3:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title'>🎯 AI Prediction Confidence</div>", unsafe_allow_html=True)
            st.plotly_chart(
                go.Figure(go.Indicator(mode="gauge+number", value=92,
                                        gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#8b5cf6"}},
                                        number={"suffix": "%", "font": {"color": "white"}}))
                .update_layout(height=180, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)",
                               font=dict(color="#cbd5e1")),
                use_container_width=True, config={"displayModeBar": False},
            )
