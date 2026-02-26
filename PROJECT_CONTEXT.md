# PROJECT_CONTEXT.md — Brighter Investing Form 990 Analyzer

Pre-refactor documentation. Snapshot commit: `pre-refactor snapshot`

---

## File Inventory

### `app.py` (1814 lines) — Main Streamlit Application
The monolithic UI entry point. Handles:
- Page config, session state initialization, auth gate
- Full CSS design system (~410 lines of inline `<style>`)
- Sidebar: file upload, ProPublica search, QuickBooks placeholder, saved org browser, tag management
- Data loading pipeline (uploads, demo, ProPublica, saved orgs)
- Duplicate detection UI
- Organization & year filtering (All Years / Single Year / Year Range)
- 6 tabs: Dashboard, Trends, Investment Detail, Financial Statements, Raw Data, Compare (conditional)
- Plotly charts: revenue vs expenses bar, expense pie/bar, trend lines, balance sheet, workforce, cash trend
- KPI card grid rendering via raw HTML
- Excel export download button
- Footer

### `parser.py` (365 lines) — XML Parser
Parses IRS Form 990 XML files (via `xmltodict`) into flat dicts. Extracts ~60 financial fields across:
- Organization info (name, EIN, tax year, address, mission)
- Revenue (contributions, program service, investment, other)
- Expenses (program, mgmt, fundraising, line items like salaries, legal, travel)
- Assets (cash, savings, investments, property, inventory)
- Liabilities & net assets (restricted/unrestricted)
- Governance (employee count, board members, exec compensation)
- Investment detail (realized/unrealized gains, real estate)

Also defines `FIELD_GROUPS` (display groupings) and `FIELD_LABELS` (human-readable names for every field).

### `kpis.py` (388 lines) — KPI Computation Engine
`compute_kpis(row)` takes a parsed row dict and returns ~28 derived metrics:
- Core: operating surplus, program/mgmt/fundraising ratios, operating margin, contribution dependency
- Liquidity: months expense coverage, liquid assets, current ratio, cash equivalents
- Growth: revenue growth, expense growth, net asset growth
- Investment: realized/unrealized gains, total returns, return ratios (to liquid, to assets, to expenses)

Also contains:
- `KPI_DEFINITIONS`: dict with label, format, description, benchmark for each KPI
- `PRIMARY_KPIS`, `TREND_KPIS`, `INVESTMENT_KPIS`: lists controlling which KPIs appear where
- `format_kpi_value()`: formats values as currency/percent/decimal/ratio
- `get_kpi_status()`: returns good/warning/concern based on hardcoded thresholds

### `login.py` (417 lines) — Authentication UI
- `show_login_page()`: Branded login card with 3 tabs (Sign In, Create Account, Forgot Password)
- Registration with password strength meter and security questions
- Password reset via security question verification
- Remember-me auto-login via session tokens
- `show_admin_panel()`: User management table with role toggle, activate/deactivate, password reset, delete

### `db_utils.py` (571 lines) — Database Layer
SQLite database (`auth.db`) with tables:
- `users`: id, username, password_hash, role, last_login, created_at, is_active
- `security_questions`: user_id, question_1/2, answer_hash_1/2 (bcrypt)
- `user_organizations`: user_id, ein, org name, tax_years JSON, parsed_data_json, data_hash, timestamp
- `session_tokens`: user_id, token, expires_at (30-day remember-me)
- `org_tags`: user_id, tag_name, tag_color
- `org_tag_map`: user_id, ein, tag_id (many-to-many)

Key functions: `init_extended_db()`, `save_organization()` (with merge logic), `load_user_organizations()`, `detect_duplicates()`, tag CRUD, user management, security question hashing.

### `export.py` (276 lines) — Excel Report Generator
`generate_workbook(parsed_rows)` creates a 3-sheet openpyxl workbook:
1. **Summary**: KPI table with all years, formatted with currency/percent/ratio styles
2. **Extracted Data**: Raw fields with human-readable headers
3. **KPI Definitions**: Label, description, benchmark for each metric

Applies professional styling: header colors, zebra striping, auto-width columns, frozen panes.

### `propublica.py` (129 lines) — ProPublica API Integration
- `search_nonprofits(query)`: searches by name/EIN, returns org list (cached 5 min)
- `get_organization_filings(ein)`: fetches filing history with XML URLs (cached 5 min)
- `fetch_filing_xml(xml_url)`: downloads raw XML bytes (cached 10 min)
- `format_filing_year()`, `format_revenue()`: display helpers

### Config & Support Files
- `.streamlit/config.toml`: Light theme, teal primary, 50MB upload limit, XSRF protection
- `.devcontainer/devcontainer.json`: Python 3.11, auto-installs deps, runs `streamlit run app.py`
- `.gitignore`: pycache, DS_Store, env, xlsx, pptx
- `requirements.txt`: streamlit, plotly, xmltodict, openpyxl, pandas, bcrypt, requests
- `assets/logo.svg`: Brighter Investing SVG logo
- `auth.db`: SQLite database (live data — users, saved orgs, tokens)

