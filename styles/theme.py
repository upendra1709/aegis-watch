"""
THEME / GLOBAL CSS
===================
Injects the dark-blue + orange glassmorphism theme used across every page.
Call inject_theme() once at the top of app.py (before rendering anything else).
"""

import streamlit as st

PRIMARY_BG = "#0b1220"
CARD_BG = "rgba(255,255,255,0.04)"
ACCENT_ORANGE = "#f97316"
ACCENT_BLUE = "#3b82f6"
STATUS_COLOR = {"Healthy": "#22c55e", "Warning": "#f59e0b", "Critical": "#ef4444"}


def inject_theme():
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}

    .stApp {{
        background: radial-gradient(circle at 10% 0%, #10192f 0%, #0b1220 55%, #070c17 100%);
        color: #e5e9f2;
    }}

    section[data-testid="stSidebar"] {{
        background: linear-gradient(180deg, #0e1526 0%, #0a0f1c 100%);
        border-right: 1px solid rgba(255,255,255,0.06);
    }}
    section[data-testid="stSidebar"] * {{ color: #cbd5e1 !important; }}

    div[data-testid="stVerticalBlockBorderWrapper"] {{
        background: {CARD_BG};
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        border-radius: 18px;
        border: 1px solid rgba(255,255,255,0.08) !important;
        box-shadow: 0 8px 28px rgba(0,0,0,0.35);
    }}

    .aw-title {{ font-size: 30px; font-weight: 900; color: #ffffff; margin-bottom: 2px; letter-spacing: -0.5px;}}
    .aw-sub {{ color: #8a94a8; font-size: 14px; margin-bottom: 22px; }}
    .aw-badge {{
        display: inline-block; padding: 4px 14px; border-radius: 20px;
        font-size: 12.5px; font-weight: 700; letter-spacing: 0.3px;
    }}
    .aw-kpi-label {{ font-size: 13px; color: #8a94a8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.6px;}}
    .aw-kpi-value {{ font-size: 32px; font-weight: 900; color: #ffffff; }}
    .aw-kpi-icon {{ font-size: 22px; }}
    .aw-card-title {{ font-size: 16px; font-weight: 800; color: #ffffff; letter-spacing: 0.2px;}}
    .aw-muted {{ color: #8a94a8; font-size: 12.5px; }}
    .aw-divider {{ border: none; border-top: 1px solid rgba(255,255,255,0.08); margin: 10px 0 20px 0; }}
    .aw-logo {{ font-size: 21px; font-weight: 900; color: #ffffff; letter-spacing: -0.5px;}}
    .aw-logo span {{ color: {ACCENT_ORANGE}; }}
    .aw-footer {{ text-align:center; color:#5b6472; font-size:12px; padding: 30px 0 10px 0; }}

    div.stButton > button {{
        border-radius: 10px; border: 1px solid rgba(249,115,22,0.4);
        background: linear-gradient(135deg, {ACCENT_ORANGE}, #ea580c);
        color: white; font-weight: 700; padding: 0.55rem 1rem;
        box-shadow: 0 4px 14px rgba(249,115,22,0.25);
    }}
    div.stButton > button:hover {{ filter: brightness(1.08); color: white; }}
    .aw-secondary-btn button {{
        background: rgba(255,255,255,0.06) !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        box-shadow: none !important; color: #cbd5e1 !important;
    }}

    [data-testid="stMetric"] {{ background: transparent; }}
    [data-testid="stMetricValue"] {{ color: #ffffff; }}

    thead tr th {{ background-color: rgba(255,255,255,0.05) !important; color: #cbd5e1 !important; }}
    tbody tr td {{ color: #dbe2ee !important; }}
    </style>
    """, unsafe_allow_html=True)


def status_badge_html(status: str) -> str:
    color = STATUS_COLOR.get(status, "#9aa2b1")
    bg = color + "26"  # translucent
    return f"<span class='aw-badge' style='background:{bg}; color:{color}; border:1px solid {color}55;'>{status}</span>"
