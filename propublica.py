"""
ProPublica Nonprofit Explorer Integration
Search nonprofits and fetch Form 990 XML filings directly from ProPublica's API.

Developed by Epic Intentions for Brighter Investing
Georgia Institute of Technology — Spring 2026
"""

import requests
import streamlit as st
import xml.etree.ElementTree as ET


PROPUBLICA_SEARCH_URL = "https://projects.propublica.org/nonprofits/api/v2/search.json"
PROPUBLICA_ORG_URL = "https://projects.propublica.org/nonprofits/api/v2/organizations/{ein}.json"


@st.cache_data(ttl=300, show_spinner=False)
def search_nonprofits(query, page=0):
    """
    Search ProPublica Nonprofit Explorer for organizations.

    Parameters:
        query: search string (name, EIN, etc.)
        page: pagination (0-indexed)

    Returns:
        dict with 'organizations' list and 'total_results' count
    """
    try:
        resp = requests.get(
            PROPUBLICA_SEARCH_URL,
            params={"q": query, "page": page},
            timeout=10,
            headers={"User-Agent": "BrighterInvesting/1.0"},
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "organizations": data.get("organizations", []),
            "total_results": data.get("total_results", 0),
            "num_pages": data.get("num_pages", 0),
        }
    except requests.exceptions.RequestException as e:
        return {"organizations": [], "total_results": 0, "error": str(e)}


@st.cache_data(ttl=300, show_spinner=False)
def get_organization_filings(ein):
    """
    Get filing history for a specific organization by EIN.

    Returns:
        dict with org info and list of filings with XML URLs
    """
    try:
        url = PROPUBLICA_ORG_URL.format(ein=ein)
        resp = requests.get(
            url,
            timeout=10,
            headers={"User-Agent": "BrighterInvesting/1.0"},
        )
        resp.raise_for_status()
        data = resp.json()
        org = data.get("organization", {})
        filings = data.get("filings_with_data", [])

        # Also check filings_without_data for completeness
        filings_no_data = data.get("filings_without_data", [])

        return {
            "organization": org,
            "filings_with_data": filings,
            "filings_without_data": filings_no_data,
        }
    except requests.exceptions.RequestException as e:
        return {"organization": {}, "filings_with_data": [], "error": str(e)}


@st.cache_data(ttl=600, show_spinner=False)
def fetch_filing_xml(xml_url):
    """
    Download a Form 990 XML filing from the IRS/ProPublica.

    Parameters:
        xml_url: URL to the XML filing

    Returns:
        bytes of the XML content, or None on failure
    """
    try:
        resp = requests.get(
            xml_url,
            timeout=30,
            headers={"User-Agent": "BrighterInvesting/1.0"},
        )
        resp.raise_for_status()
        return resp.content
    except requests.exceptions.RequestException:
        return None


def format_filing_year(filing):
    """Extract a human-readable tax year from a filing record."""
    tax_prd = filing.get("tax_prd", "")
    tax_prd_yr = filing.get("tax_prd_yr", "")
    if tax_prd_yr:
        return str(tax_prd_yr)
    if tax_prd and len(str(tax_prd)) >= 4:
        return str(tax_prd)[:4]
    return "Unknown"


def format_revenue(value):
    """Format a revenue number for display."""
    if value is None:
        return "N/A"
    try:
        v = float(value)
        if abs(v) >= 1_000_000_000:
            return f"${v / 1e9:.1f}B"
        if abs(v) >= 1_000_000:
            return f"${v / 1e6:.1f}M"
        if abs(v) >= 1_000:
            return f"${v / 1e3:.0f}K"
        return f"${v:,.0f}"
    except (ValueError, TypeError):
        return "N/A"
