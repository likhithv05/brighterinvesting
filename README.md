# Form 990 Analyzer

A web application for analyzing IRS Form 990 XML filings. Upload nonprofit tax filings to view financial dashboards, KPI trends, and export Excel reports.

## Features

- **KPI Dashboard** — Key financial health metrics with benchmark comparisons
- **Trend Analysis** — Multi-year visualizations for tracking performance over time
- **Financial Statements** — Extracted revenue, expenses, assets, and liabilities
- **Excel Export** — Downloadable reports with computed KPIs and raw data

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Usage

1. Upload one or more Form 990 XML files via the sidebar
2. View the dashboard, trends, and financial statement tabs
3. Download the Excel report for offline analysis

## Requirements

- Python 3.9+
- Streamlit
- Plotly
- pandas
- openpyxl
- xmltodict

## Project Structure

```
├── app.py        # Streamlit UI and visualization
├── parser.py     # XML extraction logic
├── kpis.py       # KPI computation and definitions
├── export.py     # Excel report generation
└── assets/       # Logo and static files
```

## Data Source

Form 990 XML files can be downloaded from the [IRS Tax Exempt Organization Search](https://apps.irs.gov/app/eos/).
