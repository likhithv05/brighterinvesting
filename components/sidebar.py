"""
Sidebar Component
Handles data source selection, saved organizations,
tag management, account settings, admin panel, and role enforcement.
"""

import os
import streamlit as st

from components.header import get_logo_tags
from core.parser import parse_single_xml
from core.db_utils import (
    save_organization,
    load_user_organizations,
    delete_organization,
    create_tag,
    get_user_tags,
    delete_tag,
    assign_tag,
    remove_tag_from_org,
    get_tags_for_org,
    get_orgs_by_tag,
    get_system_stats,
    TAG_COLORS,
)
from core.propublica import (
    search_nonprofits,
    get_organization_filings,
    fetch_filing_xml,
    format_filing_year,
)
from components.admin_panel import render_admin_panel
from components.account_settings import render_account_settings


# ─── Data Loading Helpers ───

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


_MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB


def load_uploads(files):
    rows, errs = [], []
    for i, f in enumerate(files):
        # Check file extension
        if not f.name.lower().endswith(".xml"):
            errs.append((f.name, "Not an XML file. Only Form 990 XML files are supported."))
            continue
        # Read and check size
        raw = f.read()
        if len(raw) > _MAX_UPLOAD_SIZE:
            errs.append((f.name, f"File is too large ({len(raw) / (1024*1024):.1f} MB). Maximum is 50 MB."))
            continue
        try:
            rows.append(parse_single_xml(raw, filename=f.name))
        except Exception as e:
            errs.append((f.name, str(e)))
    return rows, errs


def _section_label(text):
    """Render a small uppercase section label in the sidebar."""
    st.markdown(
        f'<div style="font-size:0.65rem;font-weight:600;color:#94A3B8;'
        f'letter-spacing:0.05em;text-transform:uppercase;margin:8px 0 4px;">'
        f'{text}</div>',
        unsafe_allow_html=True,
    )


# ─── Data Source Resolution ───

def _resolve_data(data_tab, uploaded_files, use_demo, demo_dir,
                  demo_available, saved_orgs, user_id):
    """Pick the active data source and return (rows, errors)."""
    if data_tab == "Upload XML" and uploaded_files:
        with st.spinner(f"Parsing {len(uploaded_files)} file(s)…"):
            rows, errors = load_uploads(uploaded_files)
        if rows and user_id:
            save_organization(user_id, rows)
            st.session_state["_orgs_dirty"] = True
        st.session_state["pp_loaded_rows"] = None
        return rows, errors

    if data_tab == "Upload XML" and use_demo and demo_available:
        st.session_state["pp_loaded_rows"] = None
        return load_demo(demo_dir), []

    if st.session_state.get("pp_loaded_rows"):
        return st.session_state["pp_loaded_rows"], []

    selected_ein = st.session_state.get("data_selected_ein")
    if selected_ein and selected_ein in saved_orgs:
        return saved_orgs[selected_ein]["parsed_data"], []

    return [], []


# ─── ProPublica Search Section ───

