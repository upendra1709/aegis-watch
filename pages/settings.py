import streamlit as st
from utils.data_utils import COMPANY_NAME, AI_MODEL_VERSION


def render():
    st.markdown("<div class='aw-title'>Settings</div>", unsafe_allow_html=True)
    st.markdown("<div class='aw-sub'>Application & AI configuration</div>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title'>General</div>", unsafe_allow_html=True)
            st.text_input("Company Name", value=COMPANY_NAME)
            st.selectbox("Language", ["English", "Hindi", "German", "French"])
            st.toggle("Dark Mode", value=True)
            st.selectbox("Theme", ["Aegis Dark (default)", "Midnight Blue", "Slate"])

        with st.container(border=True):
            st.markdown("<div class='aw-card-title'>Notification Settings</div>", unsafe_allow_html=True)
            st.toggle("Email notifications", value=True)
            st.toggle("SMS notifications (placeholder)", value=False)
            st.toggle("Voice alarm on Critical status", value=True)

    with c2:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title'>Threshold Settings</div>", unsafe_allow_html=True)
            st.slider("Warning threshold (health score)", 0, 100, 75)
            st.slider("Critical threshold (health score)", 0, 100, 45)
            st.slider("Temperature alert limit (°C)", 40, 150, 90)
            st.slider("Vibration alert limit", 0.0, 2.0, 0.6)

        with st.container(border=True):
            st.markdown("<div class='aw-card-title'>AI / System Status</div>", unsafe_allow_html=True)
            st.markdown(f"**AI Model Version:** {AI_MODEL_VERSION}")
            st.markdown("**Database Status:** 🟢 Connected (dataset: `data/ai4i2020_10k.csv`)")
            st.markdown("**Model Files:** `machine_failure_model.pkl` (XGBoost) + `failure_mode_model.pkl` (failure-mode classifier), loaded from the project root")

    if st.button("💾 Save Settings"):
        st.success("Settings saved (demo) — wire these controls to a persisted config file or DB.")
