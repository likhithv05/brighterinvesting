# Brighter Investing — Form 990 Financial Analyzer

A full-featured web application for analyzing IRS Form 990 nonprofit tax filings. Upload XML filings or search organizations directly through ProPublica's Nonprofit Explorer API. View interactive dashboards, trend analysis, investment breakdowns, financial statements, scenario forecasting, and export professional Excel reports.

Developed by **Epic Intentions** for **Brighter Investing**
Georgia Institute of Technology — Spring 2026

---

## Features

### Core Analysis
- **KPI Dashboard** — 18+ financial health metrics with color-coded status indicators and benchmark comparisons
- **Trend Analysis** — Multi-year interactive charts (Plotly) tracking revenue, expenses, margins, and ratios over time
- **Investment Detail** — Breakdown of cash positions, realized/unrealized gains, real estate assets, and investment return ratios
- **Financial Statements** — Detailed revenue, expense, asset, and liability tables extracted from Form 990 data
- **Raw Data View** — Full parsed data table with search and sort capabilities
- **Scenario Forecasting** — What-if projections with adjustable revenue growth, expense changes, and custom assumptions

### Data Sources
- **XML File Upload** — Upload one or more IRS Form 990 XML filings directly (supports Form 990, 990-EZ, 990-PF)
- **ProPublica Integration** — Search any US nonprofit by name or EIN, browse filing history, and load filings directly from ProPublica's public Nonprofit Explorer API (no API key required)

### Multi-Organization Support
- **Saved Organizations** — Save loaded organizations to your account for quick access across sessions
- **Tag System** — Organize saved organizations with custom tags and filter by tag
- **Side-by-Side Comparison** — Compare two organizations on the same KPIs in a dedicated Compare tab

### User Management
- **Authentication** — Secure login with bcrypt password hashing, account lockout after failed attempts, and remember-me functionality
- **Account Settings** — Change display name, email, password, and security questions from the sidebar
- **Admin Panel** — Admin users can manage all accounts: reset passwords, change roles, deactivate, or delete users
- **Role-Based Access** — Admin and standard user roles with appropriate access controls
- **Password Recovery** — Security question-based password reset flow

### Export
- **Excel Reports** — Professionally formatted multi-sheet workbooks with KPI summary, raw extracted data, and KPI definitions with benchmarks

---

## Quick Start

### Prerequisites

- **Python 3.9** or higher
- **pip** (Python package manager)
- Internet connection (required for ProPublica search; not needed for XML file uploads)

### macOS / Linux

```bash
# 1. Clone the repository
git clone https://github.com/likhithv05/brighterinvesting.git
cd brighterinvesting

# 2. (Recommended) Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the application
streamlit run app.py
```

The app will open in your default browser at `http://localhost:8501`.

### Windows

```powershell
# 1. Clone the repository
git clone https://github.com/likhithv05/brighterinvesting.git
cd brighterinvesting

# 2. (Recommended) Create a virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the application
streamlit run app.py
```

The app will open in your default browser at `http://localhost:8501`.

> **Note:** On Windows, if `python` is not recognized, try `py` instead of `python`. If `streamlit` is not recognized after install, try `python -m streamlit run app.py`.

---

## First-Time Setup

1. **Create an account** — On first launch, the app creates a local SQLite database (`auth.db`). Click "Create Account" on the login page to register.
2. **First registered user becomes admin** — The very first user to register is automatically assigned the admin role and can manage other users through the Admin Panel in the sidebar.
3. **Upload data or search ProPublica** — Use the sidebar to either upload Form 990 XML files or search for organizations via ProPublica.

---

## Using ProPublica Search

The ProPublica Nonprofit Explorer integration lets you analyze any US nonprofit without needing to download XML files manually.

1. In the sidebar, switch the data source to **"ProPublica Search"**
2. Enter an organization name or EIN in the search box
3. Select an organization from the results
4. Choose which tax years to load (filings with available XML data are shown)
5. Click "Load Selected Filings" — the app downloads and parses the XML filings automatically
6. Optionally save the organization to your account for quick access later

