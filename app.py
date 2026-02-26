"""
Brighter Investing — Form 990 Financial Analyzer
A Streamlit web application for nonprofit financial analysis.

Upload IRS Form 990 XML filings to instantly extract financial data,
view interactive dashboards, and download formatted Excel reports.

Developed by Epic Intentions for Brighter Investing
Georgia Institute of Technology — Spring 2026
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import sys
import base64

from login import show_login_page, show_admin_panel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parser import parse_single_xml, FIELD_LABELS, FIELD_GROUPS
from kpis import (
    compute_kpis, KPI_DEFINITIONS, PRIMARY_KPIS, TREND_KPIS,
    INVESTMENT_KPIS, format_kpi_value, get_kpi_status,
)
from export import generate_workbook
from db_utils import (
    init_extended_db,
    get_user_id,
    save_organization,
    load_user_organizations,
    delete_organization,
    detect_duplicates,
    clear_remember_me_token,
    create_tag,
    get_user_tags,
    delete_tag,
    assign_tag,
    remove_tag_from_org,
    get_tags_for_org,
    get_orgs_by_tag,
    TAG_COLORS,
)
from propublica import (
    search_nonprofits,
    get_organization_filings,
    fetch_filing_xml,
    format_filing_year,
    format_revenue,
)


# ─── Page Config (MUST be first Streamlit command) ───
st.set_page_config(
    page_title="Brighter — Form 990 Analyzer",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ─── Session State Defaults ───
_DEFAULTS = {
    "authenticated": False,
    "username": None,
    "role": None,
    "user_id": None,
    "selected_ein": None,
    "selected_org_name": None,
    "year_filter_mode": "All Years",
    "selected_year": None,
    "year_range": None,
    "comparison_mode": False,
    "comparison_ein": None,
    "show_admin": False,
    "tag_filter_eins": None,
    "propublica_results": None,
    "propublica_filings": None,
    "propublica_selected_ein": None,
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ─── AUTH GATE ───
if not st.session_state["authenticated"]:
    show_login_page()
    st.stop()


# ─── Design Tokens — Professional Navy + Teal ───
NAVY = "#0F172A"
NAVY_MID = "#1E293B"
SLATE = "#334155"
TEAL = "#0D9488"
TEAL_LT = "#14B8A6"
TEAL_BG = "#F0FDFA"
EMERALD = "#059669"
SKY = "#0284C7"
AMBER = "#D97706"
ROSE = "#E11D48"
PAL = [TEAL, SKY, AMBER, ROSE, "#7C3AED", "#0891B2"]


@st.cache_data
def _logo_b64():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.svg")
    if os.path.isfile(p):
        with open(p, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""


# ─── Font via <link> tag (NOT @import inside <style>) ───
st.markdown(
    '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">',
    unsafe_allow_html=True,
)


# ─── CSS — Professional redesign ───
st.markdown("""<style>
/* ── Safe Streamlit overrides ── */
[data-testid="stDecoration"] { display: none; }
[data-testid="stAppDeployButton"] { display: none; }

[data-testid="stAppViewContainer"],
[data-testid="stApp"],
.main, .main .block-container {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}
.main .block-container {
    padding: 1.5rem 2.5rem 4rem !important;
    max-width: 1200px !important;
}
section[data-testid="stSidebar"] {
    background: #F8FAFC !important;
    border-right: 1px solid #E2E8F0 !important;
}
section[data-testid="stSidebar"] > div:first-child {
    padding-top: 1.25rem !important;
}
section[data-testid="stSidebar"] [data-testid="stMarkdown"] p {
    font-size: .8rem; color: #64748B; line-height: 1.6;
}
section[data-testid="stSidebar"] .stCheckbox label span {
    font-size: .82rem !important;
}

/* Tabs — pill / segmented control */
.stTabs [data-baseweb="tab-list"] {
    gap: 2px; background: #fff; border: 1px solid #E2E8F0;
    border-radius: 10px; padding: 4px; width: fit-content;
    margin-bottom: 1.25rem;
}
.stTabs [data-baseweb="tab"] {
    padding: .5rem 1.1rem; border-radius: 7px; font-size: .8rem;
    font-weight: 500; color: #64748B; border-bottom: none !important;
    white-space: nowrap;
}
.stTabs [data-baseweb="tab"]:hover { color: #0F172A; background: #F1F5F9; }
.stTabs [aria-selected="true"] {
    color: #0F172A !important; background: #F1F5F9 !important;
    font-weight: 600 !important; box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] { display: none !important; }

/* Download button */
.stDownloadButton > button {
    background: #0F172A !important; color: #fff !important;
    border: none !important; font-weight: 600 !important;
    font-size: .8rem !important; padding: .6rem 1.4rem !important;
    border-radius: 10px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,.04) !important;
}
.stDownloadButton > button:hover {
    opacity: .88 !important;
    box-shadow: 0 4px 14px rgba(0,0,0,.06) !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 3px; }


/* ═══════════════════════════════════════
   CUSTOM COMPONENT STYLES (class-scoped)
   ═══════════════════════════════════════ */

