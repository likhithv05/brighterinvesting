"""
Supplement Form Component
Optional form for users to fill in fields that QuickBooks data cannot provide,
such as governance info and the Form 990 functional expense split.
"""

import streamlit as st
from core.quickbooks import apply_supplement_data


def _has_qb_data(parsed_rows):
    """Check if any of the parsed rows come from QuickBooks."""
    return any(r.get("DataSource") == "quickbooks" for r in parsed_rows)


def _get_missing_fields(parsed_rows):
    """Identify which fields are missing (None) in QB data."""
    missing = set()
    for row in parsed_rows:
        if row.get("DataSource") != "quickbooks":
            continue
        for key, value in row.items():
            if value is None:
                missing.add(key)
    return missing


def render_supplement_form(parsed_rows):
    """
    Render the 'Fill in the Gaps' form for QuickBooks data.

    Only appears when QB-sourced data is loaded. Returns the (potentially
    modified) parsed_rows with supplement data applied.
    """
    if not _has_qb_data(parsed_rows):
        return parsed_rows

    missing = _get_missing_fields(parsed_rows)
    if not missing:
        return parsed_rows

    # Check if user already applied supplements this session
    supplement_key = "qb_supplement_data"
    existing_supplement = st.session_state.get(supplement_key)
    if existing_supplement:
        return apply_supplement_data(parsed_rows, existing_supplement)

    # Show the form
    with st.expander("Fill in the Gaps (Optional)", expanded=False):
        st.markdown(
            '<div class="sec-s">'
            "Some fields aren't available from QuickBooks exports. "
            "Fill in what you know to unlock additional KPIs, or skip "
            "this — your data works as-is with available metrics."
            "</div>",
            unsafe_allow_html=True,
        )

        supplement = {}

        # ── Organization Info ──
        any_missing_ein = any(
            not r.get("EIN") for r in parsed_rows
            if r.get("DataSource") == "quickbooks"
        )
        if any_missing_ein or "Mission" in missing:
            st.markdown("**Organization Info**")
            col1, col2 = st.columns(2)
            with col1:
                if any_missing_ein:
                    ein = st.text_input(
                        "EIN (Employer ID Number)",
                        placeholder="XX-XXXXXXX",
                        key="qb_supp_ein",
                    )
                    if ein.strip():
                        supplement["EIN"] = ein.strip()
            with col2:
                if "Mission" in missing:
                    mission = st.text_area(
                        "Mission Statement",
                        placeholder="Brief description of the organization's mission",
                        key="qb_supp_mission",
                        height=80,
                    )
                    if mission.strip():
                        supplement["Mission"] = mission.strip()

        # ── Governance ──
        governance_fields = {
            "VotingBoardMembers", "IndependentBoardMembers",
            "Volunteers", "EmployeeCount", "ExecutiveDirectorCompensation",
        }
        if governance_fields & missing:
            st.markdown("**Governance & Workforce**")
            cols = st.columns(3)
            with cols[0]:
                if "EmployeeCount" in missing:
                    emp = st.number_input(
                        "Number of Employees",
                        min_value=0, step=1, value=None,
                        key="qb_supp_employees",
                    )
                    if emp is not None:
                        supplement["EmployeeCount"] = emp
            with cols[1]:
                if "VotingBoardMembers" in missing:
                    board = st.number_input(
                        "Voting Board Members",
                        min_value=0, step=1, value=None,
                        key="qb_supp_board",
                    )
                    if board is not None:
                        supplement["VotingBoardMembers"] = board
            with cols[2]:
                if "IndependentBoardMembers" in missing:
                    indep = st.number_input(
                        "Independent Board Members",
                        min_value=0, step=1, value=None,
                        key="qb_supp_indep_board",
                    )
                    if indep is not None:
                        supplement["IndependentBoardMembers"] = indep

            col1, col2 = st.columns(2)
            with col1:
                if "Volunteers" in missing:
                    vol = st.number_input(
                        "Number of Volunteers",
                        min_value=0, step=1, value=None,
                        key="qb_supp_volunteers",
                    )
                    if vol is not None:
                        supplement["Volunteers"] = vol
            with col2:
                if "ExecutiveDirectorCompensation" in missing:
                    exec_comp = st.number_input(
                        "Executive Director Compensation ($)",
                        min_value=0, step=1000, value=None,
                        key="qb_supp_exec_comp",
                    )
                    if exec_comp is not None:
                        supplement["ExecutiveDirectorCompensation"] = exec_comp

        # ── Functional Expense Split ──
        functional_fields = {
            "ProgramExpenses", "ManagementGeneralExpenses", "FundraisingExpenses",
        }
        if functional_fields & missing:
            st.markdown("**Functional Expense Split**")
            st.caption(
                "Form 990 requires nonprofits to classify expenses by function. "
                "QuickBooks doesn't track this unless you use Class Tracking. "
                "Enter your best estimates below."
            )

            col1, col2, col3 = st.columns(3)
            with col1:
                prog_pct = st.number_input(
                    "Program Services %",
                    min_value=0.0, max_value=100.0, step=1.0, value=None,
                    help="Percentage of expenses spent directly on programs",
                    key="qb_supp_program_pct",
                )
                if prog_pct is not None:
                    supplement["ProgramExpensePct"] = prog_pct
            with col2:
                mgmt_pct = st.number_input(
                    "Management & General %",
                    min_value=0.0, max_value=100.0, step=1.0, value=None,
                    help="Percentage of expenses spent on administration",
                    key="qb_supp_mgmt_pct",
                )
                if mgmt_pct is not None:
                    supplement["ManagementExpensePct"] = mgmt_pct
            with col3:
                fund_pct = st.number_input(
                    "Fundraising %",
                    min_value=0.0, max_value=100.0, step=1.0, value=None,
                    help="Percentage of expenses spent on fundraising",
                    key="qb_supp_fund_pct",
                )
                if fund_pct is not None:
                    supplement["FundraisingExpensePct"] = fund_pct

            # Validate total doesn't exceed 100%
            entered_pcts = [
                supplement.get("ProgramExpensePct", 0) or 0,
                supplement.get("ManagementExpensePct", 0) or 0,
                supplement.get("FundraisingExpensePct", 0) or 0,
            ]
            total_pct = sum(entered_pcts)
            if total_pct > 100:
                st.warning(
                    f"Percentages total {total_pct:.0f}% — "
                    "they should add up to 100% or less."
                )

        # Apply button
        if supplement:
            if st.button("Apply Supplemental Data", type="primary",
                         key="qb_apply_supplement"):
                st.session_state[supplement_key] = supplement
                st.success("Supplemental data applied. KPIs updated.")
                st.rerun()

    # Apply any existing supplement from session state
    if existing_supplement:
        return apply_supplement_data(parsed_rows, existing_supplement)
    return parsed_rows
