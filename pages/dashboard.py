"""
Dashboard Page — Tab 1
KPI cards, revenue vs expenses chart, and expense allocation.
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.kpis import compute_kpis, PRIMARY_KPIS
from components.kpi_cards import sec, kpi_html
from components.charts import apply_theme, PAL


def render(parsed_rows, latest_kpis, latest_year):
    st.markdown(
        sec(f"Key Performance Indicators — {latest_year}",
            "Core financial health metrics for the most recent filing year."),
        unsafe_allow_html=True,
    )
    st.markdown(kpi_html(PRIMARY_KPIS, latest_kpis), unsafe_allow_html=True)

    st.markdown(
        sec("Additional Metrics",
            "Supplementary financial and operational indicators."),
        unsafe_allow_html=True,
    )
    st.markdown(
        kpi_html(
            ["LiquidAssets", "TotalCashEquivalents", "CurrentRatio",
             "SalaryToExpenseRatio", "RevenueGrowth", "NetAssetGrowth"],
            latest_kpis,
        ),
        unsafe_allow_html=True,
    )

    if len(parsed_rows) > 1:
        st.markdown(
            sec("Revenue vs. Expenses",
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
        apply_theme(fig, 400)
        fig.update_yaxes(title_text="Amount ($)", secondary_y=False, tickprefix="$")
        fig.update_yaxes(title_text="Surplus ($)", secondary_y=True, tickprefix="$")
        st.plotly_chart(fig, use_container_width=True)

    latest = parsed_rows[-1]
    st.markdown(
        sec(f"Expense Allocation — {latest_year}",
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
                         height=360, paper_bgcolor="#fff",
                         font=dict(family="Inter, -apple-system, sans-serif", size=12, color="#64748B"))
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
            apply_theme(fb, 360)
            fb.update_layout(margin=dict(l=10, r=80, t=28, b=16),
                             xaxis_title="Amount ($)")
            fb.update_xaxes(tickprefix="$")
            st.plotly_chart(fb, use_container_width=True)
