"""
Investment Detail Page — Tab 3
Cash breakdown, investment returns, return ratios, and cash trend chart.
"""

import streamlit as st
import plotly.graph_objects as go

from core.kpis import INVESTMENT_KPIS
from components.kpi_cards import sec, kpi_html
from components.charts import apply_theme, PAL


def render(parsed_rows, latest_kpis, latest_year):
    st.markdown(
        sec(f"Investment & Asset Detail — {latest_year}",
            "Cash breakdown, investment returns, and real estate assets."),
        unsafe_allow_html=True,
    )
    st.markdown(kpi_html(INVESTMENT_KPIS[:4], latest_kpis), unsafe_allow_html=True)

    st.markdown(
        sec("Investment Returns",
            "Realized gains, unrealized gains, and total investment performance."),
        unsafe_allow_html=True,
    )
    st.markdown(kpi_html(INVESTMENT_KPIS[4:8], latest_kpis), unsafe_allow_html=True)

    st.markdown(
        sec("Return Ratios",
            "Investment returns relative to assets, liquid assets, and expenses."),
        unsafe_allow_html=True,
    )
    st.markdown(kpi_html(INVESTMENT_KPIS[8:], latest_kpis), unsafe_allow_html=True)

    if len(parsed_rows) > 1:
        st.markdown(
            sec("Cash & Savings Trend",
                "Cash and savings positions over time."),
            unsafe_allow_html=True,
        )
        yrs_inv = [r.get("TaxYear", "") for r in parsed_rows]
        fig_cash = go.Figure()
        fig_cash.add_trace(go.Bar(
            x=yrs_inv,
            y=[r.get("CashNonInterest", 0) for r in parsed_rows],
            name="Cash (Non-Interest)", marker_color=PAL[0], marker_cornerradius=4,
        ))
        fig_cash.add_trace(go.Bar(
            x=yrs_inv,
            y=[r.get("SavingsTempCashInvestments", 0) for r in parsed_rows],
            name="Savings & Temp Inv.", marker_color=PAL[1], marker_cornerradius=4,
        ))
        fig_cash.add_trace(go.Bar(
            x=yrs_inv,
            y=[r.get("PublicInvestments", 0) for r in parsed_rows],
            name="Public Securities", marker_color=PAL[2], marker_cornerradius=4,
        ))
        fig_cash.update_layout(barmode="stack", yaxis_title="Amount ($)")
        apply_theme(fig_cash, 380)
        fig_cash.update_yaxes(tickprefix="$")
        st.plotly_chart(fig_cash, use_container_width=True)
