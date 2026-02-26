"""
Scenario Forecasting Page — Tab 7
Placeholder for future forecasting functionality.
"""

import streamlit as st
from components.kpi_cards import sec


def render(parsed_rows):
    st.markdown(
        sec("Scenario Forecasting",
            "Model future financial outcomes based on historical trends and custom assumptions."),
        unsafe_allow_html=True,
    )

    st.info(
        "Scenario forecasting is under development. "
        "This feature will allow you to project revenue, expenses, and key KPIs "
        "based on historical growth rates and custom what-if assumptions."
    )

    st.markdown(
        "**Planned features:**\n"
        "- Revenue and expense trend projection (linear, CAGR)\n"
        "- Custom growth rate assumptions per line item\n"
        "- Multi-year forecast with confidence intervals\n"
        "- Side-by-side scenario comparison (optimistic / base / conservative)\n"
        "- Exportable forecast reports"
    )
