"""
KPI Computation Engine
Calculates derived financial metrics from parsed Form 990 data.

Developed by Epic Intentions for Brighter Investing
Georgia Institute of Technology — Spring 2026
"""

import pandas as pd


def compute_kpis(row):
    """
    Compute all derived KPI metrics for a single parsed Form 990 record.

    Parameters:
        row: dict from parse_single_xml()

    Returns:
        dict with KPI field names and computed values
    """
    total_rev = row.get("TotalRevenue", 0) or 0
    total_exp = row.get("TotalExpenses", 0) or 0
    program_exp = row.get("ProgramExpenses", 0) or 0
    mgmt_exp = row.get("ManagementGeneralExpenses", 0) or 0
    fundraising_exp = row.get("FundraisingExpenses", 0) or 0
    contributions = row.get("TotalContributionsGrants", 0) or 0
    investment_income = row.get("InvestmentIncome", 0) or 0
    net_gain_investments = row.get("NetGainLossInvestments", 0) or 0
    cash = row.get("CashNonInterest", 0) or 0
    savings = row.get("SavingsTempCashInvestments", 0) or 0
    public_inv = row.get("PublicInvestments", 0) or 0
    depreciation = row.get("DepreciationAmortization", 0) or 0
    total_assets = row.get("TotalAssets", 0) or 0
    total_liabilities = row.get("TotalLiabilities", 0) or 0
    total_net_assets = row.get("TotalNetAssets", 0) or 0
    salaries = row.get("SalariesWages", 0) or 0
    prior_rev = row.get("PriorYearRevenue", 0) or 0
    prior_exp = row.get("PriorYearExpenses", 0) or 0

    # New fields from feedback
    realized_gains = row.get("RealizedGainsSecurities", 0) or 0
    unrealized_gains = row.get("UnrealizedGainsSecurities", 0) or 0
    real_estate_assets = row.get("RealEstateAssets", 0) or 0
    property_equipment = row.get("PropertyEquipmentNet", 0) or 0

    operating_surplus = total_rev - total_exp
    total_cash = cash + savings
    liquid_assets = cash + savings + public_inv

    # Total Investment Returns = investment income + unrealized gains + realized gains
    total_investment_returns = investment_income + unrealized_gains + realized_gains

    # Non-real-estate investment returns
    non_re_investment_returns = total_investment_returns  # subtract RE gains if tracked

    return {
        # ── Core KPIs ──
        "OperatingSurplus": operating_surplus,
        "TotalCashEquivalents": total_cash,
        "ProgramExpenseRatio": program_exp / total_exp if total_exp > 0 else 0,
        "ManagementGeneralRatio": mgmt_exp / total_exp if total_exp > 0 else 0,
        "FundraisingRatio": fundraising_exp / total_exp if total_exp > 0 else 0,
        "OperatingMargin": operating_surplus / total_rev if total_rev > 0 else 0,
        "ContributionDependency": contributions / total_rev if total_rev > 0 else 0,
        "LiquidAssets": liquid_assets,
        "MonthsExpenseCoverage": liquid_assets / (total_exp / 12) if total_exp > 0 else 0,
        "NetOperatingIncome": (total_rev - investment_income - net_gain_investments) - total_exp,
        "NetInvestmentGain": net_gain_investments,
        "DepreciationNonCash": depreciation,
        "DebtToAssetRatio": total_liabilities / total_assets if total_assets > 0 else 0,
        "CurrentRatio": liquid_assets / total_liabilities if total_liabilities > 0 else 0,
        "RevenueGrowth": (total_rev - prior_rev) / prior_rev if prior_rev > 0 else 0,
        "ExpenseGrowth": (total_exp - prior_exp) / prior_exp if prior_exp > 0 else 0,
        "SalaryToExpenseRatio": salaries / total_exp if total_exp > 0 else 0,
        "NetAssetGrowth": (total_net_assets - row.get("TotalNetAssetsBOY", 0)) / row.get("TotalNetAssetsBOY", 1) if row.get("TotalNetAssetsBOY", 0) > 0 else 0,

        # ── New Metrics (Feedback) ──
        "CashOnly": cash,
        "SavingsOnly": savings,
        "CashToLiquidRatio": cash / liquid_assets if liquid_assets > 0 else 0,
        "SavingsToLiquidRatio": savings / liquid_assets if liquid_assets > 0 else 0,
        "RealizedGains": realized_gains,
        "UnrealizedGains": unrealized_gains,
        "TotalInvestmentReturns": total_investment_returns,
        "RealEstateAssets": real_estate_assets + property_equipment,
        "InvestmentReturnsToLiquid": non_re_investment_returns / liquid_assets if liquid_assets > 0 else 0,
        "InvestmentReturnsToAssets": total_investment_returns / total_assets if total_assets > 0 else 0,
        "InvestmentReturnsToExpenses": total_investment_returns / total_exp if total_exp > 0 else 0,
    }


