"""
Financial Statements Page — Tab 4
Revenue, expense, and balance sheet tables with stacked revenue chart.
"""

import streamlit as st
import plotly.graph_objects as go

from core.parser import FIELD_LABELS
from components.kpi_cards import sec, fin_table
from components.charts import apply_theme, PAL


def render(parsed_rows):
    all_years = [r.get("TaxYear", "") for r in parsed_rows]

    st.markdown(
        sec("Revenue by Year", "All revenue sources across filing years."),
        unsafe_allow_html=True,
    )
    st.markdown(fin_table("Revenue by Year", all_years, [
        {"label": "Contributions & Grants", "key": "TotalContributionsGrants"},
        {"label": "Program Service Revenue", "key": "ProgramServiceRevenue"},
        {"label": "Investment Income", "key": "InvestmentIncome"},
        {"label": "Other Revenue", "key": "OtherRevenue"},
        {"label": "Total Revenue", "key": "TotalRevenue"},
    ], parsed_rows), unsafe_allow_html=True)

    if len(parsed_rows) > 1:
        rev_years = [r.get("TaxYear", "") for r in parsed_rows]
        fig_r = go.Figure()
        for src, clr in [
            ("TotalContributionsGrants", PAL[0]),
            ("ProgramServiceRevenue", PAL[5]),
            ("InvestmentIncome", PAL[2]),
            ("OtherRevenue", PAL[3]),
        ]:
            fig_r.add_trace(go.Bar(
                x=rev_years,
                y=[r.get(src, 0) for r in parsed_rows],
                name=FIELD_LABELS.get(src, src),
                marker_color=clr, marker_cornerradius=4,
            ))
        fig_r.update_layout(barmode="stack", yaxis_title="Amount ($)")
        apply_theme(fig_r, 380)
        fig_r.update_yaxes(tickprefix="$")
        st.plotly_chart(fig_r, use_container_width=True)

    st.markdown(
        sec("Expenses by Year", "Functional and line-item expense breakdown."),
        unsafe_allow_html=True,
    )
    st.markdown(fin_table("Expenses by Year", all_years, [
        {"label": "Program Expenses", "key": "ProgramExpenses"},
        {"label": "Management & General", "key": "ManagementGeneralExpenses"},
        {"label": "Fundraising", "key": "FundraisingExpenses"},
        {"label": "Salaries & Wages", "key": "SalariesWages"},
        {"label": "Grants Paid", "key": "GrantsAndSimilarPaid"},
        {"label": "Total Expenses", "key": "TotalExpenses"},
    ], parsed_rows), unsafe_allow_html=True)

    st.markdown(
        sec("Balance Sheet by Year",
            "Assets, liabilities, and net asset composition."),
        unsafe_allow_html=True,
    )
    st.markdown(fin_table("Balance Sheet by Year", all_years, [
        {"label": "Total Assets", "key": "TotalAssets"},
        {"label": "Total Liabilities", "key": "TotalLiabilities"},
        {"label": "Net Assets (Unrestricted)", "key": "NetAssetsWithoutDonorRestrictions"},
        {"label": "Net Assets (Restricted)", "key": "NetAssetsWithDonorRestrictions"},
        {"label": "Total Net Assets", "key": "TotalNetAssets"},
    ], parsed_rows), unsafe_allow_html=True)
