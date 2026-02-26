"""
Sidebar Component
Handles data source selection (Upload XML, ProPublica, QuickBooks),
saved organizations, tag management, admin panel toggle, and logout.
"""

import os
import streamlit as st

from components.header import get_logo_tags
from core.parser import parse_single_xml
from core.db_utils import (
    init_extended_db,
    save_organization,
    load_user_organizations,
    delete_organization,
    clear_remember_me_token,
    create_tag,
    get_user_tags,
    delete_tag,
    assign_tag,
    remove_tag_from_org,
    get_tags_for_org,
    get_orgs_by_tag,
    TAG_COLORS,
)
from core.propublica import (
    search_nonprofits,
    get_organization_filings,
    fetch_filing_xml,
    format_filing_year,
    format_revenue,
)
from core.login import show_admin_panel


@st.cache_data
def load_demo(path):
    rows = []
    for fn in sorted(os.listdir(path)):
        if fn.lower().endswith(".xml"):
            with open(os.path.join(path, fn), "rb") as f:
                try:
                    rows.append(parse_single_xml(f.read(), filename=fn))
                except Exception:
                    pass
    return rows


def load_uploads(files):
    rows, errs = [], []
    for f in files:
        try:
            rows.append(parse_single_xml(f.read(), filename=f.name))
        except Exception as e:
            errs.append((f.name, str(e)))
    return rows, errs