# KPI definitions for display
KPI_DEFINITIONS = {
    "OperatingSurplus": {
        "label": "Operating Surplus (Deficit)",
        "format": "currency",
        "description": "Total Revenue minus Total Expenses. Positive means surplus, negative means deficit.",
        "benchmark": "A healthy nonprofit should aim for a small positive surplus (3-5% of revenue).",
    },
    "TotalCashEquivalents": {
        "label": "Cash & Cash Equivalents",
        "format": "currency",
        "description": "Sum of non-interest bearing cash and savings/temporary investments.",
        "benchmark": "Should cover at least 3 months of operating expenses.",
    },
    "ProgramExpenseRatio": {
        "label": "Program Expense Ratio",
        "format": "percent",
        "description": "Percentage of total expenses spent directly on program services.",
        "benchmark": "75% or higher is considered efficient. Above 85% is excellent.",
    },
    "ManagementGeneralRatio": {
        "label": "Management & General Ratio",
        "format": "percent",
        "description": "Percentage of total expenses spent on administration and management.",
        "benchmark": "Should typically be below 15-20%.",
    },
    "FundraisingRatio": {
        "label": "Fundraising Ratio",
        "format": "percent",
        "description": "Percentage of total expenses spent on fundraising activities.",
        "benchmark": "Should typically be below 15%. Below 10% is efficient.",
    },
    "OperatingMargin": {
        "label": "Operating Margin",
        "format": "percent",
        "description": "Operating surplus as a percentage of total revenue.",
        "benchmark": "Healthy range is 0-10%. Persistent negatives indicate financial stress.",
    },
    "ContributionDependency": {
        "label": "Contribution Dependency",
        "format": "percent",
        "description": "How much of total revenue comes from contributions and grants.",
        "benchmark": "High dependency (>80%) may indicate revenue concentration risk.",
    },
    "LiquidAssets": {
        "label": "Liquid Assets",
        "format": "currency",
        "description": "Cash, savings, and publicly traded investments available for operations.",
        "benchmark": "Should be sufficient to cover 3-6 months of expenses.",
    },
    "MonthsExpenseCoverage": {
        "label": "Months of Expense Coverage",
        "format": "decimal",
        "description": "How many months the organization could operate using only liquid assets.",
        "benchmark": "3-6 months is healthy. Below 3 months indicates vulnerability.",
    },
    "NetOperatingIncome": {
        "label": "Net Operating Income",
        "format": "currency",
        "description": "Revenue from operations (excluding investment gains) minus total expenses.",
        "benchmark": "Shows core operational financial health, independent of investment returns.",
    },
    "NetInvestmentGain": {
        "label": "Net Investment Gain/Loss",
        "format": "currency",
        "description": "Gains or losses from investment activities.",
        "benchmark": "Varies by market conditions. Track trends over multiple years.",
    },
    "DepreciationNonCash": {
        "label": "Depreciation (Non-Cash)",
        "format": "currency",
        "description": "Non-cash expense for the wear and aging of physical assets.",
        "benchmark": "Important for understanding cash vs. accrual-basis performance.",
    },
    "DebtToAssetRatio": {
        "label": "Debt-to-Asset Ratio",
        "format": "percent",
        "description": "Total liabilities as a percentage of total assets.",
        "benchmark": "Below 50% is generally healthy. Above 80% may indicate excessive leverage.",
    },
    "CurrentRatio": {
        "label": "Liquidity Ratio",
        "format": "ratio",
        "description": "Liquid assets divided by total liabilities.",
        "benchmark": "Above 1.0 means liquid assets exceed liabilities. Above 2.0 is strong.",
    },
    "RevenueGrowth": {
        "label": "Revenue Growth (YoY)",
        "format": "percent",
        "description": "Year-over-year change in total revenue.",
        "benchmark": "Positive growth indicates expanding operations or increased support.",
    },
    "ExpenseGrowth": {
        "label": "Expense Growth (YoY)",
        "format": "percent",
        "description": "Year-over-year change in total expenses.",
        "benchmark": "Should be tracked relative to revenue growth. Faster expense growth is a concern.",
    },
    "SalaryToExpenseRatio": {
        "label": "Salary-to-Expense Ratio",
        "format": "percent",
        "description": "Total salaries and compensation as a percentage of total expenses.",
        "benchmark": "Varies by org type. Service orgs are typically 40-60%, grant-makers lower.",
    },
    "NetAssetGrowth": {
        "label": "Net Asset Growth",
        "format": "percent",
        "description": "Year-over-year change in total net assets.",
        "benchmark": "Consistent positive growth indicates financial sustainability.",
    },

    # ── New Metrics (Feedback) ──
    "CashOnly": {
        "label": "Cash (Non-Interest)",
        "format": "currency",
        "description": "Non-interest bearing cash holdings only.",
        "benchmark": "Immediate liquidity. Part of overall cash position.",
    },
    "SavingsOnly": {
        "label": "Savings & Temp Investments",
        "format": "currency",
        "description": "Savings accounts and temporary cash investments.",
        "benchmark": "Near-term liquidity. Combined with cash for total cash position.",
    },
    "CashToLiquidRatio": {
        "label": "Cash / Liquid Assets",
        "format": "percent",
        "description": "Proportion of liquid assets held in non-interest bearing cash.",
        "benchmark": "High ratio may indicate underutilized reserves. Low may indicate illiquidity.",
    },
    "SavingsToLiquidRatio": {
        "label": "Savings / Liquid Assets",
        "format": "percent",
        "description": "Proportion of liquid assets held in savings and temp investments.",
        "benchmark": "Shows how much liquidity is in interest-bearing instruments.",
    },
    "RealizedGains": {
        "label": "Realized Gains",
        "format": "currency",
        "description": "Gains from sold investments that have been realized.",
        "benchmark": "Track alongside unrealized gains for full investment picture.",
    },
    "UnrealizedGains": {
        "label": "Unrealized Gains",
        "format": "currency",
        "description": "Paper gains on investments not yet sold.",
        "benchmark": "Volatile metric. Significant swings may indicate portfolio risk.",
    },
    "TotalInvestmentReturns": {
        "label": "Total Investment Returns",
        "format": "currency",
        "description": "Investment income + unrealized gains + realized gains.",
        "benchmark": "Comprehensive view of investment portfolio performance.",
    },
    "RealEstateAssets": {
        "label": "Real Estate & Property Assets",
        "format": "currency",
        "description": "Land, buildings, and equipment (net of depreciation).",
        "benchmark": "Significant for orgs with large property portfolios. Book value may differ from market.",
    },
    "InvestmentReturnsToLiquid": {
        "label": "Investment Returns / Liquid Assets",
        "format": "percent",
        "description": "Total investment returns as percentage of liquid assets (excl. real estate).",
        "benchmark": "Measures return on liquid portfolio. Compare to market benchmarks.",
    },
    "InvestmentReturnsToAssets": {
        "label": "Investment Returns / Total Assets",
        "format": "percent",
        "description": "Total investment returns as percentage of total assets.",
        "benchmark": "Shows how efficiently the full asset base generates investment returns.",
    },
    "InvestmentReturnsToExpenses": {
        "label": "Investment Returns / Expenses",
        "format": "percent",
        "description": "Total investment returns relative to operating expenses.",
        "benchmark": "Shows how much investment returns subsidize operations.",
    },
}

