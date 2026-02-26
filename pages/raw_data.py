"""
Raw Data Page — Tab 5
Full extracted data table and KPI summary across all years.
"""

import streamlit as st
import pandas as pd

from core.parser import FIELD_LABELS
from core.kpis import compute_kpis, KPI_DEFINITIONS
from components.kpi_cards import sec, kpi_html


def render(parsed_rows):
    st.markdown(
        sec("Extracted Data",
            "Every field extracted from the uploaded Form 990 XML files."),
        unsafe_allow_html=True,
    )
    raw_df = pd.DataFrame([
        {FIELD_LABELS.get(f, f): r.get(f) for f in FIELD_LABELS if f in r}
        for r in parsed_rows
    ])
    st.dataframe(raw_df, use_container_width=True, hide_index=True, height=500)

    st.markdown(
        sec("KPI Summary — All Years",
            "Computed metrics for every filing year."),
        unsafe_allow_html=True,
    )
    from core.kpis import format_kpi_value
    kpi_display_df = pd.DataFrame([
        {"Year": r.get("TaxYear", "")}
        | {d["label"]: format_kpi_value(k, compute_kpis(r).get(k, 0))
           for k, d in KPI_DEFINITIONS.items()}
        for r in parsed_rows
    ])
    st.dataframe(kpi_display_df, use_container_width=True, hide_index=True)
