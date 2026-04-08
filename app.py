import streamlit as st
import sys
import os

# Ensure app directory is on path — required for Streamlit Cloud
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="Finance Command Centre",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Inter:wght@300;400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

section[data-testid="stSidebar"] {
    background: #0f1117;
    border-right: 1px solid #1e2130;
}
section[data-testid="stSidebar"] * { color: #c9d1d9 !important; }
section[data-testid="stSidebar"] .stRadio label {
    padding: 6px 10px; border-radius: 6px; cursor: pointer;
}
section[data-testid="stSidebar"] .stRadio label:hover { background: #1e2130; }

[data-testid="metric-container"] {
    background: #0d1117;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 16px !important;
}
[data-testid="metric-container"] [data-testid="stMetricLabel"] {
    color: #8b949e !important; font-size: 12px !important; letter-spacing: 0.5px;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #e6edf3 !important; font-size: 22px !important; font-weight: 600;
    font-family: 'IBM Plex Mono', monospace;
}
[data-testid="metric-container"] [data-testid="stMetricDelta"] svg { display: none; }

[data-testid="stFileUploader"] {
    border: 1.5px dashed #30363d !important;
    border-radius: 10px;
    padding: 12px;
    background: #0d1117;
}

.stTabs [data-baseweb="tab-list"] { background: #0d1117; border-radius: 8px; padding: 4px; }
.stTabs [data-baseweb="tab"] { border-radius: 6px; color: #8b949e; font-weight: 500; }
.stTabs [aria-selected="true"] { background: #1f6feb !important; color: #fff !important; }

[data-testid="stDataFrame"] { border: 1px solid #21262d; border-radius: 8px; }
hr { border-color: #21262d !important; }
[data-testid="stExpander"] { border: 1px solid #21262d !important; border-radius: 8px; background: #0d1117; }

.section-header {
    font-size: 11px; font-weight: 600; letter-spacing: 1.5px;
    color: #8b949e; text-transform: uppercase; margin: 16px 0 8px;
}
.kpi-good { color: #3fb950; font-weight: 600; }
.kpi-warn { color: #d29922; font-weight: 600; }
.kpi-bad  { color: #f85149; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ── Session state init ─────────────────────────────────────────────────────
from state import init_state
init_state()

# ── Sidebar ────────────────────────────────────────────────────────────────
from sidebar import render_sidebar
render_sidebar()

# ── Page routing ───────────────────────────────────────────────────────────
page = st.session_state.get("page", "Overview")

if page == "Overview":
    from tabs import overview; overview.render()
elif page == "Inventory":
    from tabs import inventory; inventory.render()
elif page == "P&L":
    from tabs import pnl; pnl.render()
elif page == "Working Capital":
    from tabs import working_capital; working_capital.render()
elif page == "Receivables":
    from tabs import receivables; receivables.render()
elif page == "Supplier Performance":
    from tabs import supplier; supplier.render()
