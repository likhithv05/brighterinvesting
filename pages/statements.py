"""
Financial Statements Page — Tab 4
Revenue statement, expense statement, and balance sheet with charts.
"""

import streamlit as st
import plotly.graph_objects as go

from components.charts import apply_theme, PAL


# ─── Statement Definitions ───
# Each row: (label, field_key, style)
#   style: "" = normal, "indent" = sub-item, "total" = bold total row

_REVENUE_ROWS = [
    ("Contributions & Grants", "TotalContributionsGrants", ""),
    ("\u2003Government Grants", "GovernmentGrants", "indent"),
    ("\u2003Other Contributions", "ContributionsGrantsOther", "indent"),
    ("Program Service Revenue", "ProgramServiceRevenue", ""),
    ("Investment Income", "InvestmentIncome", ""),
    ("Net Gain/Loss on Investments", "NetGainLossInvestments", ""),
    ("Unrelated Business Revenue", "UnrelatedBusinessRevenue", ""),
    ("Other Revenue", "OtherRevenue", ""),
    ("Total Revenue", "TotalRevenue", "total"),
]

_EXPENSE_ROWS = [
    ("By Function", None, "header"),
    ("\u2003Program Services", "ProgramExpenses", "indent"),
    ("\u2003Management & General", "ManagementGeneralExpenses", "indent"),
    ("\u2003Fundraising", "FundraisingExpenses", "indent"),
    ("By Line Item", None, "header"),
    ("\u2003Salaries & Wages", "SalariesWages", "indent"),
    ("\u2003Employee Benefits", "EmployeeBenefits", "indent"),
    ("\u2003Pension Contributions", "PensionRetirementContributions", "indent"),
    ("\u2003Payroll Taxes", "PayrollTaxes", "indent"),
    ("\u2003Grants & Similar Paid", "GrantsAndSimilarPaid", "indent"),
    ("\u2003Occupancy", "Occupancy", "indent"),
    ("\u2003Depreciation & Amortization", "DepreciationAmortization", "indent"),
    ("\u2003Information Technology", "InformationTechnology", "indent"),
    ("\u2003Travel", "Travel", "indent"),
    ("\u2003Insurance", "Insurance", "indent"),
    ("\u2003Legal Fees", "LegalFees", "indent"),
    ("\u2003Accounting Fees", "AccountingFees", "indent"),
    ("\u2003Office Expenses", "OfficeExpenses", "indent"),
    ("\u2003Other Expenses", "OtherExpenses", "indent"),
    ("Total Expenses", "TotalExpenses", "total"),
]

_BALANCE_ROWS = [
    ("Assets", None, "header"),
    ("\u2003Cash (Non-Interest Bearing)", "CashNonInterest", "indent"),
    ("\u2003Savings & Temp Investments", "SavingsTempCashInvestments", "indent"),
    ("\u2003Publicly Traded Securities", "PublicInvestments", "indent"),
    ("\u2003Inventory", "Inventory", "indent"),
    ("\u2003Prepaid Expenses", "PrepaidExpenses", "indent"),
    ("\u2003Property & Equipment (Net)", "PropertyEquipmentNet", "indent"),
    ("\u2003Other Assets", "OtherAssets", "indent"),
    ("Total Assets", "TotalAssets", "total"),
    ("Liabilities", None, "header"),
    ("\u2003Accounts Payable", "AccountsPayableAccrued", "indent"),
    ("\u2003Other Liabilities", "OtherLiabilities", "indent"),
    ("Total Liabilities", "TotalLiabilities", "total"),
    ("Net Assets", None, "header"),
    ("\u2003Unrestricted", "NetAssetsWithoutDonorRestrictions", "indent"),
    ("\u2003Donor-Restricted", "NetAssetsWithDonorRestrictions", "indent"),
    ("Total Net Assets", "TotalNetAssets", "total"),
]


def _fmt(value):
    """Format a dollar value with $ prefix, commas, and negative parentheses."""
    if value is None:
        return '<span style="color:#94A3B8;">N/A</span>'
    if not isinstance(value, (int, float)):
        return str(value) if value else "\u2014"
    if value < 0:
        return f'<span class="neg">({_fmt_abs(abs(value))})</span>'
    return _fmt_abs(value)


def _fmt_abs(v):
    """Format an absolute dollar value."""
    return f"${v:,.0f}"