def render_sidebar():
    """
    Render the full sidebar and return (all_parsed_rows, parse_errors).
    Also handles admin panel display and logout.
    """
    _, logo_tag_sm = get_logo_tags()
    user_id = st.session_state.get("user_id")

    with st.sidebar:
        st.markdown(f"""
        <div class="sb-brand">
            {logo_tag_sm}
            <div class="sb-lbl">Analyzer</div>
        </div>
        """, unsafe_allow_html=True)

        # ── DATA SOURCE TABS ──
        data_tab = st.radio(
            "Data Source",
            ["Upload XML", "Search ProPublica", "QuickBooks"],
            horizontal=True,
            label_visibility="collapsed",
        )

        uploaded_files = []
        use_demo = False
        demo_dir = ""
        demo_available = False

        # ════════ UPLOAD XML ════════
        if data_tab == "Upload XML":
            st.markdown("""
            <div class="sb-upload-zone">
                <div class="sb-upload-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/>
                    </svg>
                </div>
                <div class="sb-upload-title">Upload Form 990 XMLs</div>
                <div class="sb-upload-sub">Drop files below or click to browse.<br>Supports multiple files from different organizations.</div>
            </div>
            """, unsafe_allow_html=True)

            uploaded_files = st.file_uploader(
                "Drop XML files here",
                type=["xml"],
                accept_multiple_files=True,
                label_visibility="collapsed",
                help="Select IRS Form 990 XML files. You can upload files from multiple different nonprofits at once.",
            )

            demo_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..", "..", "Form 990 Parser", "Data Engineering 2.6.2026",
                "Final_Model_Files", "Habitat for Humanity Test Data",
            )
            demo_available = os.path.isdir(demo_dir)
            if demo_available:
                st.markdown('<div class="sb-or">or try a sample</div>', unsafe_allow_html=True)
                use_demo = st.checkbox(
                    "Load demo data (Habitat for Humanity)",
                    help="Load 9 years of Habitat for Humanity International Form 990 filings.",
                )

        # ════════ PROPUBLICA SEARCH ════════
        elif data_tab == "Search ProPublica":
            st.markdown('<div class="sb-section-title">Search Nonprofits</div>', unsafe_allow_html=True)
            st.markdown(
                '<p class="sb-section-desc">Search by organization name or EIN. '
                'Select years to load their Form 990 data directly.</p>',
                unsafe_allow_html=True,
            )

            pp_query = st.text_input(
                "Organization name or EIN",
                placeholder="e.g. Habitat for Humanity, 91-1914868",
                key="pp_search_input",
            )

            if st.button("Search", key="pp_search_btn", use_container_width=True, type="primary"):
                if pp_query.strip():
                    with st.spinner("Searching ProPublica..."):
                        results = search_nonprofits(pp_query.strip())
                        st.session_state["propublica_results"] = results

            results = st.session_state.get("propublica_results")
            if results and results.get("organizations"):
                orgs = results["organizations"]
                total = results.get("total_results", len(orgs))
                st.caption(f"Found {total:,} result{'s' if total != 1 else ''}")

                for org in orgs[:10]:
                    name = org.get("name", "Unknown")
                    ein_val = org.get("ein", "")
                    city = org.get("city", "")
                    state = org.get("state", "")
                    revenue = org.get("income_amount")
                    loc = f"{city}, {state}" if city and state else (city or state or "")

                    st.markdown(f"""
                    <div class="pp-card">
                        <div class="pp-name">{name}</div>
                        <div class="pp-meta">
                            <span>EIN: {ein_val}</span>
                            <span>{loc}</span>
                            {f'<span>Revenue: {format_revenue(revenue)}</span>' if revenue else ''}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    if st.button(f"Select \u2192 {name[:30]}", key=f"pp_select_{ein_val}", use_container_width=True):
                        st.session_state["propublica_selected_ein"] = ein_val
                        with st.spinner(f"Loading filings for {name}..."):
                            filings_data = get_organization_filings(ein_val)
                            st.session_state["propublica_filings"] = filings_data
                        st.rerun()

            # Show filing year selection if we have filings
            filings_data = st.session_state.get("propublica_filings")
            selected_ein_pp = st.session_state.get("propublica_selected_ein")
            if filings_data and selected_ein_pp:
                org_info = filings_data.get("organization", {})
                filings = filings_data.get("filings_with_data", [])

                if filings:
                    org_n = org_info.get("name", "Selected Organization")
                    st.markdown(f'<div class="sb-section-title">{org_n}</div>', unsafe_allow_html=True)

                    year_options = []
                    filing_map = {}
                    for f in filings:
                        yr = format_filing_year(f)
                        xml_url = f.get("xml_url")
                        if xml_url and yr != "Unknown":
                            year_options.append(yr)
                            filing_map[yr] = f

                    if year_options:
                        selected_years = st.multiselect(
                            "Select filing years to load",
                            year_options,
                            default=year_options[:3],
                            key="pp_year_select",
                        )

                        if st.button("Load Selected Filings", key="pp_load_filings", type="primary", use_container_width=True):
                            if selected_years:
                                with st.spinner(f"Downloading {len(selected_years)} filing(s)..."):
                                    loaded_rows = []
                                    errors = []
                                    for yr in selected_years:
                                        f = filing_map.get(yr)
                                        if f and f.get("xml_url"):
                                            xml_bytes = fetch_filing_xml(f["xml_url"])
                                            if xml_bytes:
                                                try:
                                                    row = parse_single_xml(xml_bytes, filename=f"ProPublica_{selected_ein_pp}_{yr}.xml")
                                                    loaded_rows.append(row)
                                                except Exception as e:
                                                    errors.append((yr, str(e)))
                                            else:
                                                errors.append((yr, "Failed to download XML"))

                                    if loaded_rows:
                                        if user_id:
                                            save_organization(user_id, loaded_rows)
                                        st.session_state["pp_loaded_rows"] = loaded_rows
                                        st.success(f"Loaded {len(loaded_rows)} filing(s) successfully!")
                                        st.rerun()
                                    if errors:
                                        for yr, err in errors:
                                            st.error(f"Year {yr}: {err}")
                    else:
                        st.warning("No filings with XML data available for this organization.")
                else:
                    st.warning("No filings found for this organization.")

        # ════════ QUICKBOOKS ════════
        elif data_tab == "QuickBooks":
            st.markdown("""
            <div class="qb-banner">
                <div class="qb-title">QuickBooks Integration</div>
                <div class="qb-desc">Coming Soon</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown('<div class="sb-section-title">Connect QuickBooks</div>', unsafe_allow_html=True)
            st.markdown(
                '<p class="sb-section-desc">'
                'Import financial data directly from QuickBooks Online to compare '
                'against Form 990 filings and track real-time financials.</p>',
                unsafe_allow_html=True,
            )

            st.info(
                "QuickBooks integration is under development. "
                "This will allow you to connect your QuickBooks Online account "
                "and pull in real-time financial data for comparison with 990 filings."
            )

            st.markdown(
                "**Planned features:**\n"
                "- OAuth2 secure connection to QuickBooks Online\n"
                "- Import P&L, Balance Sheet, and Cash Flow statements\n"
                "- Side-by-side comparison with Form 990 data\n"
                "- Reconciliation tools for audit preparation"
            )

        # ── Saved Organizations Section ──
        saved_orgs = {}
        if user_id:
            saved_orgs = load_user_organizations(user_id)

        if saved_orgs:
            st.markdown('<div class="sb-or">saved organizations</div>', unsafe_allow_html=True)

            tag_filter_eins = st.session_state.get("tag_filter_eins")
            display_orgs = saved_orgs
            if tag_filter_eins:
                display_orgs = {k: v for k, v in saved_orgs.items() if k in tag_filter_eins}
                if not display_orgs:
                    st.caption("No organizations match this category filter.")

            for s_ein, s_info in display_orgs.items():
                yrs = ", ".join(s_info["years"][-3:])
                if len(s_info["years"]) > 3:
                    yrs = f"{s_info['years'][0]}\u2013{s_info['years'][-1]}"

                if user_id:
                    org_tags = get_tags_for_org(user_id, s_ein)
                    if org_tags:
                        badges = ""
                        for ot in org_tags:
                            c = ot["tag_color"]
                            r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
                            bg = f"rgba({r},{g},{b},.12)"
                            badges += f'<span class="tag-badge" style="background:{bg};color:{c};font-size:.55rem;">{ot["tag_name"]}</span> '
                        st.markdown(f'<div style="margin:2px 0 -6px;">{badges}</div>', unsafe_allow_html=True)

                col_load, col_del = st.columns([3, 1])
                with col_load:
                    if st.button(
                        f"\U0001F4C2 {s_info['name'][:25]} ({yrs})",
                        key=f"load_saved_{s_ein}",
                        use_container_width=True,
                    ):
                        st.session_state["selected_ein"] = s_ein
                        st.session_state["selected_org_name"] = s_info["name"]
                with col_del:
                    if st.button("\U0001F5D1", key=f"del_saved_{s_ein}"):
                        delete_organization(user_id, s_ein)
                        st.rerun()

        # ── Tags / Categories Section ──
        if user_id and saved_orgs:
            st.markdown('<div class="sb-or">tags &amp; categories</div>', unsafe_allow_html=True)
            user_tags = get_user_tags(user_id)

            if user_tags:
                tag_html = '<div class="tag-row">'
                for t in user_tags:
                    color = t["tag_color"]
                    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
                    bg = f"rgba({r},{g},{b},.12)"
                    tag_html += (
                        f'<span class="tag-badge" style="background:{bg};color:{color};">'
                        f'{t["tag_name"]}</span>'
                    )
                tag_html += '</div>'
                st.markdown(tag_html, unsafe_allow_html=True)

                tag_names = ["All Organizations"] + [t["tag_name"] for t in user_tags]
                filter_tag = st.selectbox(
                    "Filter by category",
                    tag_names,
                    key="filter_tag_select",
                    label_visibility="collapsed",
                )
                if filter_tag != "All Organizations":
                    tag_obj = next((t for t in user_tags if t["tag_name"] == filter_tag), None)
                    if tag_obj:
                        filtered_eins = get_orgs_by_tag(user_id, tag_obj["id"])
                        if filtered_eins:
                            st.session_state["tag_filter_eins"] = filtered_eins
                        else:
                            st.session_state["tag_filter_eins"] = None
                            st.caption("No organizations in this category yet.")
                else:
                    st.session_state["tag_filter_eins"] = None

            with st.expander("Manage Tags"):
                new_tag_name = st.text_input(
                    "New category name",
                    placeholder="e.g. University Endowments",
                    key="new_tag_input",
                )
                col_color, col_btn = st.columns([1, 1])
                with col_color:
                    color_opts = {name: hex_c for hex_c, name in TAG_COLORS}
                    sel_color_name = st.selectbox("Color", list(color_opts.keys()), key="new_tag_color")
                    sel_color = color_opts[sel_color_name]
                with col_btn:
                    st.write("")
                    if st.button("Add Tag", key="add_tag_btn", use_container_width=True):
                        if new_tag_name.strip():
                            result = create_tag(user_id, new_tag_name.strip(), sel_color)
                            if result:
                                st.success(f"Created '{new_tag_name.strip()}'")
                                st.rerun()
                            else:
                                st.error("Tag already exists.")

                if user_tags:
                    del_tag = st.selectbox(
                        "Remove tag",
                        [t["tag_name"] for t in user_tags],
                        key="del_tag_select",
                    )
                    if st.button("Delete Tag", key="del_tag_btn"):
                        tag_obj = next((t for t in user_tags if t["tag_name"] == del_tag), None)
                        if tag_obj:
                            delete_tag(user_id, tag_obj["id"])
                            st.rerun()

                if user_tags and saved_orgs:
                    st.markdown("---")
                    st.caption("Assign tags to organizations")
                    assign_ein = st.selectbox(
                        "Organization",
                        [f"{info['name']} ({ein})" for ein, info in saved_orgs.items()],
                        key="assign_org_select",
                    )
                    assign_ein_val = assign_ein.split("(")[-1].rstrip(")")
                    current_tags = get_tags_for_org(user_id, assign_ein_val)
                    current_tag_ids = {t["id"] for t in current_tags}

                    available_tags = [t for t in user_tags if t["id"] not in current_tag_ids]
                    if available_tags:
                        add_tag_sel = st.selectbox(
                            "Add tag",
                            [t["tag_name"] for t in available_tags],
                            key="assign_tag_select",
                        )
                        if st.button("Assign", key="assign_tag_btn"):
                            tag_obj = next((t for t in available_tags if t["tag_name"] == add_tag_sel), None)
                            if tag_obj:
                                assign_tag(user_id, assign_ein_val, tag_obj["id"])
                                st.rerun()

                    if current_tags:
                        rm_tag_sel = st.selectbox(
                            "Remove tag from org",
                            [t["tag_name"] for t in current_tags],
                            key="remove_tag_select",
                        )
                        if st.button("Remove", key="remove_tag_btn"):
                            tag_obj = next((t for t in current_tags if t["tag_name"] == rm_tag_sel), None)
                            if tag_obj:
                                remove_tag_from_org(user_id, assign_ein_val, tag_obj["id"])
                                st.rerun()

        st.markdown(
            '<div class="sb-credits">'
            'Developed by <b>Epic Intentions</b><br>'
            "for Brighter Investing<br>"
            "Georgia Tech \u00b7 Spring 2026"
            "</div>",
            unsafe_allow_html=True,
        )

        # ── Admin & Logout ──
        if st.session_state.get("role") == "admin":
            if st.button("\u2699 Admin Panel", use_container_width=True):
                st.session_state["show_admin"] = not st.session_state.get("show_admin", False)
                st.rerun()

        if st.button("Logout", use_container_width=True):
            uid = st.session_state.get("user_id")
            if uid:
                clear_remember_me_token(uid)
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    # ─── Admin Panel (rendered in main area) ───
    if st.session_state.get("show_admin") and st.session_state.get("role") == "admin":
        show_admin_panel()
        st.markdown("---")

    # ─── Load Data ───
    all_parsed_rows, parse_errors = [], []

    if data_tab == "Upload XML" and uploaded_files:
        all_parsed_rows, parse_errors = load_uploads(uploaded_files)
        if all_parsed_rows and user_id:
            save_organization(user_id, all_parsed_rows)
    elif data_tab == "Upload XML" and use_demo and demo_available:
        all_parsed_rows = load_demo(demo_dir)
    elif "pp_loaded_rows" in st.session_state and st.session_state["pp_loaded_rows"]:
        all_parsed_rows = st.session_state["pp_loaded_rows"]
    elif st.session_state.get("selected_ein") and saved_orgs:
        s_ein = st.session_state["selected_ein"]
        if s_ein in saved_orgs:
            all_parsed_rows = saved_orgs[s_ein]["parsed_data"]

    return all_parsed_rows, parse_errors
