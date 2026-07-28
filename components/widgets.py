import streamlit as st
import plotly.graph_objects as go
from styles.theme import STATUS_COLOR, status_badge_html


def _hex_to_rgba(hex_color, alpha=0.15):
    """Convert '#22c55e' -> 'rgba(34,197,94,0.15)'. Plotly rejects '#22c55e26'."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return f"rgba(59,130,246,{alpha})"  # fallback blue
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def kpi_card(label, value, icon="📊", color="#3b82f6", spark_values=None, key=""):
    with st.container(border=True):
        top = st.columns([3, 1])
        with top[0]:
            st.markdown(f"<div class='aw-kpi-label'>{label}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='aw-kpi-value'>{value}</div>", unsafe_allow_html=True)
        with top[1]:
            st.markdown(f"<div class='aw-kpi-icon' style='text-align:right;'>{icon}</div>", unsafe_allow_html=True)
        if spark_values:
            fig = go.Figure()
            fig.add_trace(go.Scatter(y=spark_values, mode="lines", line=dict(color=color, width=2.5),
                                      fill="tozeroy", fillcolor=_hex_to_rgba(color)))
            fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=42,
                               xaxis=dict(visible=False), yaxis=dict(visible=False),
                               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=f"spark_{key}")


def gauge_chart(value, title="Health Score", max_value=100, height=260):
    if value >= 75:
        color = STATUS_COLOR["Healthy"]
    elif value >= 45:
        color = STATUS_COLOR["Warning"]
    else:
        color = STATUS_COLOR["Critical"]

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={"suffix": "", "font": {"color": "#ffffff", "size": 40}},
        title={"text": title, "font": {"color": "#8a94a8", "size": 14}},
        gauge={
            "axis": {"range": [0, max_value], "tickcolor": "#8a94a8", "tickfont": {"color": "#8a94a8"}},
            "bar": {"color": color, "thickness": 0.28},
            "bgcolor": "rgba(255,255,255,0.04)",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 45], "color": "rgba(239,68,68,0.15)"},
                {"range": [45, 75], "color": "rgba(245,158,11,0.15)"},
                {"range": [75, 100], "color": "rgba(34,197,94,0.15)"},
            ],
        },
    ))
    fig.update_layout(height=height, margin=dict(l=20, r=20, t=50, b=10),
                       paper_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter", color="#ffffff"))
    return fig


def machine_card(machine, latest, health, on_click, key):
    color = STATUS_COLOR[health["status"]]
    with st.container(border=True):
        top = st.columns([1, 4])
        with top[0]:
            st.markdown(f"<div style='font-size:34px;'>{machine.get('icon','⚙️')}</div>", unsafe_allow_html=True)
        with top[1]:
            st.markdown(f"<div class='aw-card-title'>{machine['name']}</div>", unsafe_allow_html=True)
            st.markdown(status_badge_html(health["status"]), unsafe_allow_html=True)

        st.markdown(f"<div class='aw-kpi-value' style='font-size:26px; margin-top:8px;'>{health['score']}/100</div>",
                     unsafe_allow_html=True)
        st.progress(int(health["score"]))

        st.markdown(
            f"<div class='aw-muted' style='margin-top:6px; line-height:1.7;'>"
            f"🌡️ Air: {latest['air_temp']:.1f}K &nbsp; | &nbsp; 🔥 Process: {latest['process_temp']:.1f}K<br>"
            f"⚙️ RPM: {latest['rpm']:.0f} &nbsp; | &nbsp; 🔧 Torque: {latest.get('torque', 0):.0f} Nm<br>"
            f"🪛 Tool Wear: {latest.get('tool_wear', 0):.0f} min",
            unsafe_allow_html=True,
        )
        st.write("")
        st.button("View Full Report →", key=f"card_btn_{key}", on_click=on_click, args=(machine["id"],),
                   use_container_width=True)
