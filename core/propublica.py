"""
ProPublica Nonprofit Explorer Integration
Search nonprofits and fetch Form 990 XML filings directly from ProPublica's API.

Developed by Epic Intentions for Brighter Investing
Georgia Institute of Technology — Spring 2026
"""

import json
import re

import requests
import streamlit as st


PROPUBLICA_SEARCH_URL = "https://projects.propublica.org/nonprofits/api/v2/search.json"
PROPUBLICA_ORG_URL = "https://projects.propublica.org/nonprofits/api/v2/organizations/{ein}.json"
PROPUBLICA_ORG_PAGE = "https://projects.propublica.org/nonprofits/organizations/{ein}"
PROPUBLICA_DOWNLOAD_XML = "https://projects.propublica.org/nonprofits/download-xml?object_id={object_id}"


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
        return {
            "organizations": [], "total_results": 0,
            "error": f"Could not connect to ProPublica. Check your internet connection. ({e})",
        }
    except (json.JSONDecodeError, ValueError):
        return {
            "organizations": [], "total_results": 0,
            "error": "ProPublica returned an unexpected response. Try again later.",
        }


@st.cache_data(ttl=3600, show_spinner=False)
def _scrape_xml_object_ids(ein):
    """
    Scrape the ProPublica organization page to extract object_ids for XML downloads.

    The ProPublica API no longer includes xml_url in filings. The organization
    web page contains download-xml links with object_id parameters.

    Returns:
        dict mapping fiscal-year strings to object_ids, e.g. {"2023": "202431279349301813"}
    """
    try:
        url = PROPUBLICA_ORG_PAGE.format(ein=ein)
        resp = requests.get(url, timeout=15, headers={"User-Agent": "BrighterInvesting/1.0"})
        resp.raise_for_status()

        # Pattern: /nonprofits/download-xml?object_id=NNNN
        # These appear near fiscal year labels on the page
        pattern = re.compile(
            r'download-xml\?object_id=(\d+)',
        )
        object_ids = pattern.findall(resp.text)

        # Match each object_id to a year from surrounding context.
        # The page lists filings in order; the object_ids appear paired
        # with fiscal year text. Extract year-objectid pairs from the HTML.
        year_pattern = re.compile(
            r'Fiscal Year (\d{4}).*?download-xml\?object_id=(\d+)',
            re.DOTALL,
        )
        year_map = {}
        for match in year_pattern.finditer(resp.text):
            year_map[match.group(1)] = match.group(2)

        # Fallback: if the regex above didn't capture well,
        # just return the raw list of object_ids (caller will use index-based matching)
        if not year_map and object_ids:
            return {"_raw_ids": object_ids}

        return year_map
    except requests.exceptions.RequestException:
        return {}


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
        filings_no_data = data.get("filings_without_data", [])

        # ProPublica API v2 no longer includes xml_url in filings.
        # Scrape the organization page for download-xml object_ids.
        xml_ids = _scrape_xml_object_ids(ein)

        if xml_ids:
            raw_ids = xml_ids.pop("_raw_ids", None)

            if xml_ids:
                # Year-based matching
                for filing in filings:
                    yr = str(filing.get("tax_prd_yr", ""))
                    if yr in xml_ids:
                        filing["xml_url"] = PROPUBLICA_DOWNLOAD_XML.format(
                            object_id=xml_ids[yr]
                        )
            elif raw_ids:
                # Index-based fallback: assign object_ids in order
                for i, filing in enumerate(filings):
                    if i < len(raw_ids):
                        filing["xml_url"] = PROPUBLICA_DOWNLOAD_XML.format(
                            object_id=raw_ids[i]
                        )

        return {
            "organization": org,
            "filings_with_data": filings,
            "filings_without_data": filings_no_data,
        }
    except requests.exceptions.RequestException as e:
        return {
            "organization": {}, "filings_with_data": [],
            "error": f"Could not connect to ProPublica. Check your internet connection. ({e})",
        }
    except (json.JSONDecodeError, ValueError):
        return {
            "organization": {}, "filings_with_data": [],
            "error": "ProPublica returned an unexpected response. Try again later.",
        }


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_filing_xml(xml_url):
    """
    Download a Form 990 XML filing from ProPublica.

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