# Which KPIs to show on the main dashboard summary cards
PRIMARY_KPIS = [
    "OperatingSurplus",
    "ProgramExpenseRatio",
    "OperatingMargin",
    "MonthsExpenseCoverage",
    "ContributionDependency",
    "DebtToAssetRatio",
]

# Which KPIs to chart over time
TREND_KPIS = [
    "OperatingSurplus",
    "TotalCashEquivalents",
    "ProgramExpenseRatio",
    "FundraisingRatio",
    "OperatingMargin",
    "MonthsExpenseCoverage",
    "LiquidAssets",
    "RevenueGrowth",
]

# New investment-focused KPIs
INVESTMENT_KPIS = [
    "CashOnly",
    "SavingsOnly",
    "CashToLiquidRatio",
    "SavingsToLiquidRatio",
    "RealizedGains",
    "UnrealizedGains",
    "TotalInvestmentReturns",
    "RealEstateAssets",
    "InvestmentReturnsToLiquid",
    "InvestmentReturnsToAssets",
    "InvestmentReturnsToExpenses",
]


def format_kpi_value(key, value):
    """Format a KPI value for display based on its type."""
    defn = KPI_DEFINITIONS.get(key, {})
    fmt = defn.get("format", "currency")
    if value is None:
        return "N/A"
    if fmt == "currency":
        if abs(value) >= 1_000_000:
            return f"${value / 1_000_000:,.1f}M"
        elif abs(value) >= 1_000:
            return f"${value / 1_000:,.1f}K"
        else:
            return f"${value:,.0f}"
    elif fmt == "percent":
        return f"{value * 100:.1f}%"
    elif fmt == "decimal":
        return f"{value:.1f}"
    elif fmt == "ratio":
        return f"{value:.2f}x"
    return str(value)


