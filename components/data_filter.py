"""
Data Filtering Component
Handles duplicate detection, organization selection, year filtering,
and comparison mode. Returns the final filtered parsed_rows and ein_map.
"""

import streamlit as st
from core.db_utils import detect_duplicates


def apply_filters(all_parsed_rows, parse_errors):
    """
    Run duplicate detection, org selection, year filtering, and comparison setup.

    Returns:
        (parsed_rows, ein_map) — filtered rows and the full EIN-grouped map
    """
    if parse_errors:
        with st.expander(f"\u26a0 {len(parse_errors)} file(s) could not be parsed"):
            for fn, err in parse_errors:
                st.error(f"**{fn}:** {err}")

    if not all_parsed_rows:
        return [], {}

    # Duplicate detection
    dupes = detect_duplicates(all_parsed_rows)
    if dupes:
        with st.expander(f"\u26a0 {len(dupes)} duplicate(s) detected \u2014 click to resolve"):
            for dup in dupes:
                st.warning(
                    f"**{dup['ein']}** \u2014 Tax Year **{dup['year']}** "
                    f"appears in {len(dup['files'])} files: {', '.join(dup['files'])}"
                )
                cols = st.columns(len(dup["indices"]))
                for ci, idx in enumerate(dup["indices"]):
                    with cols[ci]:
                        if st.button(f"Keep {dup['files'][ci]}",
                                     key=f"dup_keep_{dup['ein']}_{dup['year']}_{ci}"):
                            for ri in sorted([j for j in dup["indices"] if j != idx], reverse=True):
                                if ri < len(all_parsed_rows):
                                    all_parsed_rows.pop(ri)
                            st.rerun()

    # Group by EIN
    ein_map = {}
    for row in all_parsed_rows:
        ein = row.get("EIN", "unknown")
        if ein not in ein_map:
            ein_map[ein] = {"name": row.get("OrganizationName", "Unknown"), "rows": []}
        ein_map[ein]["rows"].append(row)

    ein_list = list(ein_map.keys())
    selected_ein = ein_list[0]

    # Multi-org selector
    if len(ein_list) > 1:
        st.info(f"\U0001f4ca **{len(ein_list)} organizations detected** \u2014 "
                "Select which one to analyze below, or enable comparison mode.")
        org_options = {f"{info['name']} ({ein})": ein for ein, info in ein_map.items()}
        selected_label = st.selectbox("Select Organization", list(org_options.keys()),
                                      help="Choose which organization to analyze.")
        selected_ein = org_options[selected_label]

        st.session_state["ui_comparison_mode"] = st.checkbox(
            "Compare with another organization",
            value=st.session_state.get("ui_comparison_mode", False))
        if st.session_state["ui_comparison_mode"]:
            comp_options = {k: v for k, v in org_options.items() if v != selected_ein}
            if comp_options:
                comp_label = st.selectbox("Compare against", list(comp_options.keys()),
                                          key="comp_org_select")
                st.session_state["data_comparison_ein"] = comp_options[comp_label]
            else:
                st.info("Upload files for a second organization to enable comparison.")
                st.session_state["ui_comparison_mode"] = False

    st.session_state["data_selected_ein"] = selected_ein

    # Year filtering
    org_rows = sorted(ein_map[selected_ein]["rows"], key=lambda r: r.get("TaxYear", ""))
    available_years = sorted(set(r.get("TaxYear", "") for r in org_rows))

    if len(available_years) > 1:
        year_mode = st.radio("Year View", ["All Years", "Single Year", "Year Range"],
                             horizontal=True, key="year_filter_mode_radio")
        if year_mode == "Single Year":
            sel_year = st.selectbox("Select Year", available_years,
                                    index=len(available_years) - 1, key="single_year_select")
            org_rows = [r for r in org_rows if r.get("TaxYear") == sel_year]
        elif year_mode == "Year Range":
            year_ints = [int(y) for y in available_years if y.isdigit()]
            if len(year_ints) >= 2:
                yr_min, yr_max = st.slider("Year Range", min_value=min(year_ints),
                                           max_value=max(year_ints),
                                           value=(min(year_ints), max(year_ints)),
                                           key="year_range_slider")
                org_rows = [r for r in org_rows
                            if r.get("TaxYear", "").isdigit()
                            and yr_min <= int(r["TaxYear"]) <= yr_max]

    return org_rows, ein_map
