"""
Compare Page — Tab 6
Side-by-side KPI comparison between two organizations.
"""

import streamlit as st

from core.kpis import (
    compute_kpis, KPI_DEFINITIONS, PRIMARY_KPIS,
    format_kpi_value, get_kpi_status,
)
from components.kpi_cards import sec

_ST = {"good": ("Healthy", "g"), "warning": ("Watch", "w"), "concern": ("At Risk", "b")}


def render(parsed_rows, latest_kpis, org_name, latest_year, ein_map):
    comp_ein = st.session_state.get("comparison_ein")
    if not comp_ein or comp_ein not in ein_map:
        st.info("Select a comparison organization from the sidebar to view this tab.")
        return

    comp_rows = sorted(
        ein_map[comp_ein]["rows"],
        key=lambda r: r.get("TaxYear", ""),
    )
    comp_latest = comp_rows[-1]
    comp_kpis = compute_kpis(comp_latest)
    comp_name = comp_latest.get("OrganizationName", "Unknown")
    comp_year = comp_latest.get("TaxYear", "")

    st.markdown(
        sec("Organization Comparison",
            "Side-by-side KPI comparison for the most recent filing year."),
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
        lbl_a, cls_a = _ST.get(s_a, ("\u2014", "n"))
        lbl_b, cls_b = _ST.get(s_b, ("\u2014", "n"))

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
        sec("Additional Metrics Comparison", ""),
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