def get_kpi_status(key, value):
    """Return a status indicator (good/warning/concern) based on benchmarks."""
    if key == "ProgramExpenseRatio":
        if value >= 0.75:
            return "good"
        elif value >= 0.65:
            return "warning"
        return "concern"
    elif key == "FundraisingRatio":
        if value <= 0.10:
            return "good"
        elif value <= 0.20:
            return "warning"
        return "concern"
    elif key == "ManagementGeneralRatio":
        if value <= 0.15:
            return "good"
        elif value <= 0.25:
            return "warning"
        return "concern"
    elif key == "OperatingMargin":
        if value >= 0:
            return "good"
        elif value >= -0.05:
            return "warning"
        return "concern"
    elif key == "MonthsExpenseCoverage":
        if value >= 3:
            return "good"
        elif value >= 1:
            return "warning"
        return "concern"
    elif key == "DebtToAssetRatio":
        if value <= 0.5:
            return "good"
        elif value <= 0.7:
            return "warning"
        return "concern"
    elif key == "ContributionDependency":
        if value <= 0.7:
            return "good"
        elif value <= 0.85:
            return "warning"
        return "concern"
    elif key == "OperatingSurplus":
        if value >= 0:
            return "good"
        return "concern"
    elif key == "TotalInvestmentReturns":
        if value > 0:
            return "good"
        elif value == 0:
            return "warning"
        return "concern"
    return "neutral"