def _render_propublica(user_id):
    """Render the ProPublica search UI. Stores loaded rows in session state."""
    pp_query = st.text_input(
        "Search nonprofits",
        placeholder="Organization name or EIN",
        key="pp_search_input",
    )

    if st.button("Search", key="pp_search_btn", use_container_width=True,
                 type="primary"):
        if pp_query.strip():
            with st.spinner("Searching..."):
                results = search_nonprofits(pp_query.strip())
                st.session_state["pp_search_results"] = results
                st.session_state["pp_selected_ein"] = None
                st.session_state["pp_filings"] = None

    results = st.session_state.get("pp_search_results")
    if not results:
        return
    # Show API errors
    if results.get("error"):
        st.error(results["error"])
        return
    if not results.get("organizations"):
        query_text = st.session_state.get("pp_search_input", "").strip()
        st.warning(
            f"No organizations found for '{query_text}'. "
            "Try a different name or search by EIN."
        )
        return

    orgs = results["organizations"][:10]
    total = results.get("total_results", len(orgs))
    st.caption(f"{total:,} result{'s' if total != 1 else ''}")

    # Selectbox instead of individual HTML cards + buttons
    org_labels = []
    org_ein_map = {}
    for o in orgs:
        name = o.get("name", "Unknown")
        city = o.get("city", "")
        state = o.get("state", "")
        ein = o.get("ein", "")
        loc = f"{city}, {state}" if city and state else (city or state or "")
        label = f"{name} ({loc}) \u2014 EIN: {ein}" if loc else f"{name} \u2014 EIN: {ein}"
        org_labels.append(label)
        org_ein_map[label] = ein

    selected_label = st.selectbox(
        "Select organization",
        org_labels,
        index=None,
        placeholder="Choose an organization\u2026",
        key="pp_org_select",
    )

    if not selected_label:
        return

    ein_val = org_ein_map.get(selected_label, "")
    if not ein_val:
        return

    # Auto-fetch filings when org selection changes
    if ein_val != st.session_state.get("pp_selected_ein"):
        st.session_state["pp_selected_ein"] = ein_val
        with st.spinner("Loading available filings\u2026"):
            filings_data = get_organization_filings(ein_val)
            st.session_state["pp_filings"] = filings_data

    filings_data = st.session_state.get("pp_filings")
    if not filings_data:
        return
    if filings_data.get("error"):
        st.error(filings_data["error"])
        return

    filings = filings_data.get("filings_with_data", [])
    if not filings:
        st.warning("No filings with XML data found.")
        return

    year_options = []
    filing_map = {}
    for f in filings:
        yr = format_filing_year(f)
        xml_url = f.get("xml_url")
        if xml_url and yr != "Unknown":
            year_options.append(yr)
            filing_map[yr] = f

    if not year_options:
        st.warning("No filing years available.")
        return

    selected_years = st.multiselect(
        "Years to load",
        year_options,
        default=year_options[:3],
        key=f"pp_years_{ein_val}",
    )

    if not st.button("Load Filings", key="pp_load_filings", type="primary",
                     use_container_width=True):
        return

    if not selected_years:
        st.warning("Select at least one year.")
        return

    with st.spinner(f"Downloading {len(selected_years)} filing(s)\u2026"):
        loaded_rows, errors = [], []
        for yr in selected_years:
            filing = filing_map.get(yr)
            if filing and filing.get("xml_url"):
                xml_bytes = fetch_filing_xml(filing["xml_url"])
                if xml_bytes:
                    try:
                        row = parse_single_xml(
                            xml_bytes,
                            filename=f"ProPublica_{ein_val}_{yr}.xml",
                        )
                        loaded_rows.append(row)
                    except Exception as e:
                        errors.append((yr, str(e)))
                else:
                    errors.append((yr, "Failed to download XML"))

        if loaded_rows:
            if user_id:
                save_organization(user_id, loaded_rows)
                st.session_state["_orgs_dirty"] = True
            st.session_state["pp_loaded_rows"] = loaded_rows
            st.success(f"Loaded {len(loaded_rows)} filing(s)")
            st.rerun()
        for yr, err in errors:
            st.error(f"{yr}: {err}")


# ─── Saved Organizations Section ───

