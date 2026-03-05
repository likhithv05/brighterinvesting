"""
Empty State Component
Displayed when no data is loaded.
"""

import streamlit as st


def render_empty_state():
    """Render the onboarding empty state with feature cards."""
    st.markdown(
        '<div class="es-wrap"><div class="es-hero">'
        '<div class="es-badge">Financial Intelligence</div>'
        '<div class="es-title">Nonprofit <span>990</span> Analysis</div>'
        '<div class="es-desc">Upload IRS Form 990 XML filings or search ProPublica to instantly generate '
        'KPI dashboards, trend analysis, and exportable reports.</div></div></div>'
        '<div class="es-wrap" style="padding-top:0;"><div class="es-grid">'
        '<div class="es-cd">'
        '<div class="es-t">Upload or Search</div>'
        '<div class="es-d">Upload XML files directly, or search ProPublica to find any US nonprofit by name.</div></div>'
        '<div class="es-cd">'
        '<div class="es-t">View Dashboard</div>'
        '<div class="es-d">KPI cards, charts, and trend analysis populate automatically from your data.</div></div>'
        '<div class="es-cd">'
        '<div class="es-t">Export Report</div>'
        '<div class="es-d">Download a professionally formatted Excel workbook with full analysis.</div></div>'
        '</div>'
        '<div class="es-hint">Supports IRS Form 990 XML e-file format \u00b7 '
        '<b>Search ProPublica</b> in the sidebar to find any nonprofit</div></div>',
        unsafe_allow_html=True,
    )