def _build_table(title, rows, parsed_rows):
    """Build an HTML table string from row definitions and parsed data."""
    years = [r.get("TaxYear", "") for r in parsed_rows]

    h = f'<div class="fin-tbl"><div class="fin-hdr">{title}</div>'
    h += '<div style="overflow-x:auto"><table><thead><tr>'
    h += '<th style="text-align:left"></th>'
    for yr in years:
        h += f"<th>{yr}</th>"
    h += "</tr></thead><tbody>"

    for label, key, style in rows:
        if style == "header":
            h += (
                f'<tr class="fin-section-row">'
                f'<td colspan="{len(years) + 1}" class="fin-section">'
                f'{label}</td></tr>'
            )
            continue

        is_total = style == "total"
        is_indent = style == "indent"
        row_cls = ' class="fin-total"' if is_total else ""
        lbl_cls = "fin-indent" if is_indent else ""

        h += f"<tr{row_cls}>"
        h += f'<td class="{lbl_cls}">{label}</td>'
        for row in parsed_rows:
            v = row.get(key, 0) if key else 0
            h += f'<td class="num">{_fmt(v)}</td>'
        h += "</tr>"

    h += "</tbody></table></div></div>"
    return h


def _revenue_chart(parsed_rows):
    """Stacked bar chart of revenue by source."""
    years = [r.get("TaxYear", "") for r in parsed_rows]
    sources = [
        ("TotalContributionsGrants", "Contributions & Grants", PAL[0]),
        ("ProgramServiceRevenue", "Program Service Revenue", PAL[1]),
        ("InvestmentIncome", "Investment Income", PAL[2]),
        ("OtherRevenue", "Other Revenue", "#94A3B8"),
    ]
    fig = go.Figure()
    for key, name, color in sources:
        fig.add_trace(go.Bar(
            x=years,
            y=[r.get(key, 0) for r in parsed_rows],
            name=name,
            marker_color=color,
            marker_cornerradius=4,
        ))
    fig.update_layout(barmode="stack")
    apply_theme(fig, 360)
    fig.update_yaxes(tickprefix="$", title_text="Amount ($)")
    st.plotly_chart(fig, use_container_width=True)


def _expense_chart(parsed_rows):
    """Stacked bar chart of expenses by function."""
    years = [r.get("TaxYear", "") for r in parsed_rows]
    functions = [
        ("ProgramExpenses", "Program Services", PAL[0]),
        ("ManagementGeneralExpenses", "Management & General", "#64748B"),
        ("FundraisingExpenses", "Fundraising", PAL[2]),
    ]
    fig = go.Figure()
    for key, name, color in functions:
        fig.add_trace(go.Bar(
            x=years,
            y=[r.get(key, 0) for r in parsed_rows],
            name=name,
            marker_color=color,
            marker_cornerradius=4,
        ))
    fig.update_layout(barmode="stack")
    apply_theme(fig, 360)
    fig.update_yaxes(tickprefix="$", title_text="Amount ($)")
    st.plotly_chart(fig, use_container_width=True)


def _balance_chart(parsed_rows):
    """Grouped bar chart of assets vs liabilities over time."""
    years = [r.get("TaxYear", "") for r in parsed_rows]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=years,
        y=[r.get("TotalAssets", 0) for r in parsed_rows],
        name="Total Assets",
        marker_color=PAL[0],
        marker_cornerradius=4,
    ))
    fig.add_trace(go.Bar(
        x=years,
        y=[r.get("TotalLiabilities", 0) for r in parsed_rows],
        name="Total Liabilities",
        marker_color="#64748B",
        marker_cornerradius=4,
    ))
    fig.add_trace(go.Bar(
        x=years,
        y=[r.get("TotalNetAssets", 0) for r in parsed_rows],
        name="Net Assets",
        marker_color=PAL[1],
        marker_cornerradius=4,
    ))
    fig.update_layout(barmode="group")
    apply_theme(fig, 360)
    fig.update_yaxes(tickprefix="$", title_text="Amount ($)")
    st.plotly_chart(fig, use_container_width=True)


def render(parsed_rows):
    # ── Revenue Statement ──
    st.markdown(
        '<div class="sec-t">Revenue Statement</div>'
        '<div class="sec-s">All revenue sources across filing years.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        _build_table("Revenue", _REVENUE_ROWS, parsed_rows),
        unsafe_allow_html=True,
    )
    if len(parsed_rows) > 1:
        _revenue_chart(parsed_rows)

    # ── Expense Statement ──
    st.markdown(
        '<div class="sec-t">Expense Statement</div>'
        '<div class="sec-s">'
        'Functional and line-item expense breakdown.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        _build_table("Expenses", _EXPENSE_ROWS, parsed_rows),
        unsafe_allow_html=True,
    )
    if len(parsed_rows) > 1:
        _expense_chart(parsed_rows)

    # ── Balance Sheet ──
    st.markdown(
        '<div class="sec-t">Balance Sheet</div>'
        '<div class="sec-s">'
        'Assets, liabilities, and net asset composition.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        _build_table("Balance Sheet", _BALANCE_ROWS, parsed_rows),
        unsafe_allow_html=True,
    )
    if len(parsed_rows) > 1:
        _balance_chart(parsed_rows)