def _render_saved_orgs(saved_orgs, user_id):
    """Render the saved organizations list inside an expander."""
    tag_filter_eins = st.session_state.get("data_tag_filter_eins")
    display_orgs = saved_orgs
    if tag_filter_eins:
        display_orgs = {k: v for k, v in saved_orgs.items()
                        if k in tag_filter_eins}
        if not display_orgs:
            st.caption("No organizations match this filter.")

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
                    badges += (
                        f'<span class="tag-badge" style="background:{bg};'
                        f'color:{c};font-size:.55rem;">'
                        f'{ot["tag_name"]}</span> '
                    )
                st.markdown(
                    f'<div style="margin:2px 0 -6px;">{badges}</div>',
                    unsafe_allow_html=True,
                )

        col_load, col_del = st.columns([3, 1])
        with col_load:
            if st.button(
                f"{s_info['name'][:25]}{'…' if len(s_info['name']) > 25 else ''} ({yrs})",
                key=f"load_saved_{s_ein}",
                use_container_width=True,
            ):
                st.session_state["data_selected_ein"] = s_ein
                st.session_state["pp_loaded_rows"] = None
                st.rerun()
        with col_del:
            if st.button("\U0001F5D1", key=f"del_saved_{s_ein}"):
                delete_organization(user_id, s_ein)
                st.session_state["_orgs_dirty"] = True
                st.rerun()


# ─── Tags & Categories Section ───

def _render_tags(user_id, saved_orgs):
    """Render tag management UI inside an expander."""
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
            tag_obj = next(
                (t for t in user_tags if t["tag_name"] == filter_tag), None
            )
            if tag_obj:
                filtered_eins = get_orgs_by_tag(user_id, tag_obj["id"])
                st.session_state["data_tag_filter_eins"] = filtered_eins or None
                if not filtered_eins:
                    st.caption("No organizations in this category.")
        else:
            st.session_state["data_tag_filter_eins"] = None

    # ── Create tag ──
    st.markdown("---")
    new_tag_name = st.text_input(
        "New category name",
        placeholder="e.g. University Endowments",
        key="new_tag_input",
    )
    col_color, col_btn = st.columns([1, 1])
    with col_color:
        color_opts = {name: hex_c for hex_c, name in TAG_COLORS}
        sel_color_name = st.selectbox(
            "Color", list(color_opts.keys()), key="new_tag_color"
        )
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

    # ── Delete tag ──
    if user_tags:
        del_tag_name = st.selectbox(
            "Remove tag",
            [t["tag_name"] for t in user_tags],
            key="del_tag_select",
        )
        if st.button("Delete Tag", key="del_tag_btn"):
            tag_obj = next(
                (t for t in user_tags if t["tag_name"] == del_tag_name), None
            )
            if tag_obj:
                delete_tag(user_id, tag_obj["id"])
                st.rerun()

    # ── Assign / remove tags from orgs ──
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
                tag_obj = next(
                    (t for t in available_tags if t["tag_name"] == add_tag_sel),
                    None,
                )
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
                tag_obj = next(
                    (t for t in current_tags if t["tag_name"] == rm_tag_sel),
                    None,
                )
                if tag_obj:
                    remove_tag_from_org(user_id, assign_ein_val, tag_obj["id"])
                    st.rerun()


# ─── Main Entry Point ───

