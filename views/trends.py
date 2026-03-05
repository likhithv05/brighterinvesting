"""
Trends Page — Tab 2
Multi-year trend analysis charts for financial KPIs.
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.kpis import compute_kpis, KPI_DEFINITIONS, TREND_KPIS, format_kpi_value
from components.kpi_cards import sec
from components.charts import apply_theme, PAL, ROSE


def render(parsed_rows, kpi_data):
    if len(parsed_rows) < 2:
        st.info("Upload multiple years of data to unlock trend analysis. If you filtered to a single year, switch to 'All Years' or 'Year Range' to see trends.")
        return

    st.markdown(
        sec("Financial Trends",
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
            apply_theme(f, 280)
            if dd.get("format") == "percent":
                f.update_yaxes(tickformat=".1%")
            elif dd.get("format") == "currency":
                f.update_yaxes(tickprefix="$")
            with cols[i % 2]:
                st.plotly_chart(f, use_container_width=True)

    st.markdown(
        sec("Balance Sheet Trend",
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
    apply_theme(fig_bs, 380)
    fig_bs.update_yaxes(tickprefix="$")
    st.plotly_chart(fig_bs, use_container_width=True)

    st.markdown(
        sec("Workforce Trend",
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
    apply_theme(fig_wf, 340)
    fig_wf.update_yaxes(title_text="Employees", secondary_y=False)
    fig_wf.update_yaxes(title_text="Board Members", secondary_y=True)
    st.plotly_chart(fig_wf, use_container_width=True)
