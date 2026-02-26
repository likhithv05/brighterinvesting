"""
Header & Org Banner Components
Logo header bar and organization banner for the main app view.
"""

import os
import base64
import streamlit as st

from core.db_utils import get_tags_for_org


@st.cache_data
def _logo_b64():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "logo.svg")
    if os.path.isfile(p):
        with open(p, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""


def get_logo_tags():
    """Return (logo_tag, logo_tag_sm) HTML strings."""
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
    return logo_tag, logo_tag_sm


def render_header():
    """Render the top header bar with logo."""
    logo_tag, _ = get_logo_tags()
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


def render_org_banner(parsed_rows, latest, user_id):
    """Render the organization banner card."""
    org_name = latest.get("OrganizationName", "Unknown Organization")
    ein = latest.get("EIN", "N/A")
    city, state = latest.get("City", ""), latest.get("State", "")
    loc = f"{city}, {state}" if city and state else (city or state or "\u2014")
    latest_year = latest.get("TaxYear", "")
    yr_range = (
        f"{parsed_rows[0].get('TaxYear', '?')}\u2013{latest_year}"
        if len(parsed_rows) > 1 else latest_year
    )

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
                    <span class="dot">\u25cf</span>
                    <span>{loc}</span>
                    <span class="dot">\u25cf</span>
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


def render_footer():
    """Render the page footer."""
    st.markdown("""
    <div class="bi-ft">
        <b>Brighter Investing</b> \u2014 Form 990 Financial Analyzer<br>
        Developed by Epic Intentions \u00b7 Georgia Institute of Technology \u00b7 Spring 2026<br>
        <span style="font-size:.65rem;color:#94A3B8;">Data sourced from IRS Form 990 XML e-file submissions & ProPublica Nonprofit Explorer.</span>
    </div>
    """, unsafe_allow_html=True)
