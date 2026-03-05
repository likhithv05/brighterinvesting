"""
Brighter Investing — Form 990 Financial Analyzer
Main entry point: page config, auth gate, data orchestration, tab routing.

Developed by Epic Intentions for Brighter Investing
Georgia Institute of Technology — Spring 2026
"""

import os
import time as _time
import streamlit as st

from core.login import show_login_page

# ─── Page Config (MUST be first Streamlit command) ───
st.set_page_config(
    page_title="Brighter — Form 990 Analyzer", page_icon="✦",
    layout="wide", initial_sidebar_state="expanded",
)

# ─── Session State Defaults ───
# All keys in one block so there's a single source of truth.
_DEFAULTS = {
    # auth_* — authentication
    "auth_authenticated": False,
    "auth_user_id": None,
    "auth_username": None,
    "auth_display_name": None,
    "auth_role": None,
    # data_* — loaded data
    "data_selected_ein": None,
    "data_tag_filter_eins": None,
    "data_comparison_ein": None,
    # ui_* — UI state
    "ui_comparison_mode": False,
    # pp_* — ProPublica
    "pp_search_results": None,
    "pp_filings": None,
    "pp_selected_ein": None,
    "pp_loaded_rows": None,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ─── Auth Gate ───
if not st.session_state["auth_authenticated"]:
    if not show_login_page():
        st.stop()

# ─── Post-Auth Imports (deferred to speed up login page) ───
from core.db_utils import verify_session          # noqa: E402
from core.kpis import compute_kpis                # noqa: E402
from core.export import generate_workbook          # noqa: E402
from components.header import render_header, render_org_banner, render_footer, smart_title  # noqa: E402
from components.sidebar import render_sidebar      # noqa: E402
from components.data_filter import apply_filters   # noqa: E402
from components.empty_state import render_empty_state  # noqa: E402
from views import dashboard, trends, investments, statements, raw_data, compare, forecasting  # noqa: E402

# ─── Force Logout Check ───
# Verify the session every 30 seconds, not on every rerun.
_now = _time.time()
if _now - st.session_state.get("_last_session_check", 0) > 30:
    st.session_state["_last_session_check"] = _now
    _session = verify_session(st.session_state.get("auth_user_id"))
    if not _session["valid"]:
        _reason = _session["reason"]
        st.session_state.clear()
        for _k, _v in _DEFAULTS.items():
            st.session_state[_k] = _v
        st.session_state["_logout_reason"] = _reason
        st.rerun()

# ─── CSS & Font ───
@st.cache_data(show_spinner=False)
def _read_css():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "styles", "main.css")
    if os.path.isfile(p):
        with open(p) as f:
            return f.read()
    return ""

_css = _read_css()
if _css:
    st.markdown(f"<style>\n{_css}\n</style>", unsafe_allow_html=True)
st.markdown(
    '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">',
    unsafe_allow_html=True,
)

# ─── Header + Sidebar ───
render_header()
all_parsed_rows, parse_errors = render_sidebar()

# ─── Filtering ───
parsed_rows, ein_map = apply_filters(all_parsed_rows, parse_errors)

if not parsed_rows:
    render_empty_state()
    st.stop()

# ─── Compute KPIs ───
with st.spinner("Analyzing financial data…"):
    kpi_data = []
    for row in parsed_rows:
        kpis = compute_kpis(row)
        kpis["TaxYear"] = row.get("TaxYear", "")
        kpis["OrganizationName"] = row.get("OrganizationName", "")
        kpi_data.append(kpis)

    latest = parsed_rows[-1]
    latest_kpis = compute_kpis(latest)
    org_name = smart_title(latest.get("OrganizationName", "Unknown Organization"))
    latest_year = latest.get("TaxYear", "")

# ─── Zero-activity warning ───
if latest.get("TotalRevenue", 0) == 0 and latest.get("TotalExpenses", 0) == 0:
    st.warning(
        "This filing reports **zero financial activity** (zero revenue and zero expenses). "
        "The data may be incomplete or this may be a partial/amended return."
    )

# ─── Banner + Export ───
render_org_banner(parsed_rows, latest, st.session_state.get("auth_user_id"))
@st.cache_data(show_spinner=False)
def _cached_workbook(rows):
    return generate_workbook(rows)

# Download button in sidebar
with st.sidebar:
    with st.spinner("Preparing Excel report…"):
        wb_bytes = _cached_workbook(parsed_rows)
    safe = org_name.replace(" ", "_").replace("/", "_")[:30]
    st.download_button("⬇ Download Excel Report", data=wb_bytes,
                       file_name=f"{safe}_Form990_Analysis.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True)

# ─── Tab Routing ───
tab_names = ["Dashboard", "Trends", "Investment Detail", "Financial Statements",
             "Raw Data", "Forecasting"]
if st.session_state.get("ui_comparison_mode") and st.session_state.get("data_comparison_ein"):
    tab_names.append("Compare")

tabs = st.tabs(tab_names)

def _safe_render(tab_idx, label, fn, *args):
    """Render a page tab with error handling."""
    with tabs[tab_idx]:
        try:
            fn(*args)
        except Exception as exc:
            st.error(
                f"Something went wrong while rendering **{label}**. "
                f"This may be caused by unexpected data in the uploaded files. "
                f"Try re-uploading or selecting a different organization."
            )
            st.caption(f"Technical detail: {exc}")

_safe_render(0, "Dashboard", dashboard.render, parsed_rows, latest_kpis, latest_year)
_safe_render(1, "Trends", trends.render, parsed_rows, kpi_data)
_safe_render(2, "Investment Detail", investments.render, parsed_rows, latest_kpis, latest_year)
_safe_render(3, "Financial Statements", statements.render, parsed_rows)
_safe_render(4, "Raw Data", raw_data.render, parsed_rows)
_safe_render(5, "Forecasting", forecasting.render, parsed_rows)
if len(tabs) > 6:
    _safe_render(6, "Compare", compare.render, parsed_rows, latest_kpis, org_name, latest_year, ein_map)

render_footer()