---

## Data Flow

```
1. DATA INGESTION
   ├── Upload XML tab → st.file_uploader → raw bytes
   ├── ProPublica tab → search API → select org → select years → fetch XML bytes
   ├── Demo data → load from filesystem (hardcoded path)
   └── Saved orgs → load from SQLite (user_organizations.parsed_data_json)

2. PARSING (parser.py)
   raw XML bytes → xmltodict.parse() → navigate Return/ReturnData/IRS990
   → extract ~60 fields → flat dict (one per filing year)
   → validate (warn on missing EIN/TaxYear/name/zeroes)

3. PERSISTENCE (db_utils.py)
   parsed rows → group by EIN → save_organization()
   → merge with existing data (dedup by TaxYear) → store as JSON in SQLite

4. FILTERING (app.py)
   all_parsed_rows → group by EIN → select org → filter by year mode
   → parsed_rows (final filtered set)

5. KPI COMPUTATION (kpis.py)
   each parsed row → compute_kpis() → dict of ~28 derived metrics
   → kpi_data list + kpi_df DataFrame

6. DISPLAY (app.py)
   ├── Dashboard tab: KPI cards (HTML), revenue/expense chart, expense pie/bar
   ├── Trends tab: multi-select trend lines, balance sheet, workforce charts
   ├── Investment tab: cash/savings/investment KPI cards, cash trend chart
   ├── Financial Statements tab: HTML tables (revenue, expenses, balance sheet by year)
   ├── Raw Data tab: pandas DataFrames
   └── Compare tab: side-by-side KPI cards for two orgs

7. EXPORT (export.py)
   parsed_rows → generate_workbook() → openpyxl workbook → bytes
   → st.download_button
```

---

## Session State Keys

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `authenticated` | bool | `False` | Auth gate — blocks entire app when False |
| `username` | str/None | `None` | Logged-in username |
| `role` | str/None | `None` | `"user"` or `"admin"` |
| `user_id` | int/None | `None` | SQLite user ID for DB queries |
| `selected_ein` | str/None | `None` | Currently selected org EIN (sidebar + org selector) |
| `selected_org_name` | str/None | `None` | Currently selected org name |
| `year_filter_mode` | str | `"All Years"` | Declared in defaults but **not actually used** — the radio uses key `year_filter_mode_radio` instead |
| `selected_year` | str/None | `None` | Declared in defaults but **unused** — single year uses key `single_year_select` |
| `year_range` | tuple/None | `None` | Declared in defaults but **unused** — year range uses key `year_range_slider` |
| `comparison_mode` | bool | `False` | Enables Compare tab and org-B selector |
| `comparison_ein` | str/None | `None` | EIN of the comparison org |
| `show_admin` | bool | `False` | Toggles admin panel visibility |
| `tag_filter_eins` | list/None | `None` | Set of EINs matching a tag filter; filters saved orgs list |
| `propublica_results` | dict/None | `None` | Cached ProPublica search results |
| `propublica_filings` | dict/None | `None` | Cached filings for a selected ProPublica org |
| `propublica_selected_ein` | str/None | `None` | EIN selected from ProPublica search |
| `pp_loaded_rows` | list | (not in defaults) | Parsed rows from ProPublica download; set dynamically |
| `remember_me_token` | str | (not in defaults) | Set on login with "remember me"; checked on page load |
| `confirm_del_{uid}` | bool | (dynamic) | Two-click delete confirmation in admin panel |

**Widget keys** (Streamlit-managed, not in `_DEFAULTS`):
`pp_search_input`, `pp_search_btn`, `pp_year_select`, `pp_load_filings`, `filter_tag_select`, `new_tag_input`, `new_tag_color`, `add_tag_btn`, `del_tag_select`, `del_tag_btn`, `assign_org_select`, `assign_tag_select`, `assign_tag_btn`, `remove_tag_select`, `remove_tag_btn`, `login_user`, `login_pass`, `login_remember`, `reg_user`, `reg_pass`, `reg_confirm`, `reg_sq1`, `reg_sa1`, `reg_sq2`, `reg_sa2`, `reset_user`, `reset_a1`, `reset_a2`, `reset_new_pw`, `reset_confirm_pw`, `year_filter_mode_radio`, `single_year_select`, `year_range_slider`, `comp_org_select`, `load_saved_{ein}`, `del_saved_{ein}`, `pp_select_{ein}`, `dup_keep_{ein}_{year}_{ci}`

---

## Known Bugs & Issues

### Structural / Architectural
1. **Monolithic `app.py`** (1814 lines) — All UI, styling, data loading, filtering, and charting logic in one file. Extremely hard to maintain, test, or extend.
2. **~410 lines of inline CSS** — Embedded as a raw string in `app.py`. No separation of concerns; any style change requires editing Python code.
3. **No test suite** — Zero unit tests, integration tests, or fixtures anywhere in the project.
4. **`auth.db` is committed to the repo** — Contains live user credentials (bcrypt hashes) and session tokens. This is a security concern; it should be in `.gitignore`.

