import streamlit as st

st.set_page_config(page_title="Aegis Watch — AI Machine Health Guardian", layout="wide",
                    initial_sidebar_state="expanded", page_icon="⚡")

from styles.theme import inject_theme
inject_theme()

from pages import home, machine_list, machine_detail, analytics, reports, alert_center, settings, live_monitoring
from utils.data_utils import COMPANY_NAME, AI_MODEL_VERSION

# ---------------------------------------------------------------
# Live backend -- sensor simulator + alert engine
# ---------------------------------------------------------------
# Both run as background daemon threads so they never block the UI.
# The session_state guard is important -- without it, Streamlit's
# rerun-on-interaction model would spawn a new thread on every click.
if "backend_started" not in st.session_state:
    from sensor_simulator import start_simulator_thread
    from alert_engine import start_alert_engine_thread

    start_simulator_thread()
    start_alert_engine_thread()
    st.session_state.backend_started = True

# ---------------------------------------------------------------
# Navigation state
# ---------------------------------------------------------------
if "page" not in st.session_state:
    st.session_state.page = "Home"
if "selected_machine" not in st.session_state:
    st.session_state.selected_machine = None


def go_to_detail(machine_id):
    st.session_state.selected_machine = machine_id
    st.session_state.page = "Machine Detail"


def go_to_machines_list():
    st.session_state.selected_machine = None
    st.session_state.page = "My Machines"


def nav(page_name):
    st.session_state.page = page_name
    st.session_state.selected_machine = None


# =================================================================
# SIDEBAR
# =================================================================
with st.sidebar:
    st.markdown("<div class='aw-logo'>⚡ AEGIS <span>WATCH</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='aw-muted' style='margin-bottom:18px;'>AI-Powered Machine Health Guardian</div>", unsafe_allow_html=True)

    nav_items = [
        ("🏠", "Home"),
        ("⚙️", "My Machines"),
        ("📊", "Analytics"),
        ("📄", "Reports"),
        ("🚨", "Alert Center"),
        ("📡", "Live Monitoring"),
        ("🔧", "Settings"),
    ]
    for icon, label in nav_items:
        active = st.session_state.page == label or (label == "My Machines" and st.session_state.page == "Machine Detail")
        btn_label = f"{icon}  {label}"
        if st.button(btn_label, key=f"nav_{label}", use_container_width=True,
                     type="primary" if active else "secondary"):
            nav(label)

    st.markdown("<hr class='aw-divider'>", unsafe_allow_html=True)
    st.markdown(f"<div class='aw-muted'>{COMPANY_NAME}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='aw-muted'>Model: {AI_MODEL_VERSION}</div>", unsafe_allow_html=True)


# =================================================================
# ROUTER
# =================================================================
page = st.session_state.page

if page == "Home":
    home.render()
elif page == "My Machines":
    machine_list.render(go_to_detail=go_to_detail)
elif page == "Machine Detail":
    if st.session_state.selected_machine:
        machine_detail.render(st.session_state.selected_machine, go_back=go_to_machines_list)
    else:
        machine_list.render(go_to_detail=go_to_detail)
elif page == "Analytics":
    analytics.render()
elif page == "Reports":
    reports.render()
elif page == "Alert Center":
    alert_center.render()
elif page == "Live Monitoring":
    live_monitoring.render()
elif page == "Settings":
    settings.render()

# ---------------------------------------------------------------
# Footer
# ---------------------------------------------------------------
st.markdown("""
<div class='aw-footer'>
    Developed by <b>Aegis Watch</b> — AI Powered Industrial Safety Platform &nbsp;·&nbsp; Version 1.0.0
</div>
""", unsafe_allow_html=True)
