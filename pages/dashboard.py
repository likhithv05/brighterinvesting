"""
Dashboard Page — Tab 1
Financial health overview with KPI cards and revenue vs expenses chart.
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.kpis import (
    PRIMARY_KPIS, KPI_DEFINITIONS,
    format_kpi_value, get_kpi_status,
)
from components.charts import apply_theme, PAL


# Status label / CSS-class mapping
_STATUS = {
    "good": ("Healthy", "g"),
    "warning": ("Watch", "w"),
    "concern": ("At Risk", "b"),
}

_SECONDARY_KPIS = [
    "LiquidAssets", "TotalCashEquivalents", "CurrentRatio",
    "SalaryToExpenseRatio", "RevenueGrowth", "NetAssetGrowth",
]


def _kpi_card(key, kpis_dict):
    """Render a single KPI card inside an st.container."""
    defn = KPI_DEFINITIONS.get(key, {})
    value = kpis_dict.get(key, 0)
    formatted = format_kpi_value(key, value)
    status = get_kpi_status(key, value)
    label, cls = _STATUS.get(status, ("\u2014", "n"))

    with st.container(border=True):
        st.markdown(
            f'<div class="kpi-lbl">{defn.get("label", key)}</div>'
            f'<div class="kpi-val">{formatted}</div>'
            f'<span class="bdg bdg-{cls}"><span class="dt"></span>{label}</span>'
            f'<div class="kpi-bm">{defn.get("benchmark", "")}</div>',
            unsafe_allow_html=True,
        )


def _kpi_grid(keys, kpis_dict):
    """Render a 3-column grid of KPI cards."""
    for row_start in range(0, len(keys), 3):
        row_keys = keys[row_start:row_start + 3]
        cols = st.columns(3)
        for col, key in zip(cols, row_keys):
            with col:
                _kpi_card(key, kpis_dict)


def _revenue_expenses_chart(parsed_rows):
    """Grouped bar chart: revenue vs expenses with surplus line."""
    years = [r.get("TaxYear", "") for r in parsed_rows]
    revs = [r.get("TotalRevenue", 0) for r in parsed_rows]
    exps = [r.get("TotalExpenses", 0) for r in parsed_rows]
    surp = [rv - ex for rv, ex in zip(revs, exps)]

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=years, y=revs, name="Revenue",
            marker_color=PAL[0], marker_cornerradius=4, opacity=0.92,
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Bar(
            x=years, y=exps, name="Expenses",
            marker_color="#64748B", marker_cornerradius=4, opacity=0.92,
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=years, y=surp, name="Surplus / Deficit",
            mode="lines+markers",
            line=dict(color=PAL[1], width=2.5),
            marker=dict(size=7),
        ),
        secondary_y=True,
    )
    fig.update_layout(barmode="group")
    apply_theme(fig, 400)
    fig.update_yaxes(title_text="Amount ($)", secondary_y=False, tickprefix="$")
    fig.update_yaxes(title_text="Surplus ($)", secondary_y=True, tickprefix="$")
    st.plotly_chart(fig, use_container_width=True)


def render(parsed_rows, latest_kpis, latest_year):
    # ── Section 1: Primary KPIs ──
    st.markdown(
        f'<div class="sec-t">Financial Health Overview \u2014 {latest_year}</div>'
        f'<div class="sec-s">Core financial health metrics for the most recent filing year.</div>',
        unsafe_allow_html=True,
    )
    _kpi_grid(PRIMARY_KPIS, latest_kpis)

    # ── Section 2: Revenue vs Expenses (multi-year only) ──
    if len(parsed_rows) > 1:
        st.markdown(
            '<div class="sec-t">Revenue vs. Expenses</div>'
            '<div class="sec-s">Year-over-year comparison with surplus/deficit trend line.</div>',
            unsafe_allow_html=True,
        )
        _revenue_expenses_chart(parsed_rows)
    else:
        st.info("Upload multiple years of data to see the Revenue vs. Expenses chart.")

    # ── Section 3: Secondary KPIs ──
    st.markdown(
        '<div class="sec-t">Additional Metrics</div>'
        '<div class="sec-s">Supplementary financial and operational indicators.</div>',
        unsafe_allow_html=True,
    )
    _kpi_grid(_SECONDARY_KPIS, latest_kpis)