### Session State
5. **Dead session state keys** — `year_filter_mode`, `selected_year`, and `year_range` are initialized in `_DEFAULTS` but never read. The actual widgets use Streamlit-managed keys (`year_filter_mode_radio`, `single_year_select`, `year_range_slider`). These defaults are dead code.
6. **`pp_loaded_rows` not in `_DEFAULTS`** — Set dynamically after ProPublica download but never cleared. If a user uploads XML after previously loading from ProPublica, the ProPublica data persists and may reload unexpectedly due to the fallback chain in data loading (lines 1069-1081).
7. **`selected_ein` set in two places** — Set by saved-org buttons in the sidebar (line 888) AND by the org selector in the main area (line 1166). These can conflict. The sidebar sets it without clearing other state, so stale org names or comparison state can carry over.

### Data Flow
8. **Demo data path is hardcoded and fragile** — Points to `../Form 990 Parser/Data Engineering 2.6.2026/Final_Model_Files/Habitat for Humanity Test Data` (line 681). This relative path depends on a sibling directory existing with that exact name.
9. **Data loading priority is implicit** — The `if/elif/elif/elif` chain (lines 1069-1081) silently picks the first matching source. No feedback to the user about which source was used. ProPublica data (`pp_loaded_rows`) takes priority over saved orgs, which may be confusing.
10. **Duplicate resolution mutates `all_parsed_rows` in-place** — The `pop()` on line 1112 modifies the list, but since this runs during a Streamlit rerun, the original data is lost without the user explicitly saving. The fix is applied ephemerally.
11. **Auto-save on upload** (line 1072-1073) runs every rerun if files are still in the uploader, not just on first upload. The `save_organization` merge logic prevents data duplication, but it's wasteful.

### Security
12. **No CSRF protection on login form** — While Streamlit has XSRF for API endpoints (config.toml), the login form itself has no rate limiting or brute force protection.
13. **Security questions stored with bcrypt** — Correct approach, but the questions themselves are visible in the DB. An attacker with DB access sees which questions a user chose.
14. **Admin password reset shows temp password in plaintext** — On line 407, `st.info(f"Temporary password: {temp_pw}")`. This is visible on screen and may persist in browser history.
15. **Remember-me token stored in session state** — Streamlit session state is server-side and ephemeral, so the "remember me" token cannot actually survive a browser close/reopen. The feature is effectively broken.

### Parser
16. **`import warnings` inside function body** — `parse_single_xml()` line 239 imports `warnings` conditionally inside the function. Should be a top-level import.
17. **No support for Form 990-PF** — The parser only handles `IRS990` and `IRS990EZ`. Private foundations (990-PF) silently fail with "No IRS990 or IRS990EZ data found."
18. **`RealizedGainsSecurities` extraction is fragile** — Lines 224-226 use `GainOrLossFromSaleOtherAssets` which is a different field than investment securities gains. The field name doesn't match what's being extracted.

### KPIs
19. **`NetAssetGrowth` division safety** — Line 76: if `TotalNetAssetsBOY` is exactly 0, the `else` branch divides by 1 (hardcoded fallback), returning a misleading non-zero result instead of 0.
20. **`CurrentRatio` is mislabeled** — Defined as "liquid assets / total liabilities" but labeled "Liquidity Ratio." In accounting, "Current Ratio" is current assets / current liabilities, not total liabilities.
21. **`get_kpi_status` returns `"neutral"` as default** — But the `_ST` dict in app.py (line 567) doesn't have a `"neutral"` key, so it falls through to `("—", "n")`. Works but is fragile.

### UI / Display
22. **Comparison delta always calculated from Org A's perspective** — Line 1759: `diff_pct = ((v_a - v_b) / abs(v_b)) * 100`. For metrics where lower is better (DebtToAssetRatio, FundraisingRatio), a "positive" delta is actually bad, but it's styled green.
23. **`parsed_rows` variable scoping** — `parsed_rows` is only defined inside the `if all_parsed_rows:` block (line 1208). The later code at line 1214 references it in `if not all_parsed_rows or not parsed_rows:` which would raise `NameError` if `all_parsed_rows` is truthy but some other code path skipped defining `parsed_rows`. In practice this works because the only path to truthy `all_parsed_rows` goes through the block, but it's fragile.
24. **`_fin_table` iterates `data` for columns but `fields` for rows** — The function (line 590) assumes `data` is ordered the same as `years`. This is only correct because `parsed_rows` is pre-sorted. No defensive check.
25. **Unused import: `xml.etree.ElementTree`** — In `propublica.py` line 3, `ET` is imported but never used.
26. **Unused import: `pandas`** — In `kpis.py` line 9, `pd` is imported but never used.

### Export
27. **Export only includes the filtered org** — `generate_workbook(parsed_rows)` receives the already-filtered single-org data. If a user has multiple orgs loaded, only the currently selected one is exported. No option to export all.
28. **BOY fields missing from export** — `TotalAssetsBOY`, `TotalLiabilitiesBOY`, `TotalNetAssetsBOY` are parsed but not included in the Extracted Data sheet's `input_fields` list.
