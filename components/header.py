"""
Header & Org Banner Components
Logo header bar and organization banner for the main app view.
"""

import os
import base64
import streamlit as st

from core.db_utils import get_tags_for_org


# Words that should stay lowercase in title case (unless first word)
_SMALL_WORDS = {"a", "an", "and", "as", "at", "but", "by", "for", "if", "in",
                "nor", "of", "on", "or", "so", "the", "to", "up", "yet"}
# Common abbreviations that should stay uppercase
_UPPER_WORDS = {"llc", "llp", "lp", "ii", "iii", "iv",
                "usa", "us", "ymca", "ywca", "hiv", "aids",
                "ar", "ny", "ca", "tx", "fl", "pa", "oh", "il", "ga",
                "nc", "va", "wa", "ma", "md", "mn", "wi", "mo", "tn",
                "az", "nj", "ct", "ok", "ky", "la", "sc", "al",
                "ia", "ks", "ms", "ut", "nv", "nm", "hi", "wv",
                "nh", "ri", "mt", "sd", "nd", "ak", "vt", "wy", "dc",
                "nw", "ne", "sw", "se"}


def smart_title(name):
    """Convert an org name to smart title case.

    Handles ALL CAPS names from Form 990, preserving abbreviations
    and applying standard title case rules.
    """
    if not name:
        return name
    # Only transform if the name is mostly uppercase
    upper_count = sum(1 for c in name if c.isupper())
    alpha_count = sum(1 for c in name if c.isalpha())
    if alpha_count > 0 and upper_count / alpha_count < 0.7:
        return name  # Already mixed case, leave it alone

    words = name.split()
    result = []
    for i, word in enumerate(words):
        lower = word.lower().rstrip(".,;:")
        punct_suffix = word[len(lower):]  # trailing punctuation
        if lower in _UPPER_WORDS:
            result.append(lower.upper() + punct_suffix)
        elif i > 0 and lower in _SMALL_WORDS:
            result.append(lower + punct_suffix)
        else:
            # Normal capitalization: "INC" -> "Inc", "REMERGE" -> "Remerge"
            result.append(word.capitalize() + punct_suffix)
    return " ".join(result)


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
    org_name = smart_title(latest.get("OrganizationName", "Unknown Organization"))
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

    n_years = len(parsed_rows)
    yr_text = f"{n_years} year{'s' if n_years > 1 else ''}"
    st.markdown(
        f'<div class="org-ban">'
        f'<div class="accent-bar"></div>'
        f'<div class="inner"><div>'
        f'<h2>{org_name}</h2>'
        f'<div class="meta">'
        f'<span>EIN {ein}</span>'
        f'<span class="dot">\u25cf</span>'
        f'<span>{loc}</span>'
        f'<span class="dot">\u25cf</span>'
        f'<span>{yr_range}</span>'
        f'<span class="dot">\u25cf</span>'
        f'<span>{yr_text}</span>'
        f'</div>'
        f'{banner_tags_html}'
        f'</div></div></div>',
        unsafe_allow_html=True,
    )


def render_footer():
    """Render the page footer."""
    st.markdown("""
    <div class="bi-ft">
        <b>Brighter Investing</b> \u2014 Form 990 Financial Analyzer<br>
        Developed by Epic Intentions \u00b7 Georgia Institute of Technology \u00b7 Spring 2026<br>
        <span style="font-size:.65rem;color:#94A3B8;">Data sourced from IRS Form 990 XML e-file submissions & ProPublica Nonprofit Explorer.</span>
    </div>
    """, unsafe_allow_html=True)
