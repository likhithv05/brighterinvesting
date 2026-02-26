"""
Empty State Component
Displayed when no data is loaded.
"""

import streamlit as st


def render_empty_state():
    """Render the onboarding empty state with feature cards."""
    st.markdown(
        '<div class="es-wrap"><div class="es-hero">'
        '<div class="es-badge">'
        '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">'
        '<path stroke-linecap="round" stroke-linejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5"/>'
        '</svg> Financial Intelligence</div>'
        '<div class="es-title">Nonprofit <span>990</span> Analysis</div>'
        '<div class="es-desc">Upload IRS Form 990 XML filings or search ProPublica to instantly generate '
        'KPI dashboards, trend analysis, and exportable reports.</div></div></div>'
        '<div class="es-wrap" style="padding-top:0;"><div class="es-grid">'
        '<div class="es-cd"><div class="es-icon teal"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9 8.25H7.5a2.25 2.25 0 00-2.25 2.25v9a2.25 2.25 0 002.25 2.25h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25H15M9 12l3 3m0 0l3-3m-3 3V2.25"/></svg></div>'
        '<div class="es-t">Upload or Search</div><div class="es-d">Upload XML files directly, or search ProPublica to find any US nonprofit by name.</div></div>'
        '<div class="es-cd"><div class="es-icon indigo"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75z"/><path stroke-linecap="round" stroke-linejoin="round" d="M9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625z"/><path stroke-linecap="round" stroke-linejoin="round" d="M16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"/></svg></div>'
        '<div class="es-t">View Dashboard</div><div class="es-d">KPI cards, charts, and trend analysis populate automatically from your data.</div></div>'
        '<div class="es-cd"><div class="es-icon amber"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"/></svg></div>'
        '<div class="es-t">Export Report</div><div class="es-d">Download a professionally formatted Excel workbook with full analysis.</div></div>'
        '</div><div class="es-hint">Supports IRS Form 990 XML e-file format \u00b7 <b>Search ProPublica</b> in the sidebar to find any nonprofit</div></div>',
        unsafe_allow_html=True,
    )
