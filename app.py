"""
Brighter Investing — Form 990 Financial Analyzer
Main entry point: page config, auth gate, data orchestration, tab routing.

Developed by Epic Intentions for Brighter Investing
Georgia Institute of Technology — Spring 2026
"""

import os
import streamlit as st

from core.login import show_login_page
from core.kpis import compute_kpis
from core.export import generate_workbook

from components.header import render_header, render_org_banner, render_footer
from components.sidebar import render_sidebar
from components.data_filter import apply_filters
from components.empty_state import render_empty_state

from pages import dashboard, trends, investments, statements, raw_data, compare, forecasting

# ─── Page Config (MUST be first Streamlit command) ───
st.set_page_config(
    page_title="Brighter — Form 990 Analyzer", page_icon="✦",
    layout="wide", initial_sidebar_state="expanded",
)

# ─── Session State Defaults ───
_DEFAULTS = {
    "authenticated": False, "username": None, "role": None, "user_id": None,
    "selected_ein": None, "selected_org_name": None,
    "year_filter_mode": "All Years", "selected_year": None, "year_range": None,
    "comparison_mode": False, "comparison_ein": None, "show_admin": False,
    "tag_filter_eins": None, "propublica_results": None,
    "propublica_filings": None, "propublica_selected_ein": None,
    "pp_loaded_rows": None, "pp_loaded_org_name": None,
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── Auth Gate ───
if not st.session_state["authenticated"]:
    show_login_page()
    st.stop()

# ─── CSS & Font ───
_css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "styles", "main.css")
if os.path.isfile(_css_path):
    with open(_css_path) as _f:
        st.markdown(f"<style>{_f.read()}</style>", unsafe_allow_html=True)
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
kpi_data = []
for row in parsed_rows:
    kpis = compute_kpis(row)
    kpis["TaxYear"] = row.get("TaxYear", "")
    kpis["OrganizationName"] = row.get("OrganizationName", "")
    kpi_data.append(kpis)

latest = parsed_rows[-1]
latest_kpis = compute_kpis(latest)
org_name = latest.get("OrganizationName", "Unknown Organization")
latest_year = latest.get("TaxYear", "")

# ─── Banner + Export ───
render_org_banner(parsed_rows, latest, st.session_state.get("user_id"))
c1, _ = st.columns([1, 4])
with c1:
    wb_bytes = generate_workbook(parsed_rows)
    safe = org_name.replace(" ", "_").replace("/", "_")[:30]
    st.download_button("⬇ Download Excel Report", data=wb_bytes,
                       file_name=f"{safe}_Form990_Analysis.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True)

# ─── Tab Routing ───
tab_names = ["Dashboard", "Trends", "Investment Detail", "Financial Statements",
             "Raw Data", "Forecasting"]
if st.session_state.get("comparison_mode") and st.session_state.get("comparison_ein"):
    tab_names.append("Compare")

tabs = st.tabs(tab_names)
with tabs[0]: dashboard.render(parsed_rows, latest_kpis, latest_year)
with tabs[1]: trends.render(parsed_rows, kpi_data)
with tabs[2]: investments.render(parsed_rows, latest_kpis, latest_year)
with tabs[3]: statements.render(parsed_rows)
with tabs[4]: raw_data.render(parsed_rows)
with tabs[5]: forecasting.render(parsed_rows)
if len(tabs) > 6:
    with tabs[6]: compare.render(parsed_rows, latest_kpis, org_name, latest_year, ein_map)

render_footer()