def render_sidebar():
    """
    Render the full sidebar and return (all_parsed_rows, parse_errors).
    """
    _, logo_tag_sm = get_logo_tags()
    user_id = st.session_state.get("auth_user_id")

    # Cache saved orgs in session state; reload only when flagged dirty
    if "data_saved_orgs" not in st.session_state or st.session_state.get("_orgs_dirty"):
        st.session_state["data_saved_orgs"] = load_user_organizations(user_id) if user_id else {}
        st.session_state.pop("_orgs_dirty", None)
    saved_orgs = st.session_state.get("data_saved_orgs", {})

    with st.sidebar:
        # ── Brand ──
        st.markdown(
            f'<div class="sb-brand">{logo_tag_sm}'
            f'<div class="sb-lbl">Analyzer</div></div>',
            unsafe_allow_html=True,
        )

        # Reserve a slot for the "Currently loaded" indicator.
        # We fill it AFTER resolving data so it reflects this render cycle.
        indicator_slot = st.empty()

        # ── Admin System Info (admin only) ──
        if st.session_state.get("auth_role") == "admin":
            stats = get_system_stats()
            st.markdown(
                f'<div style="font-size:0.65rem;color:#64748B;'
                f'background:#F8FAFC;border-radius:6px;padding:6px 10px;'
                f'margin-bottom:8px;">'
                f'<span style="font-weight:600;color:#0F172A;">System</span>'
                f' &middot; {stats["total_users"]} user'
                f'{"s" if stats["total_users"] != 1 else ""}'
                f' &middot; {stats["total_saved_orgs"]} saved org'
                f'{"s" if stats["total_saved_orgs"] != 1 else ""}'
                f'</div>',
                unsafe_allow_html=True,
            )

        # ── Data Source Toggle ──
        _section_label("Data Source")
        data_tab = st.radio(
            "Source",
            ["Upload XML", "Search ProPublica"],
            horizontal=True,
            label_visibility="collapsed",
        )

        uploaded_files = []
        use_demo = False
        demo_dir = ""
        demo_available = False

        if data_tab == "Upload XML":
            st.markdown(
                '<div class="sb-upload-zone">'
                '<div class="sb-upload-icon">'
                '<svg xmlns="http://www.w3.org/2000/svg" fill="none" '
                'viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">'
                '<path stroke-linecap="round" stroke-linejoin="round" '
                'd="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 '
                '0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/>'
                '</svg></div>'
                '<div class="sb-upload-title">Upload Form 990 XMLs</div>'
                '<div class="sb-upload-sub">Drop files or click to browse'
                '</div></div>',
                unsafe_allow_html=True,
            )

            uploaded_files = st.file_uploader(
                "Upload XMLs",
                type=["xml"],
                accept_multiple_files=True,
                label_visibility="collapsed",
            )

            demo_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..", "..", "Form 990 Parser", "Data Engineering 2.6.2026",
                "Final_Model_Files", "Habitat for Humanity Test Data",
            )
            demo_available = os.path.isdir(demo_dir)
            if demo_available:
                use_demo = st.checkbox("Load demo data (Habitat for Humanity)")

        else:  # Search ProPublica
            _render_propublica(user_id)

        # ── Resolve Data Source ──
        all_parsed_rows, parse_errors = _resolve_data(
            data_tab, uploaded_files, use_demo, demo_dir,
            demo_available, saved_orgs, user_id,
        )

        # ── Fill the "Currently Loaded" indicator ──
        if all_parsed_rows:
            names = set(r.get("OrganizationName", "") for r in all_parsed_rows)
            display_name = (
                next(iter(names)) if len(names) == 1
                else f"{len(names)} organizations"
            )
            n_years = len(set(r.get("TaxYear", "") for r in all_parsed_rows))
            with indicator_slot.container():
                st.markdown(
                    f'<div class="sb-loaded">'
                    f'<div class="sb-loaded-name">{display_name}</div>'
                    f'<div class="sb-loaded-meta">'
                    f'{n_years} year{"s" if n_years != 1 else ""} loaded</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # ── Saved Organizations ──
        if saved_orgs:
            with st.expander(f"Saved Organizations ({len(saved_orgs)})"):
                _render_saved_orgs(saved_orgs, user_id)

        # ── Tags & Categories ──
        if user_id and saved_orgs:
            with st.expander("Tags & Categories"):
                _render_tags(user_id, saved_orgs)

        st.divider()
        _section_label("Account")

        # ── Account Settings ──
        display = (st.session_state.get("auth_display_name")
                   or st.session_state.get("auth_username", "Account"))
        with st.expander(f"\U0001F464 {display}"):
            render_account_settings()

        # ── Admin Panel (admin only) ──
        if st.session_state.get("auth_role") == "admin":
            with st.expander("\u2699 Admin Panel"):
                render_admin_panel()

        # ── Credits ──
        st.markdown(
            '<div class="sb-credits">'
            'Developed by <b>Epic Intentions</b><br>'
            "for Brighter Investing<br>"
            "Georgia Tech \u00b7 Spring 2026"
            "</div>",
            unsafe_allow_html=True,
        )

    return all_parsed_rows, parse_errors