/* Header */
.bi-hdr {
    display: flex; align-items: center; gap: 18px;
    padding: 8px 0 24px; margin-bottom: 0;
}
.bi-hdr img { height: 54px; }
.bi-hdr .pipe { width: 1.5px; height: 36px; background: linear-gradient(180deg, #0D9488, #059669); border-radius: 2px; }
.bi-hdr .tool-name {
    font-size: .82rem; font-weight: 600; color: #475569;
    letter-spacing: .01em; text-transform: uppercase; line-height: 1.4;
}
.bi-hdr .tool-sub {
    font-size: .68rem; font-weight: 400; color: #94A3B8;
    letter-spacing: .005em; margin-top: 1px;
}
.hdr-bar {
    height: 3px; border-radius: 3px; margin-bottom: 8px;
    background: linear-gradient(90deg, #0D9488 0%, #0284C7 60%, transparent 100%);
}

/* Org Banner */
.org-ban {
    background: #fff; border: 1px solid #E2E8F0;
    border-radius: 16px; overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,.04); margin: 20px 0 16px;
}
.org-ban .accent-bar {
    height: 4px;
    background: linear-gradient(90deg, #0D9488 0%, #0284C7 100%);
}
.org-ban .inner {
    display: flex; align-items: center; justify-content: space-between;
    flex-wrap: wrap; gap: 12px; padding: 20px 24px 18px;
}
.org-ban h2 {
    font-family: 'Inter', sans-serif;
    font-size: 1.5rem; font-weight: 800; color: #0F172A;
    letter-spacing: -.04em; margin: 0 0 6px; line-height: 1.15;
}
.org-ban .meta { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.org-ban .meta span { font-size: .78rem; color: #64748B; }
.org-ban .meta .dot { color: #CBD5E1; font-size: .4rem; }
.yr-badge {
    display: inline-flex; align-items: center; gap: 5px;
    background: #F0FDFA; color: #0D9488;
    border: 1px solid rgba(13,148,136,.2);
    padding: 6px 14px; border-radius: 100px;
    font-size: .72rem; font-weight: 600;
}

/* Section Headings */
.sec-t {
    font-family: 'Inter', sans-serif; font-size: 1.08rem;
    font-weight: 700; color: #0F172A; letter-spacing: -.02em;
    margin: 32px 0 4px;
}
.sec-s {
    font-size: .78rem; color: #64748B; margin: 0 0 16px;
    font-weight: 400; line-height: 1.55;
}

/* KPI Grid */
.kpi-grid {
    display: grid; grid-template-columns: repeat(3, 1fr);
    gap: 10px; margin-bottom: 12px;
}
@media(max-width:900px) { .kpi-grid { grid-template-columns: repeat(2,1fr); } }
@media(max-width:560px) { .kpi-grid { grid-template-columns: 1fr; } }

/* KPI Card */
.kpi-c {
    background: #fff; border: 1px solid #E2E8F0;
    border-radius: 16px; padding: 20px 22px 18px;
    box-shadow: 0 1px 3px rgba(0,0,0,.04);
    transition: box-shadow .2s, transform .2s;
    animation: kfIn .35s ease both;
}
.kpi-c:hover { box-shadow: 0 4px 14px rgba(0,0,0,.06); transform: translateY(-2px); }
.kpi-c:nth-child(2) { animation-delay: 40ms; }
.kpi-c:nth-child(3) { animation-delay: 80ms; }
.kpi-c:nth-child(4) { animation-delay: 120ms; }
.kpi-c:nth-child(5) { animation-delay: 160ms; }
.kpi-c:nth-child(6) { animation-delay: 200ms; }
.kpi-c .kpi-top {
    display: flex; align-items: flex-start;
    justify-content: space-between; margin-bottom: 10px;
}
.kpi-c .kpi-lbl {
    font-size: .66rem; font-weight: 600; color: #64748B;
    text-transform: uppercase; letter-spacing: .07em;
    line-height: 1.35; max-width: 65%;
}
.kpi-c .bdg {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 2px 10px; border-radius: 100px;
    font-size: .56rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: .05em; flex-shrink: 0;
}
.kpi-c .bdg .dt { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
.bdg-g { background: #ECFDF5; color: #059669; }
.bdg-g .dt { background: #059669; }
.bdg-w { background: #FFFBEB; color: #D97706; }
.bdg-w .dt { background: #D97706; }
.bdg-b { background: #FFF1F2; color: #E11D48; }
.bdg-b .dt { background: #E11D48; }
.bdg-n { background: #F1F5F9; color: #64748B; }
.bdg-n .dt { background: #64748B; }
.kpi-c .kpi-val {
    font-family: 'Inter', sans-serif;
    font-size: 1.75rem; font-weight: 700; color: #0F172A;
    letter-spacing: -.03em; line-height: 1.1; margin-bottom: 8px;
    font-variant-numeric: tabular-nums;
}
.kpi-c .kpi-bm { font-size: .66rem; color: #94A3B8; line-height: 1.5; }

/* Financial Tables */
.fin-tbl {
    background: #fff; border: 1px solid #E2E8F0;
    border-radius: 16px; overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,.04); margin-bottom: 20px;
}
.fin-tbl .fin-hdr {
    padding: 14px 20px; border-bottom: 1px solid #E2E8F0;
    font-size: .875rem; font-weight: 600; color: #0F172A;
}
.fin-tbl table {
    width: 100%; border-collapse: collapse; font-size: .75rem;
}
.fin-tbl thead tr { background: #F8FAFC; }
.fin-tbl th {
    text-align: right; padding: 10px 16px;
    font-weight: 600; color: #64748B; font-size: .72rem;
}
.fin-tbl th:first-child { text-align: left; }
.fin-tbl td { padding: 8px 16px; color: #334155; }
.fin-tbl td:first-child { font-weight: 500; color: #0F172A; }
.fin-tbl td.num {
    text-align: right; font-variant-numeric: tabular-nums;
}
.fin-tbl tbody tr:nth-child(even) { background: rgba(0,0,0,.015); }

/* Empty State */
.es-wrap {
    text-align: center; padding: 48px 24px 40px;
    max-width: 760px; margin: 0 auto;
}
.es-hero {
    background: #fff; border: 1px solid #E2E8F0; border-radius: 20px;
    padding: 52px 40px 44px; margin-bottom: 20px; position: relative;
    overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,.03);
}
.es-hero::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 4px;
    background: linear-gradient(90deg, #0D9488 0%, #0284C7 100%);
}
.es-hero::after {
    content: ''; position: absolute; top: -60px; right: -60px;
    width: 200px; height: 200px; border-radius: 50%; opacity: .04;
    background: radial-gradient(circle, #0D9488, transparent 70%);
}
.es-badge {
    display: inline-flex; align-items: center; gap: 6px;
    background: #F0FDFA; color: #0D9488;
    border: 1px solid rgba(13,148,136,.15); padding: 6px 16px;
    border-radius: 100px; font-size: .7rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: .06em; margin-bottom: 20px;
}
.es-badge svg { width: 14px; height: 14px; }
.es-title {
    font-family: 'Inter', sans-serif; font-size: 2rem;
    font-weight: 800; color: #0F172A; letter-spacing: -.04em;
    margin: 0 0 10px; line-height: 1.15;
}
.es-title span { color: #0D9488; }
.es-desc {
    font-size: .92rem; color: #475569; line-height: 1.7;
    max-width: 480px; margin: 0 auto;
}
.es-grid {
    display: grid; grid-template-columns: repeat(3,1fr);
    gap: 14px; text-align: left;
}
@media(max-width:640px) { .es-grid { grid-template-columns: 1fr; } }
.es-cd {
    background: #fff; border: 1px solid #E2E8F0;
    border-radius: 16px; padding: 24px 22px;
    box-shadow: 0 1px 3px rgba(0,0,0,.04);
    transition: box-shadow .25s, transform .25s;
    animation: kfIn .4s ease both;
}
.es-cd:nth-child(2) { animation-delay: 60ms; }
.es-cd:nth-child(3) { animation-delay: 120ms; }
.es-cd:hover { box-shadow: 0 6px 20px rgba(0,0,0,.06); transform: translateY(-3px); }
.es-cd .es-icon {
    width: 40px; height: 40px; border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    margin-bottom: 14px;
}
.es-cd .es-icon svg { width: 20px; height: 20px; }
.es-cd .es-icon.teal { background: rgba(13,148,136,.1); }
.es-cd .es-icon.teal svg { stroke: #0D9488; }
.es-cd .es-icon.indigo { background: rgba(2,132,199,.1); }
.es-cd .es-icon.indigo svg { stroke: #0284C7; }
.es-cd .es-icon.amber { background: rgba(217,119,6,.1); }
.es-cd .es-icon.amber svg { stroke: #D97706; }
.es-cd .es-t { font-size: .88rem; font-weight: 600; color: #0F172A; margin-bottom: 5px; }
.es-cd .es-d { font-size: .78rem; color: #64748B; line-height: 1.55; }
.es-hint {
    margin-top: 22px; font-size: .75rem; color: #94A3B8; line-height: 1.7;
}
.es-hint b { color: #64748B; font-weight: 600; }

/* Sidebar */
.sb-brand {
    display: flex; align-items: center; gap: 10px;
    padding: 4px 0 18px; margin-bottom: 18px;
    border-bottom: 1px solid #E2E8F0;
}
.sb-brand img { height: 32px; }
.sb-brand .sb-lbl {
    font-size: .62rem; font-weight: 600; color: #64748B;
    text-transform: uppercase; letter-spacing: .08em;
}
.sb-section-title {
    font-family: 'Inter', sans-serif; font-size: .82rem;
    font-weight: 700; color: #0F172A; letter-spacing: -.01em;
    margin: 0 0 6px; padding: 0;
}
.sb-section-desc {
    font-size: .76rem !important; color: #64748B !important; line-height: 1.55 !important;
    margin-bottom: 12px !important;
}

/* Redesigned upload zone */
.sb-upload-zone {
    background: linear-gradient(135deg, #F0FDFA 0%, #F0F9FF 100%);
    border: 2px dashed #99F6E4; border-radius: 14px;
    padding: 20px 16px; margin-bottom: 16px; text-align: center;
    transition: border-color .2s, background .2s;
}
.sb-upload-zone:hover { border-color: #0D9488; background: linear-gradient(135deg, #ECFDF5 0%, #E0F2FE 100%); }
.sb-upload-icon {
    width: 44px; height: 44px; border-radius: 12px; margin: 0 auto 10px;
    background: #fff; border: 1px solid #E2E8F0;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.sb-upload-icon svg { width: 22px; height: 22px; stroke: #0D9488; }
.sb-upload-title { font-size: .82rem; font-weight: 600; color: #0F172A; margin-bottom: 4px; }
.sb-upload-sub { font-size: .7rem; color: #94A3B8; line-height: 1.5; }

.sb-or {
    display: flex; align-items: center; gap: 10px;
    margin: 14px 0; font-size: .7rem; color: #94A3B8; font-weight: 500;
}
.sb-or::before, .sb-or::after {
    content: ''; flex: 1; height: 1px; background: #E2E8F0;
}

/* ProPublica search result cards */
.pp-card {
    background: #fff; border: 1px solid #E2E8F0; border-radius: 12px;
    padding: 14px 16px; margin-bottom: 8px;
    transition: border-color .2s, box-shadow .2s;
}
.pp-card:hover { border-color: #0D9488; box-shadow: 0 2px 8px rgba(13,148,136,.08); }
.pp-name { font-size: .82rem; font-weight: 600; color: #0F172A; margin-bottom: 3px; }
.pp-meta { font-size: .7rem; color: #64748B; line-height: 1.5; }
.pp-meta span { margin-right: 10px; }

.sb-credits {
    text-align: center; font-size: .66rem; line-height: 2;
    color: #94A3B8; padding: 12px 0 4px;
    border-top: 1px solid #F1F5F9; margin-top: 20px;
}
.sb-credits b { color: #64748B; font-weight: 600; }

/* Comparison cards */
.comp-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;
}
.comp-hdr {
    font-family: 'Inter', sans-serif; font-size: .92rem;
    font-weight: 700; color: #0F172A; margin-bottom: 8px;
    padding-bottom: 8px; border-bottom: 2px solid #E2E8F0;
}
.comp-hdr.org-a { border-color: #0D9488; }
.comp-hdr.org-b { border-color: #0284C7; }
.comp-delta {
    font-size: .68rem; font-weight: 600; padding: 2px 8px;
    border-radius: 100px; display: inline-block; margin-left: 6px;
}
.comp-delta.positive { background: #ECFDF5; color: #059669; }
.comp-delta.negative { background: #FFF1F2; color: #E11D48; }
.comp-delta.neutral { background: #F1F5F9; color: #64748B; }

/* Footer */
.bi-ft {
    text-align: center; padding: 40px 0 16px; color: #94A3B8;
    font-size: .72rem; border-top: 1px solid #F1F5F9;
    margin-top: 48px; line-height: 2;
}
.bi-ft b { color: #64748B; font-weight: 600; }

/* QuickBooks section */
.qb-banner {
    background: linear-gradient(135deg, #F0FDF4 0%, #ECFDF5 100%);
    border: 1px solid #BBF7D0; border-radius: 12px;
    padding: 16px; margin: 12px 0; text-align: center;
}
.qb-banner .qb-title { font-size: .78rem; font-weight: 600; color: #166534; margin-bottom: 4px; }
.qb-banner .qb-desc { font-size: .68rem; color: #4ADE80; }

/* Tag badges */
.tag-badge {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 3px 10px; border-radius: 100px;
    font-size: .62rem; font-weight: 600;
    letter-spacing: .03em; white-space: nowrap;
    transition: opacity .2s;
}
.tag-badge:hover { opacity: .85; }
.tag-row {
    display: flex; flex-wrap: wrap; gap: 6px;
    margin: 6px 0 10px;
}
.tag-manage-card {
    background: #fff; border: 1px solid #E2E8F0; border-radius: 12px;
    padding: 16px 18px; margin-bottom: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.tag-manage-card .tag-card-title {
    font-size: .82rem; font-weight: 600; color: #0F172A; margin-bottom: 8px;
}

@keyframes kfIn {
    from { opacity: 0; transform: translateY(6px); }
    to   { opacity: 1; transform: translateY(0); }
}
</style>""", unsafe_allow_html=True)


# ─── Helpers ───
_CF = dict(family="Inter, -apple-system, sans-serif", size=12, color="#64748B")

def _th(fig, h=420):
    """Apply chart theme to a Plotly figure."""
    fig.update_layout(
        plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
        font=_CF, margin=dict(l=50, r=30, t=40, b=40), height=h,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            font=dict(size=11, color="#475569"), bgcolor="rgba(0,0,0,0)",
        ),
        hoverlabel=dict(
            bgcolor="#fff", bordercolor="#E2E8F0",
            font=dict(size=12, color="#0F172A", family="Inter"),
        ),
    )
    for ax in [fig.update_xaxes, fig.update_yaxes]:
        ax(gridcolor="#F1F5F9", griddash="dot", linecolor="#E2E8F0",
           linewidth=1, tickfont=dict(size=11, color="#64748B"),
           title_font=dict(size=12, color="#475569"))
    return fig


def _sec(title, sub):
    """Section heading HTML."""
    return f'<div class="sec-t">{title}</div><div class="sec-s">{sub}</div>'


_ST = {"good": ("Healthy", "g"), "warning": ("Watch", "w"), "concern": ("At Risk", "b")}

def _kpi_html(keys, kpis_dict):
    """Generate KPI card grid HTML."""
    h = '<div class="kpi-grid">'
    for k in keys:
        d = KPI_DEFINITIONS.get(k, {})
        v = kpis_dict.get(k, 0)
        fv = format_kpi_value(k, v)
        s = get_kpi_status(k, v)
        lbl, cls = _ST.get(s, ("—", "n"))
        h += f"""<div class="kpi-c">
          <div class="kpi-top">
            <span class="kpi-lbl">{d.get('label', k)}</span>
            <span class="bdg bdg-{cls}"><span class="dt"></span>{lbl}</span>
          </div>
          <div class="kpi-val">{fv}</div>
          <div class="kpi-bm">{d.get('benchmark', '')}</div>
        </div>"""
    h += "</div>"
    return h


def _fin_table(title, years, fields, data):
    """Generate a financial HTML table (rows=fields, cols=years)."""
    h = f'<div class="fin-tbl"><div class="fin-hdr">{title}</div>'
    h += '<div style="overflow-x:auto"><table><thead><tr>'
    h += '<th style="text-align:left">Field</th>'
    for yr in years:
        h += f"<th>{yr}</th>"
    h += "</tr></thead><tbody>"
    for f_def in fields:
        h += "<tr>"
        h += f'<td>{f_def["label"]}</td>'
        for row in data:
            v = row.get(f_def["key"], 0)
            if isinstance(v, (int, float)):
                fv = f"${v:,.0f}"
            else:
                fv = str(v)
            h += f'<td class="num">{fv}</td>'
        h += "</tr>"
    h += "</tbody></table></div></div>"
    return h


# ─── Header ───
logo_b64 = _logo_b64()
logo_tag = (
    f'<img src="data:image/svg+xml;base64,{logo_b64}" alt="Brighter Investing" />'
    if logo_b64
    else '<span style="font-size:1.4rem;font-weight:700;color:#0D9488;">Brighter</span>'
)
logo_tag_sm = (
    f'<img src="data:image/svg+xml;base64,{logo_b64}" alt="Brighter" style="height:28px;" />'
    if logo_b64
    else '<span style="font-size:.9rem;font-weight:700;color:#0D9488;">Brighter</span>'
)
st.markdown(f"""
<div class="bi-hdr">
    {logo_tag}
    <div class="pipe"></div>
    <div>
        <div class="tool-name">Form 990 Analyzer</div>
        <div class="tool-sub">Nonprofit Financial Intelligence</div>
    </div>
</div>
<div class="hdr-bar"></div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════
with st.sidebar:
    st.markdown(f"""
    <div class="sb-brand">
        {logo_tag_sm}
        <div class="sb-lbl">Analyzer</div>
    </div>
    """, unsafe_allow_html=True)

    # ── DATA SOURCE TABS ──
    data_tab = st.radio(
        "Data Source",
        ["Upload XML", "Search ProPublica", "QuickBooks"],
        horizontal=True,
        label_visibility="collapsed",
    )

    # ════════ UPLOAD XML ════════
    if data_tab == "Upload XML":
        st.markdown("""
        <div class="sb-upload-zone">
            <div class="sb-upload-icon">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/>
                </svg>
            </div>
            <div class="sb-upload-title">Upload Form 990 XMLs</div>
            <div class="sb-upload-sub">Drop files below or click to browse.<br>Supports multiple files from different organizations.</div>
        </div>
        """, unsafe_allow_html=True)

        uploaded_files = st.file_uploader(
            "Drop XML files here",
            type=["xml"],
            accept_multiple_files=True,
            label_visibility="collapsed",
            help="Select IRS Form 990 XML files. You can upload files from multiple different nonprofits at once.",
        )

        demo_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "Form 990 Parser", "Data Engineering 2.6.2026",
            "Final_Model_Files", "Habitat for Humanity Test Data",
        )
        demo_available = os.path.isdir(demo_dir)
        if demo_available:
            st.markdown('<div class="sb-or">or try a sample</div>', unsafe_allow_html=True)
            use_demo = st.checkbox(
                "Load demo data (Habitat for Humanity)",
                help="Load 9 years of Habitat for Humanity International Form 990 filings.",
            )
        else:
            use_demo = False

    # ════════ PROPUBLICA SEARCH ════════
    elif data_tab == "Search ProPublica":
        uploaded_files = []
        use_demo = False

        st.markdown('<div class="sb-section-title">Search Nonprofits</div>', unsafe_allow_html=True)
        st.markdown(
            '<p class="sb-section-desc">Search by organization name or EIN. '
            'Select years to load their Form 990 data directly.</p>',
            unsafe_allow_html=True,
        )

        pp_query = st.text_input(
            "Organization name or EIN",
            placeholder="e.g. Habitat for Humanity, 91-1914868",
            key="pp_search_input",
        )

        if st.button("Search", key="pp_search_btn", use_container_width=True, type="primary"):
            if pp_query.strip():
                with st.spinner("Searching ProPublica..."):
                    results = search_nonprofits(pp_query.strip())
                    st.session_state["propublica_results"] = results

        results = st.session_state.get("propublica_results")
        if results and results.get("organizations"):
            orgs = results["organizations"]
            total = results.get("total_results", len(orgs))
            st.caption(f"Found {total:,} result{'s' if total != 1 else ''}")

            for org in orgs[:10]:
                name = org.get("name", "Unknown")
                ein_val = org.get("ein", "")
                city = org.get("city", "")
                state = org.get("state", "")
                revenue = org.get("income_amount")
                loc = f"{city}, {state}" if city and state else (city or state or "")

                st.markdown(f"""
                <div class="pp-card">
                    <div class="pp-name">{name}</div>
                    <div class="pp-meta">
                        <span>EIN: {ein_val}</span>
                        <span>{loc}</span>
                        {f'<span>Revenue: {format_revenue(revenue)}</span>' if revenue else ''}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if st.button(f"Select → {name[:30]}", key=f"pp_select_{ein_val}", use_container_width=True):
                    st.session_state["propublica_selected_ein"] = ein_val
                    with st.spinner(f"Loading filings for {name}..."):
                        filings_data = get_organization_filings(ein_val)
                        st.session_state["propublica_filings"] = filings_data
                    st.rerun()

        # Show filing year selection if we have filings
        filings_data = st.session_state.get("propublica_filings")
        selected_ein_pp = st.session_state.get("propublica_selected_ein")
        if filings_data and selected_ein_pp:
            org_info = filings_data.get("organization", {})
            filings = filings_data.get("filings_with_data", [])

            if filings:
                org_n = org_info.get("name", "Selected Organization")
                st.markdown(f'<div class="sb-section-title">{org_n}</div>', unsafe_allow_html=True)

                # Build year options from filings that have XML URLs
                year_options = []
                filing_map = {}
                for f in filings:
                    yr = format_filing_year(f)
                    xml_url = f.get("xml_url")
                    if xml_url and yr != "Unknown":
                        year_options.append(yr)
                        filing_map[yr] = f

                if year_options:
                    selected_years = st.multiselect(
                        "Select filing years to load",
                        year_options,
                        default=year_options[:3],
                        key="pp_year_select",
                    )

                    if st.button("Load Selected Filings", key="pp_load_filings", type="primary", use_container_width=True):
                        if selected_years:
                            with st.spinner(f"Downloading {len(selected_years)} filing(s)..."):
                                loaded_rows = []
                                errors = []
                                for yr in selected_years:
                                    f = filing_map.get(yr)
                                    if f and f.get("xml_url"):
                                        xml_bytes = fetch_filing_xml(f["xml_url"])
                                        if xml_bytes:
                                            try:
                                                row = parse_single_xml(xml_bytes, filename=f"ProPublica_{selected_ein_pp}_{yr}.xml")
                                                loaded_rows.append(row)
                                            except Exception as e:
                                                errors.append((yr, str(e)))
                                        else:
                                            errors.append((yr, "Failed to download XML"))

                                if loaded_rows:
                                    # Save to DB
                                    user_id = st.session_state.get("user_id")
                                    if user_id:
                                        save_organization(user_id, loaded_rows)
                                    st.session_state["pp_loaded_rows"] = loaded_rows
                                    st.success(f"Loaded {len(loaded_rows)} filing(s) successfully!")
                                    st.rerun()
                                if errors:
                                    for yr, err in errors:
                                        st.error(f"Year {yr}: {err}")
                else:
                    st.warning("No filings with XML data available for this organization.")
            else:
                st.warning("No filings found for this organization.")

    # ════════ QUICKBOOKS ════════
    elif data_tab == "QuickBooks":
        uploaded_files = []
        use_demo = False

        st.markdown("""
        <div class="qb-banner">
            <div class="qb-title">QuickBooks Integration</div>
            <div class="qb-desc">Coming Soon</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="sb-section-title">Connect QuickBooks</div>', unsafe_allow_html=True)
        st.markdown(
            '<p class="sb-section-desc">'
            'Import financial data directly from QuickBooks Online to compare '
            'against Form 990 filings and track real-time financials.</p>',
            unsafe_allow_html=True,
        )

        st.info(
            "QuickBooks integration is under development. "
            "This will allow you to connect your QuickBooks Online account "
            "and pull in real-time financial data for comparison with 990 filings."
        )

        st.markdown(
            "**Planned features:**\n"
            "- OAuth2 secure connection to QuickBooks Online\n"
            "- Import P&L, Balance Sheet, and Cash Flow statements\n"
            "- Side-by-side comparison with Form 990 data\n"
            "- Reconciliation tools for audit preparation"
        )

    # ── Saved Organizations Section ──
    user_id = st.session_state.get("user_id")
    saved_orgs = {}
    if user_id:
        saved_orgs = load_user_organizations(user_id)

    if saved_orgs:
        st.markdown('<div class="sb-or">saved organizations</div>', unsafe_allow_html=True)

        # Apply tag filter if active
        tag_filter_eins = st.session_state.get("tag_filter_eins")
        display_orgs = saved_orgs
        if tag_filter_eins:
            display_orgs = {k: v for k, v in saved_orgs.items() if k in tag_filter_eins}
            if not display_orgs:
                st.caption("No organizations match this category filter.")

        for s_ein, s_info in display_orgs.items():
            yrs = ", ".join(s_info["years"][-3:])
            if len(s_info["years"]) > 3:
                yrs = f"{s_info['years'][0]}–{s_info['years'][-1]}"

            # Show tag badges for this org
            if user_id:
                org_tags = get_tags_for_org(user_id, s_ein)
                if org_tags:
                    badges = ""
                    for ot in org_tags:
                        c = ot["tag_color"]
                        r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
                        bg = f"rgba({r},{g},{b},.12)"
                        badges += f'<span class="tag-badge" style="background:{bg};color:{c};font-size:.55rem;">{ot["tag_name"]}</span> '
                    st.markdown(f'<div style="margin:2px 0 -6px;">{badges}</div>', unsafe_allow_html=True)

            col_load, col_del = st.columns([3, 1])
            with col_load:
                if st.button(
                    f"📂 {s_info['name'][:25]} ({yrs})",
                    key=f"load_saved_{s_ein}",
                    use_container_width=True,
                ):
                    st.session_state["selected_ein"] = s_ein
                    st.session_state["selected_org_name"] = s_info["name"]
            with col_del:
                if st.button("🗑", key=f"del_saved_{s_ein}"):
                    delete_organization(user_id, s_ein)
                    st.rerun()

    # ── Tags / Categories Section ──
    if user_id and saved_orgs:
        st.markdown('<div class="sb-or">tags &amp; categories</div>', unsafe_allow_html=True)
        user_tags = get_user_tags(user_id)

        # Show existing tags
        if user_tags:
            tag_html = '<div class="tag-row">'
            for t in user_tags:
                color = t["tag_color"]
                # Compute light bg from color
                r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
                bg = f"rgba({r},{g},{b},.12)"
                tag_html += (
                    f'<span class="tag-badge" style="background:{bg};color:{color};">'
                    f'{t["tag_name"]}</span>'
                )
            tag_html += '</div>'
            st.markdown(tag_html, unsafe_allow_html=True)

            # Filter by tag
            tag_names = ["All Organizations"] + [t["tag_name"] for t in user_tags]
            filter_tag = st.selectbox(
                "Filter by category",
                tag_names,
                key="filter_tag_select",
                label_visibility="collapsed",
            )
            if filter_tag != "All Organizations":
                tag_obj = next((t for t in user_tags if t["tag_name"] == filter_tag), None)
                if tag_obj:
                    filtered_eins = get_orgs_by_tag(user_id, tag_obj["id"])
                    if filtered_eins:
                        st.session_state["tag_filter_eins"] = filtered_eins
                    else:
                        st.session_state["tag_filter_eins"] = None
                        st.caption("No organizations in this category yet.")
            else:
                st.session_state["tag_filter_eins"] = None

        # Create new tag
        with st.expander("Manage Tags"):
            new_tag_name = st.text_input(
                "New category name",
                placeholder="e.g. University Endowments",
                key="new_tag_input",
            )
            col_color, col_btn = st.columns([1, 1])
            with col_color:
                color_opts = {name: hex_c for hex_c, name in TAG_COLORS}
                sel_color_name = st.selectbox("Color", list(color_opts.keys()), key="new_tag_color")
                sel_color = color_opts[sel_color_name]
            with col_btn:
                st.write("")  # spacing
                if st.button("Add Tag", key="add_tag_btn", use_container_width=True):
                    if new_tag_name.strip():
                        result = create_tag(user_id, new_tag_name.strip(), sel_color)
                        if result:
                            st.success(f"Created '{new_tag_name.strip()}'")
                            st.rerun()
                        else:
                            st.error("Tag already exists.")

            # Delete tags
            if user_tags:
                del_tag = st.selectbox(
                    "Remove tag",
                    [t["tag_name"] for t in user_tags],
                    key="del_tag_select",
                )
                if st.button("Delete Tag", key="del_tag_btn"):
                    tag_obj = next((t for t in user_tags if t["tag_name"] == del_tag), None)
                    if tag_obj:
                        delete_tag(user_id, tag_obj["id"])
                        st.rerun()

            # Assign tags to orgs
            if user_tags and saved_orgs:
                st.markdown("---")
                st.caption("Assign tags to organizations")
                assign_ein = st.selectbox(
                    "Organization",
                    [f"{info['name']} ({ein})" for ein, info in saved_orgs.items()],
                    key="assign_org_select",
                )
                # Parse EIN from selection
                assign_ein_val = assign_ein.split("(")[-1].rstrip(")")
                current_tags = get_tags_for_org(user_id, assign_ein_val)
                current_tag_ids = {t["id"] for t in current_tags}

                available_tags = [t for t in user_tags if t["id"] not in current_tag_ids]
                if available_tags:
                    add_tag_sel = st.selectbox(
                        "Add tag",
                        [t["tag_name"] for t in available_tags],
                        key="assign_tag_select",
                    )
                    if st.button("Assign", key="assign_tag_btn"):
                        tag_obj = next((t for t in available_tags if t["tag_name"] == add_tag_sel), None)
                        if tag_obj:
                            assign_tag(user_id, assign_ein_val, tag_obj["id"])
                            st.rerun()

                if current_tags:
                    rm_tag_sel = st.selectbox(
                        "Remove tag from org",
                        [t["tag_name"] for t in current_tags],
                        key="remove_tag_select",
                    )
                    if st.button("Remove", key="remove_tag_btn"):
                        tag_obj = next((t for t in current_tags if t["tag_name"] == rm_tag_sel), None)
                        if tag_obj:
                            remove_tag_from_org(user_id, assign_ein_val, tag_obj["id"])
                            st.rerun()

    st.markdown(
        '<div class="sb-credits">'
        'Developed by <b>Epic Intentions</b><br>'
        "for Brighter Investing<br>"
        "Georgia Tech · Spring 2026"
        "</div>",
        unsafe_allow_html=True,
    )

    # ── Admin & Logout ──
    if st.session_state.get("role") == "admin":
        if st.button("⚙ Admin Panel", use_container_width=True):
            st.session_state["show_admin"] = not st.session_state.get("show_admin", False)
            st.rerun()

    if st.button("Logout", use_container_width=True):
        uid = st.session_state.get("user_id")
        if uid:
            clear_remember_me_token(uid)
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()


# ─── Admin Panel ───
if st.session_state.get("show_admin") and st.session_state.get("role") == "admin":
    show_admin_panel()
    st.markdown("---")


# ═══════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════
@st.cache_data
def load_demo(path):
    rows = []
    for fn in sorted(os.listdir(path)):
        if fn.lower().endswith(".xml"):
            with open(os.path.join(path, fn), "rb") as f:
                try:
                    rows.append(parse_single_xml(f.read(), filename=fn))
                except Exception:
                    pass
    return rows


def load_uploads(files):
    rows, errs = [], []
    for f in files:
        try:
            rows.append(parse_single_xml(f.read(), filename=f.name))
        except Exception as e:
            errs.append((f.name, str(e)))
    return rows, errs


# Load from uploads, ProPublica, demo, or saved
all_parsed_rows, parse_errors = [], []

if data_tab == "Upload XML" and uploaded_files:
    all_parsed_rows, parse_errors = load_uploads(uploaded_files)
    # Auto-save to DB
    if all_parsed_rows and user_id:
        save_organization(user_id, all_parsed_rows)
elif data_tab == "Upload XML" and use_demo and demo_available:
    all_parsed_rows = load_demo(demo_dir)
elif "pp_loaded_rows" in st.session_state and st.session_state["pp_loaded_rows"]:
    all_parsed_rows = st.session_state["pp_loaded_rows"]
elif st.session_state.get("selected_ein") and saved_orgs:
    s_ein = st.session_state["selected_ein"]
    if s_ein in saved_orgs:
        all_parsed_rows = saved_orgs[s_ein]["parsed_data"]

# Parse errors display
if parse_errors:
    with st.expander(f"⚠ {len(parse_errors)} file(s) could not be parsed"):
        for fn, err in parse_errors:
            st.error(f"**{fn}:** {err}")


# ═══════════════════════════════════════════════
# DUPLICATE DETECTION
# ═══════════════════════════════════════════════
if all_parsed_rows:
    duplicates = detect_duplicates(all_parsed_rows)
    if duplicates:
        with st.expander(f"⚠ {len(duplicates)} duplicate(s) detected — click to resolve"):
            for dup in duplicates:
                st.warning(
                    f"**{dup['ein']}** — Tax Year **{dup['year']}** "
                    f"appears in {len(dup['files'])} files: {', '.join(dup['files'])}"
                )
                cols = st.columns(len(dup["indices"]))
                for ci, idx in enumerate(dup["indices"]):
                    with cols[ci]:
                        if st.button(
                            f"Keep {dup['files'][ci]}",
                            key=f"dup_keep_{dup['ein']}_{dup['year']}_{ci}",
                        ):
                            remove_indices = [j for j in dup["indices"] if j != idx]
                            for ri in sorted(remove_indices, reverse=True):
                                if ri < len(all_parsed_rows):
                                    all_parsed_rows.pop(ri)
                            st.rerun()


# ═══════════════════════════════════════════════
# ORGANIZATION & YEAR FILTERING
# ═══════════════════════════════════════════════
if all_parsed_rows:
    # Group by EIN
    ein_map = {}
    for row in all_parsed_rows:
        ein = row.get("EIN", "unknown")
        if ein not in ein_map:
            ein_map[ein] = {
                "name": row.get("OrganizationName", "Unknown"),
                "rows": [],
            }
        ein_map[ein]["rows"].append(row)

    # Organization selector (only if multiple orgs)
    ein_list = list(ein_map.keys())
    selected_ein = ein_list[0]  # default

    if len(ein_list) > 1:
        st.info(f"📊 **{len(ein_list)} organizations detected** — Select which one to analyze below, or enable comparison mode.")
        org_options = {
            f"{info['name']} ({ein})": ein
            for ein, info in ein_map.items()
        }
        selected_label = st.selectbox(
            "Select Organization",
            list(org_options.keys()),
            help="Choose which organization to analyze. Upload files for multiple orgs to compare.",
        )
        selected_ein = org_options[selected_label]

        # Comparison mode
        st.session_state["comparison_mode"] = st.checkbox(
            "Compare with another organization",
            value=st.session_state.get("comparison_mode", False),
        )
        if st.session_state["comparison_mode"]:
            comp_options = {k: v for k, v in org_options.items() if v != selected_ein}
            if comp_options:
                comp_label = st.selectbox(
                    "Compare against",
                    list(comp_options.keys()),
                    key="comp_org_select",
                )
                st.session_state["comparison_ein"] = comp_options[comp_label]
            else:
                st.info("Upload files for a second organization to enable comparison.")
                st.session_state["comparison_mode"] = False

    st.session_state["selected_ein"] = selected_ein
    st.session_state["selected_org_name"] = ein_map[selected_ein]["name"]

    # Filter to selected org
    org_rows = ein_map[selected_ein]["rows"]
    org_rows = sorted(org_rows, key=lambda r: r.get("TaxYear", ""))

    # Year filtering
    available_years = sorted(set(r.get("TaxYear", "") for r in org_rows))

    if len(available_years) > 1:
        year_mode = st.radio(
            "Year View",
            ["All Years", "Single Year", "Year Range"],
            horizontal=True,
            key="year_filter_mode_radio",
        )

        if year_mode == "Single Year":
            sel_year = st.selectbox(
                "Select Year",
                available_years,
                index=len(available_years) - 1,
                key="single_year_select",
            )
            org_rows = [r for r in org_rows if r.get("TaxYear") == sel_year]
        elif year_mode == "Year Range":
            year_ints = [int(y) for y in available_years if y.isdigit()]
            if len(year_ints) >= 2:
                yr_min, yr_max = st.slider(
                    "Year Range",
                    min_value=min(year_ints),
                    max_value=max(year_ints),
                    value=(min(year_ints), max(year_ints)),
                    key="year_range_slider",
                )
                org_rows = [
                    r for r in org_rows
                    if r.get("TaxYear", "").isdigit()
                    and yr_min <= int(r["TaxYear"]) <= yr_max
                ]

    parsed_rows = org_rows  # final filtered data


# ═══════════════════════════════════════════════
# EMPTY STATE
# ═══════════════════════════════════════════════
if not all_parsed_rows or not parsed_rows:
    _es_hero = (
        '<div class="es-wrap">'
        '<div class="es-hero">'
        '<div class="es-badge">'
        '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">'
        '<path stroke-linecap="round" stroke-linejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5"/>'
        '</svg> Financial Intelligence'
        '</div>'
        '<div class="es-title">Nonprofit <span>990</span> Analysis</div>'
        '<div class="es-desc">'
        'Upload IRS Form 990 XML filings or search ProPublica to instantly generate '
        'KPI dashboards, trend analysis, and exportable reports.'
        '</div>'
        '</div>'
        '</div>'
    )
    st.markdown(_es_hero, unsafe_allow_html=True)

    _es_cards = (
        '<div class="es-wrap" style="padding-top:0;">'
        '<div class="es-grid">'
        '<div class="es-cd">'
        '<div class="es-icon teal">'
        '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">'
        '<path stroke-linecap="round" stroke-linejoin="round" d="M9 8.25H7.5a2.25 2.25 0 00-2.25 2.25v9a2.25 2.25 0 002.25 2.25h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25H15M9 12l3 3m0 0l3-3m-3 3V2.25"/>'
        '</svg>'
        '</div>'
        '<div class="es-t">Upload or Search</div>'
        '<div class="es-d">Upload XML files directly, or search ProPublica to find any US nonprofit by name.</div>'
        '</div>'
        '<div class="es-cd">'
        '<div class="es-icon indigo">'
        '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">'
        '<path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75z"/>'
        '<path stroke-linecap="round" stroke-linejoin="round" d="M9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625z"/>'
        '<path stroke-linecap="round" stroke-linejoin="round" d="M16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"/>'
        '</svg>'
        '</div>'
        '<div class="es-t">View Dashboard</div>'
        '<div class="es-d">KPI cards, charts, and trend analysis populate automatically from your data.</div>'
        '</div>'
        '<div class="es-cd">'
        '<div class="es-icon amber">'
        '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">'
        '<path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"/>'
        '</svg>'
        '</div>'
        '<div class="es-t">Export Report</div>'
        '<div class="es-d">Download a professionally formatted Excel workbook with full analysis.</div>'
        '</div>'
        '</div>'
        '<div class="es-hint">'
        'Supports IRS Form 990 XML e-file format · <b>Search ProPublica</b> in the sidebar to find any nonprofit'
        '</div>'
        '</div>'
    )
    st.markdown(_es_cards, unsafe_allow_html=True)
    st.stop()


# ═══════════════════════════════════════════════
# PROCESS DATA
# ═══════════════════════════════════════════════
kpi_data = []
for row in parsed_rows:
    kpis = compute_kpis(row)
    kpis["TaxYear"] = row.get("TaxYear", "")
    kpis["OrganizationName"] = row.get("OrganizationName", "")
    kpi_data.append(kpis)

kpi_df = pd.DataFrame(kpi_data)
latest = parsed_rows[-1]
latest_kpis = compute_kpis(latest)
org_name = latest.get("OrganizationName", "Unknown Organization")
latest_year = latest.get("TaxYear", "")


# ─── Org Banner ───
ein = latest.get("EIN", "N/A")
city, state = latest.get("City", ""), latest.get("State", "")
loc = f"{city}, {state}" if city and state else (city or state or "—")
yr_range = (
    f"{parsed_rows[0].get('TaxYear', '?')}–{latest_year}"
    if len(parsed_rows) > 1 else latest_year
)

# Build tag badges for org banner
banner_tags_html = ""
if user_id and ein != "N/A":
    banner_org_tags = get_tags_for_org(user_id, ein)
    if banner_org_tags:
        banner_tags_html = '<div class="tag-row" style="margin:8px 0 0;">'
        for bt in banner_org_tags:
            c = bt["tag_color"]
            r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
            bg = f"rgba({r},{g},{b},.12)"
            banner_tags_html += (
                f'<span class="tag-badge" style="background:{bg};color:{c};">'
                f'{bt["tag_name"]}</span>'
            )
        banner_tags_html += '</div>'

st.markdown(f"""
<div class="org-ban">
    <div class="accent-bar"></div>
    <div class="inner">
        <div>
            <h2>{org_name}</h2>
            <div class="meta">
                <span>EIN {ein}</span>
                <span class="dot">●</span>
                <span>{loc}</span>
                <span class="dot">●</span>
                <span>{len(parsed_rows)} year{"s" if len(parsed_rows) > 1 else ""}</span>
            </div>
            {banner_tags_html}
        </div>
        <div class="yr-badge">
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" fill="none"
                 viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round"
                      d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1
                         2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18
                         0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21
                         18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25
                         2.25 0 0 1 21 11.25v7.5"/>
            </svg>
            {yr_range}
        </div>
    </div>
</div>
""", unsafe_allow_html=True)


# ─── Export ───
c1, _ = st.columns([1, 4])
with c1:
    wb_bytes = generate_workbook(parsed_rows)
    safe = org_name.replace(" ", "_").replace("/", "_")[:30]
    st.download_button(
        "⬇ Download Excel Report",
        data=wb_bytes,
        file_name=f"{safe}_Form990_Analysis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


# ═══════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════
tab_names = ["Dashboard", "Trends", "Investment Detail", "Financial Statements", "Raw Data"]
if st.session_state.get("comparison_mode") and st.session_state.get("comparison_ein"):
    tab_names.append("Compare")

tabs = st.tabs(tab_names)


# ═══ TAB 1 — Dashboard ═══
with tabs[0]:
    st.markdown(
        _sec(f"Key Performance Indicators — {latest_year}",
             "Core financial health metrics for the most recent filing year."),
        unsafe_allow_html=True,
    )
    st.markdown(_kpi_html(PRIMARY_KPIS, latest_kpis), unsafe_allow_html=True)

    st.markdown(
        _sec("Additional Metrics",
             "Supplementary financial and operational indicators."),
        unsafe_allow_html=True,
    )
    st.markdown(
        _kpi_html(
            ["LiquidAssets", "TotalCashEquivalents", "CurrentRatio",
             "SalaryToExpenseRatio", "RevenueGrowth", "NetAssetGrowth"],
            latest_kpis,
        ),
        unsafe_allow_html=True,
    )

    if len(parsed_rows) > 1:
        st.markdown(
            _sec("Revenue vs. Expenses",
                 "Year-over-year comparison with surplus/deficit trend line."),
            unsafe_allow_html=True,
        )
        years = [r.get("TaxYear", "") for r in parsed_rows]
        revs = [r.get("TotalRevenue", 0) for r in parsed_rows]
        exps = [r.get("TotalExpenses", 0) for r in parsed_rows]
        surp = [rv - ex for rv, ex in zip(revs, exps)]

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=years, y=revs, name="Revenue",
                             marker_color=PAL[0], marker_cornerradius=4, opacity=.92),
                      secondary_y=False)
        fig.add_trace(go.Bar(x=years, y=exps, name="Expenses",
                             marker_color=PAL[5], marker_cornerradius=4, opacity=.92),
                      secondary_y=False)
        fig.add_trace(go.Scatter(x=years, y=surp, name="Surplus/Deficit",
                                 mode="lines+markers",
                                 line=dict(color=PAL[1], width=2.5),
                                 marker=dict(size=7)),
                      secondary_y=True)
        fig.update_layout(barmode="group")
        _th(fig, 400)
        fig.update_yaxes(title_text="Amount ($)", secondary_y=False, tickprefix="$")
        fig.update_yaxes(title_text="Surplus ($)", secondary_y=True, tickprefix="$")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        _sec(f"Expense Allocation — {latest_year}",
             "Breakdown of how expenses are distributed across functions."),
        unsafe_allow_html=True,
    )
    c_pie, c_bar = st.columns(2)
    with c_pie:
        prog = latest.get("ProgramExpenses", 0)
        mgmt = latest.get("ManagementGeneralExpenses", 0)
        fund = latest.get("FundraisingExpenses", 0)
        other = max(0, latest.get("TotalExpenses", 0) - prog - mgmt - fund)
        fp = go.Figure(go.Pie(
            labels=["Program", "Management", "Fundraising", "Other"],
            values=[prog, mgmt, fund, other], hole=.55,
            marker_colors=[PAL[0], PAL[5], PAL[2], "#CBD5E1"],
            textinfo="label+percent", textfont_size=11, textfont_color="#475569",
            insidetextorientation="radial", sort=False,
        ))
        fp.update_layout(showlegend=False, margin=dict(l=16, r=16, t=28, b=16),
                         height=360, paper_bgcolor="#fff", font=_CF)
        st.plotly_chart(fp, use_container_width=True)

    with c_bar:
        items = [
            ("Salaries", latest.get("SalariesWages", 0)),
            ("Grants Paid", latest.get("GrantsAndSimilarPaid", 0)),
            ("Occupancy", latest.get("Occupancy", 0)),
            ("Depreciation", latest.get("DepreciationAmortization", 0)),
            ("Travel", latest.get("Travel", 0)),
            ("IT", latest.get("InformationTechnology", 0)),
            ("Insurance", latest.get("Insurance", 0)),
            ("Legal", latest.get("LegalFees", 0)),
            ("Accounting", latest.get("AccountingFees", 0)),
            ("Office", latest.get("OfficeExpenses", 0)),
        ]
        items = sorted([(k, v) for k, v in items if v > 0],
                       key=lambda x: x[1], reverse=True)
        if items:
            fb = go.Figure(go.Bar(
                x=[v for _, v in items], y=[k for k, _ in items],
                orientation="h", marker_color=PAL[0], marker_cornerradius=4,
                text=[f"${v/1e6:.1f}M" if v >= 1e6 else f"${v/1e3:.0f}K"
                      for _, v in items],
                textposition="outside",
                textfont=dict(size=10, color="#64748B"),
            ))
            fb.update_layout(yaxis=dict(autorange="reversed"))
            _th(fb, 360)
            fb.update_layout(margin=dict(l=10, r=80, t=28, b=16),
                             xaxis_title="Amount ($)")
            fb.update_xaxes(tickprefix="$")
            st.plotly_chart(fb, use_container_width=True)


# ═══ TAB 2 — Trends ═══
with tabs[1]:
    if len(parsed_rows) < 2:
        st.info("Upload multiple years of data to unlock trend analysis. If you filtered to a single year, switch to 'All Years' or 'Year Range' to see trends.")
    else:
        st.markdown(
            _sec("Financial Trends",
                 "Track key metrics across filing years to spot patterns and shifts."),
            unsafe_allow_html=True,
        )
        trend_opts = {KPI_DEFINITIONS[k]["label"]: k for k in TREND_KPIS}
        sel = st.multiselect(
            "Select metrics",
            list(trend_opts.keys()),
            default=list(trend_opts.keys())[:4],
        )
        sel_keys = [trend_opts[l] for l in sel]

        if sel_keys:
            cols = st.columns(2)
            for i, kk in enumerate(sel_keys):
                dd = KPI_DEFINITIONS[kk]
                vals = [kpi_data[j].get(kk, 0) for j in range(len(kpi_data))]
                yrs = [kpi_data[j].get("TaxYear", "") for j in range(len(kpi_data))]
                c = PAL[i % len(PAL)]
                r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)

                f = go.Figure()
                f.add_trace(go.Scatter(
                    x=yrs, y=vals, mode="lines+markers+text",
                    line=dict(color=c, width=2.5), marker=dict(size=7, color=c),
                    text=[format_kpi_value(kk, v) for v in vals],
                    textposition="top center",
                    textfont=dict(size=9, color="#64748B"),
                    fill="tozeroy", fillcolor=f"rgba({r},{g},{b},.04)",
                ))
                if dd.get("format") in ("percent", "currency"):
                    f.add_hline(y=0, line_dash="dot", line_color="#E2E8F0",
                                line_width=1)
                f.update_layout(
                    title=dict(text=dd["label"],
                               font=dict(size=12.5, color="#0F172A", family="Inter")),
                    showlegend=False,
                )
                _th(f, 280)
                if dd.get("format") == "percent":
                    f.update_yaxes(tickformat=".1%")
                elif dd.get("format") == "currency":
                    f.update_yaxes(tickprefix="$")
                with cols[i % 2]:
                    st.plotly_chart(f, use_container_width=True)

        st.markdown(
            _sec("Balance Sheet Trend",
                 "Assets, liabilities, and net assets over time."),
            unsafe_allow_html=True,
        )
        ybs = [r.get("TaxYear", "") for r in parsed_rows]
        fig_bs = go.Figure()
        fig_bs.add_trace(go.Bar(
            x=ybs, y=[r.get("TotalAssets", 0) for r in parsed_rows],
            name="Assets", marker_color=PAL[0], marker_cornerradius=4))
        fig_bs.add_trace(go.Bar(
            x=ybs, y=[r.get("TotalLiabilities", 0) for r in parsed_rows],
            name="Liabilities", marker_color=ROSE,
            marker_cornerradius=4, opacity=.85))
        fig_bs.add_trace(go.Scatter(
            x=ybs, y=[r.get("TotalNetAssets", 0) for r in parsed_rows],
            name="Net Assets", mode="lines+markers",
            line=dict(color=PAL[1], width=2.5), marker=dict(size=7)))
        fig_bs.update_layout(barmode="group", yaxis_title="Amount ($)")
        _th(fig_bs, 380)
        fig_bs.update_yaxes(tickprefix="$")
        st.plotly_chart(fig_bs, use_container_width=True)

        st.markdown(
            _sec("Workforce Trend",
                 "Employee count and board composition over time."),
            unsafe_allow_html=True,
        )
        fig_wf = make_subplots(specs=[[{"secondary_y": True}]])
        fig_wf.add_trace(go.Bar(
            x=ybs, y=[r.get("EmployeeCount", 0) for r in parsed_rows],
            name="Employees", marker_color=PAL[0], marker_cornerradius=4),
            secondary_y=False)
        fig_wf.add_trace(go.Scatter(
            x=ybs, y=[r.get("VotingBoardMembers", 0) for r in parsed_rows],
            name="Board", mode="lines+markers",
            line=dict(color=PAL[2], width=2), marker=dict(size=7)),
            secondary_y=True)
        _th(fig_wf, 340)
        fig_wf.update_yaxes(title_text="Employees", secondary_y=False)
        fig_wf.update_yaxes(title_text="Board Members", secondary_y=True)
        st.plotly_chart(fig_wf, use_container_width=True)


# ═══ TAB 3 — Investment Detail (NEW) ═══
with tabs[2]:
    st.markdown(
        _sec(f"Investment & Asset Detail — {latest_year}",
             "Cash breakdown, investment returns, and real estate assets."),
        unsafe_allow_html=True,
    )
    st.markdown(_kpi_html(INVESTMENT_KPIS[:4], latest_kpis), unsafe_allow_html=True)

    st.markdown(
        _sec("Investment Returns",
             "Realized gains, unrealized gains, and total investment performance."),
        unsafe_allow_html=True,
    )
    st.markdown(_kpi_html(INVESTMENT_KPIS[4:8], latest_kpis), unsafe_allow_html=True)

    st.markdown(
        _sec("Return Ratios",
             "Investment returns relative to assets, liquid assets, and expenses."),
        unsafe_allow_html=True,
    )
    st.markdown(_kpi_html(INVESTMENT_KPIS[8:], latest_kpis), unsafe_allow_html=True)

    if len(parsed_rows) > 1:
        st.markdown(
            _sec("Cash & Savings Trend",
                 "Cash and savings positions over time."),
            unsafe_allow_html=True,
        )
        yrs_inv = [r.get("TaxYear", "") for r in parsed_rows]
        fig_cash = go.Figure()
        fig_cash.add_trace(go.Bar(
            x=yrs_inv,
            y=[r.get("CashNonInterest", 0) for r in parsed_rows],
            name="Cash (Non-Interest)", marker_color=PAL[0], marker_cornerradius=4,
        ))
        fig_cash.add_trace(go.Bar(
            x=yrs_inv,
            y=[r.get("SavingsTempCashInvestments", 0) for r in parsed_rows],
            name="Savings & Temp Inv.", marker_color=PAL[1], marker_cornerradius=4,
        ))
        fig_cash.add_trace(go.Bar(
            x=yrs_inv,
            y=[r.get("PublicInvestments", 0) for r in parsed_rows],
            name="Public Securities", marker_color=PAL[2], marker_cornerradius=4,
        ))
        fig_cash.update_layout(barmode="stack", yaxis_title="Amount ($)")
        _th(fig_cash, 380)
        fig_cash.update_yaxes(tickprefix="$")
        st.plotly_chart(fig_cash, use_container_width=True)


# ═══ TAB 4 — Financial Statements ═══
with tabs[3]:
    all_years = [r.get("TaxYear", "") for r in parsed_rows]

    st.markdown(
        _sec("Revenue by Year", "All revenue sources across filing years."),
        unsafe_allow_html=True,
    )
    st.markdown(_fin_table("Revenue by Year", all_years, [
        {"label": "Contributions & Grants", "key": "TotalContributionsGrants"},
        {"label": "Program Service Revenue", "key": "ProgramServiceRevenue"},
        {"label": "Investment Income", "key": "InvestmentIncome"},
        {"label": "Other Revenue", "key": "OtherRevenue"},
        {"label": "Total Revenue", "key": "TotalRevenue"},
    ], parsed_rows), unsafe_allow_html=True)

    if len(parsed_rows) > 1:
        rev_years = [r.get("TaxYear", "") for r in parsed_rows]
        fig_r = go.Figure()
        for src, clr in [
            ("TotalContributionsGrants", PAL[0]),
            ("ProgramServiceRevenue", PAL[5]),
            ("InvestmentIncome", PAL[2]),
            ("OtherRevenue", PAL[3]),
        ]:
            fig_r.add_trace(go.Bar(
                x=rev_years,
                y=[r.get(src, 0) for r in parsed_rows],
                name=FIELD_LABELS.get(src, src),
                marker_color=clr, marker_cornerradius=4,
            ))
        fig_r.update_layout(barmode="stack", yaxis_title="Amount ($)")
        _th(fig_r, 380)
        fig_r.update_yaxes(tickprefix="$")
        st.plotly_chart(fig_r, use_container_width=True)

    st.markdown(
        _sec("Expenses by Year", "Functional and line-item expense breakdown."),
        unsafe_allow_html=True,
    )
    st.markdown(_fin_table("Expenses by Year", all_years, [
        {"label": "Program Expenses", "key": "ProgramExpenses"},
        {"label": "Management & General", "key": "ManagementGeneralExpenses"},
        {"label": "Fundraising", "key": "FundraisingExpenses"},
        {"label": "Salaries & Wages", "key": "SalariesWages"},
        {"label": "Grants Paid", "key": "GrantsAndSimilarPaid"},
        {"label": "Total Expenses", "key": "TotalExpenses"},
    ], parsed_rows), unsafe_allow_html=True)

    st.markdown(
        _sec("Balance Sheet by Year",
             "Assets, liabilities, and net asset composition."),
        unsafe_allow_html=True,
    )
    st.markdown(_fin_table("Balance Sheet by Year", all_years, [
        {"label": "Total Assets", "key": "TotalAssets"},
        {"label": "Total Liabilities", "key": "TotalLiabilities"},
        {"label": "Net Assets (Unrestricted)", "key": "NetAssetsWithoutDonorRestrictions"},
        {"label": "Net Assets (Restricted)", "key": "NetAssetsWithDonorRestrictions"},
        {"label": "Total Net Assets", "key": "TotalNetAssets"},
    ], parsed_rows), unsafe_allow_html=True)


# ═══ TAB 5 — Raw Data ═══
with tabs[4]:
    st.markdown(
        _sec("Extracted Data",
             "Every field extracted from the uploaded Form 990 XML files."),
        unsafe_allow_html=True,
    )
    raw_df = pd.DataFrame([
        {FIELD_LABELS.get(f, f): r.get(f) for f in FIELD_LABELS if f in r}
        for r in parsed_rows
    ])
    st.dataframe(raw_df, use_container_width=True, hide_index=True, height=500)

    st.markdown(
        _sec("KPI Summary — All Years",
             "Computed metrics for every filing year."),
        unsafe_allow_html=True,
    )
    kpi_display_df = pd.DataFrame([
        {"Year": r.get("TaxYear", "")}
        | {d["label"]: format_kpi_value(k, compute_kpis(r).get(k, 0))
           for k, d in KPI_DEFINITIONS.items()}
        for r in parsed_rows
    ])
    st.dataframe(kpi_display_df, use_container_width=True, hide_index=True)


# ═══ TAB 6 — Compare (conditional) ═══
if len(tabs) > 5:
    with tabs[5]:
        comp_ein = st.session_state.get("comparison_ein")
        if comp_ein and comp_ein in ein_map:
            comp_rows = sorted(
                ein_map[comp_ein]["rows"],
                key=lambda r: r.get("TaxYear", ""),
            )
            comp_latest = comp_rows[-1]
            comp_kpis = compute_kpis(comp_latest)
            comp_name = comp_latest.get("OrganizationName", "Unknown")
            comp_year = comp_latest.get("TaxYear", "")

            st.markdown(
                _sec("Organization Comparison",
                     f"Side-by-side KPI comparison for the most recent filing year."),
                unsafe_allow_html=True,
            )

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(
                    f'<div class="comp-hdr org-a">{org_name} ({latest_year})</div>',
                    unsafe_allow_html=True,
                )
            with col_b:
                st.markdown(
                    f'<div class="comp-hdr org-b">{comp_name} ({comp_year})</div>',
                    unsafe_allow_html=True,
                )

            for kpi_key in PRIMARY_KPIS:
                d = KPI_DEFINITIONS.get(kpi_key, {})
                v_a = latest_kpis.get(kpi_key, 0)
                v_b = comp_kpis.get(kpi_key, 0)
                fv_a = format_kpi_value(kpi_key, v_a)
                fv_b = format_kpi_value(kpi_key, v_b)
                s_a = get_kpi_status(kpi_key, v_a)
                s_b = get_kpi_status(kpi_key, v_b)

                if isinstance(v_a, (int, float)) and isinstance(v_b, (int, float)) and v_b != 0:
                    diff_pct = ((v_a - v_b) / abs(v_b)) * 100
                    delta_cls = "positive" if diff_pct > 0 else ("negative" if diff_pct < 0 else "neutral")
                    delta_html = f'<span class="comp-delta {delta_cls}">{diff_pct:+.1f}%</span>'
                else:
                    delta_html = ""

                ca, cb = st.columns(2)
                lbl_a, cls_a = _ST.get(s_a, ("—", "n"))
                lbl_b, cls_b = _ST.get(s_b, ("—", "n"))

                with ca:
                    st.markdown(f"""<div class="kpi-c">
                        <div class="kpi-top">
                            <span class="kpi-lbl">{d.get('label', kpi_key)}</span>
                            <span class="bdg bdg-{cls_a}"><span class="dt"></span>{lbl_a}</span>
                        </div>
                        <div class="kpi-val">{fv_a} {delta_html}</div>
                    </div>""", unsafe_allow_html=True)
                with cb:
                    st.markdown(f"""<div class="kpi-c">
                        <div class="kpi-top">
                            <span class="kpi-lbl">{d.get('label', kpi_key)}</span>
                            <span class="bdg bdg-{cls_b}"><span class="dt"></span>{lbl_b}</span>
                        </div>
                        <div class="kpi-val">{fv_b}</div>
                    </div>""", unsafe_allow_html=True)

            st.markdown(
                _sec("Additional Metrics Comparison", ""),
                unsafe_allow_html=True,
            )
            extra_kpis = ["LiquidAssets", "TotalCashEquivalents", "CurrentRatio",
                          "SalaryToExpenseRatio", "RevenueGrowth", "NetAssetGrowth"]
            for kpi_key in extra_kpis:
                d = KPI_DEFINITIONS.get(kpi_key, {})
                v_a = latest_kpis.get(kpi_key, 0)
                v_b = comp_kpis.get(kpi_key, 0)
                fv_a = format_kpi_value(kpi_key, v_a)
                fv_b = format_kpi_value(kpi_key, v_b)

                ca, cb = st.columns(2)
                with ca:
                    st.metric(d.get("label", kpi_key), fv_a)
                with cb:
                    st.metric(d.get("label", kpi_key), fv_b)


# ─── Footer ───
st.markdown("""
<div class="bi-ft">
    <b>Brighter Investing</b> — Form 990 Financial Analyzer<br>
    Developed by Epic Intentions · Georgia Institute of Technology · Spring 2026<br>
    <span style="font-size:.65rem;color:#94A3B8;">Data sourced from IRS Form 990 XML e-file submissions & ProPublica Nonprofit Explorer.</span>
</div>
""", unsafe_allow_html=True)