**No API key is required.** ProPublica's Nonprofit Explorer API is free and public. The app caches API responses to minimize network requests.

---

## Getting Form 990 XML Files

If you prefer to upload files directly:

- **IRS Tax Exempt Organization Search**: [https://apps.irs.gov/app/eos/](https://apps.irs.gov/app/eos/)
- **ProPublica Nonprofit Explorer**: [https://projects.propublica.org/nonprofits/](https://projects.propublica.org/nonprofits/)
- Files should be IRS e-file XML format (the raw XML return, not PDFs)
- Supported form types: Form 990, Form 990-EZ, Form 990-PF
- Maximum file size: 50 MB per file

---

## Project Structure

```
brighterinvesting/
├── app.py                          # Main entry point — config, auth gate, tab routing
├── requirements.txt                # Python dependencies
├── .streamlit/
│   └── config.toml                 # Streamlit theme and server settings
├── assets/
│   └── logo.svg                    # Brighter Investing logo
├── core/
│   ├── db_utils.py                 # SQLite database — users, sessions, orgs, tags
│   ├── export.py                   # Excel workbook generation (openpyxl)
│   ├── kpis.py                     # KPI computation engine and definitions
│   ├── login.py                    # Login, registration, and password reset UI
│   ├── parser.py                   # Form 990 XML extraction logic
│   └── propublica.py               # ProPublica Nonprofit Explorer API client
├── components/
│   ├── account_settings.py         # Account management (password, profile, security questions)
│   ├── admin_panel.py              # Admin user management panel
│   ├── charts.py                   # Plotly chart builders
│   ├── data_filter.py              # Organization and year filtering
│   ├── empty_state.py              # Empty state placeholder
│   ├── header.py                   # App header and org banner
│   ├── kpi_cards.py                # KPI summary card components
│   └── sidebar.py                  # Sidebar — data source, saved orgs, tags, account
├── views/
│   ├── dashboard.py                # KPI dashboard tab
│   ├── trends.py                   # Trend analysis tab
│   ├── investments.py              # Investment detail tab
│   ├── statements.py               # Financial statements tab
│   ├── raw_data.py                 # Raw extracted data tab
│   ├── forecasting.py              # Scenario forecasting tab
│   └── compare.py                  # Side-by-side organization comparison tab
└── styles/
    └── main.css                    # Custom CSS styling
```

---

## Requirements

All dependencies are listed in `requirements.txt`:

| Package | Purpose |
|---------|---------|
| `streamlit` | Web application framework |
| `plotly` | Interactive charts and visualizations |
| `xmltodict` | XML parsing for Form 990 filings |
| `openpyxl` | Excel report generation |
| `pandas` | Data manipulation and table display |
| `bcrypt` | Secure password hashing |
| `requests` | HTTP client for ProPublica API |

No external database is required — the app uses SQLite (built into Python) for user accounts and saved organizations.

---

## Configuration

The app is pre-configured via `.streamlit/config.toml`:

- **Theme**: Light mode with teal accent color
- **Max upload size**: 50 MB
- **XSRF protection**: Enabled
- **Usage stats**: Disabled

To change the port or other server settings, edit `.streamlit/config.toml` or pass flags:

```bash
streamlit run app.py --server.port 8080
```

---

## GitHub Codespaces

This project includes a `.devcontainer/devcontainer.json` for GitHub Codespaces. Opening the repo in a Codespace will automatically install dependencies and start the Streamlit server on port 8501.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` again |
| `streamlit: command not found` | Use `python -m streamlit run app.py` instead |
| ProPublica search returns no results | Check your internet connection; ProPublica may be temporarily down |
| Login page shows "Database error" | Delete `auth.db` and restart — a fresh database will be created |
| Excel download fails | Ensure `openpyxl` is installed: `pip install openpyxl` |
| Port 8501 already in use | Use `streamlit run app.py --server.port 8502` |

---

## License

This project was developed by Epic Intentions for Brighter Investing as part of a Georgia Institute of Technology capstone project (Spring 2026).
