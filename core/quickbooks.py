"""
QuickBooks Report Parser
Parses Profit & Loss and Balance Sheet Excel/CSV exports from QuickBooks
and maps them to the standard flat dict format used by the rest of the app.

Supports:
  - QuickBooks Online and Desktop Excel (.xlsx) exports
  - CSV (.csv) exports
  - Single-period and multi-period comparative reports
  - Automatic P&L vs Balance Sheet detection
  - Merging P&L + Balance Sheet data by year

Developed by Epic Intentions for Brighter Investing
Georgia Institute of Technology — Spring 2026
"""

import io
import re

import pandas as pd

from core.parser import safe_float


# ─── Account Label → Field Key Mappings ───
# Each field maps to a list of lowercase patterns to match against QB row labels.
# Patterns are checked with 'in' matching against the cleaned label.
# Order matters: first match wins per row.

_PL_FIELD_MAP = [
    # ── Revenue (match totals first, then sub-items) ──
    ("TotalRevenue", [
        "total income", "total revenue", "total receipts",
        "total income/revenue",
    ]),
    ("TotalContributionsGrants", [
        "total contributions", "contributions & grants",
        "contributions and grants", "total donations",
    ]),
    ("ProgramServiceRevenue", [
        "program service revenue", "program revenue",
        "service revenue", "fee for service", "fees for service",
    ]),
    ("InvestmentIncome", [
        "investment income", "interest income", "dividend income",
        "interest and dividends", "interest & dividends",
    ]),
    ("OtherRevenue", [
        "other income", "other revenue", "miscellaneous income",
        "total other income",
    ]),
    ("UnrelatedBusinessRevenue", [
        "unrelated business",
    ]),
    ("NetGainLossInvestments", [
        "gain on sale", "loss on sale", "gain/loss",
        "investment gains", "investment losses",
    ]),

    # ── Expenses ──
    ("TotalExpenses", [
        "total expenses", "total expense", "total expenditures",
    ]),
    ("SalariesWages", [
        "salaries and wages", "salaries & wages", "salaries",
        "wages", "payroll expenses", "total payroll expenses",
    ]),
    ("EmployeeBenefits", [
        "employee benefits", "benefits", "health insurance",
        "employee benefit",
    ]),
    ("PensionRetirementContributions", [
        "pension", "retirement", "401k", "403b",
    ]),
    ("PayrollTaxes", [
        "payroll taxes", "payroll tax", "employer taxes",
    ]),
    ("Occupancy", [
        "occupancy", "rent or lease", "rent expense", "rent",
        "utilities",
    ]),
    ("Insurance", [
        "insurance",
    ]),
    ("Travel", [
        "travel", "travel expense",
    ]),
    ("DepreciationAmortization", [
        "depreciation", "amortization", "depreciation and amortization",
        "depreciation & amortization",
    ]),
    ("LegalFees", [
        "legal fees", "legal expense", "legal services",
    ]),
    ("AccountingFees", [
        "accounting fees", "accounting expense", "accounting services",
        "audit fees",
    ]),
    ("OfficeExpenses", [
        "office expenses", "office supplies", "office expense",
    ]),
    ("InformationTechnology", [
        "information technology", "computer expense", "it expense",
        "software", "technology",
    ]),
    ("GrantsAndSimilarPaid", [
        "grants paid", "grants and similar", "grants awarded",
        "grant expense",
    ]),
]

_BS_FIELD_MAP = [
    # ── Assets ──
    ("CashNonInterest", [
        "checking", "petty cash", "cash on hand",
        "cash and cash equivalents", "total bank accounts",
        "total checking/savings",
    ]),
    ("SavingsTempCashInvestments", [
        "savings", "money market",
    ]),
    ("PublicInvestments", [
        "investments", "securities", "marketable securities",
        "publicly traded",
    ]),
    ("Inventory", [
        "inventory",
    ]),
    ("PrepaidExpenses", [
        "prepaid expenses", "prepaid",
    ]),
    ("PropertyEquipmentNet", [
        "total fixed assets", "property and equipment",
        "furniture and equipment", "fixed assets",
        "net fixed assets",
    ]),
    ("OtherAssets", [
        "other assets", "total other assets",
    ]),
    ("TotalAssets", [
        "total assets",
    ]),

    # ── Liabilities ──
    ("AccountsPayableAccrued", [
        "accounts payable", "accrued liabilities",
        "accrued expenses",
    ]),
    ("OtherLiabilities", [
        "other liabilities", "other current liabilities",
        "long term liabilities", "total long-term liabilities",
    ]),
    ("TotalLiabilities", [
        "total liabilities",
    ]),

    # ── Net Assets / Equity ──
    ("NetAssetsWithoutDonorRestrictions", [
        "unrestricted net assets", "net assets without donor",
    ]),
    ("NetAssetsWithDonorRestrictions", [
        "restricted net assets", "net assets with donor",
        "temporarily restricted", "permanently restricted",
    ]),
    ("TotalNetAssets", [
        "total equity", "total net assets",
    ]),
]

# Fields that only exist on Form 990 and cannot come from QuickBooks
_QB_UNAVAILABLE_FIELDS = [
    "GrossReceipts",
    "PriorYearRevenue",
    "PriorYearExpenses",
    "PriorYearContributions",
    "GovernmentGrants",
    "ContributionsGrantsOther",
    "ProgramExpenses",
    "ManagementGeneralExpenses",
    "FundraisingExpenses",
    "TotalAssetsBOY",
    "TotalLiabilitiesBOY",
    "TotalNetAssetsBOY",
    "EmployeeCount",
    "Volunteers",
    "VotingBoardMembers",
    "IndependentBoardMembers",
    "ExecutiveDirectorCompensation",
    "DonatedServicesFacilities",
    "RealizedGainsSecurities",
    "UnrealizedGainsSecurities",
    "RealEstateAssets",
    "Mission",
    "FormationType",
]


# ─── Helpers ───

def _clean_label(text):
    """Normalize a QB account label for matching.

    Strips account numbers (e.g. '6000'), whitespace, and lowercases.
    """
    s = str(text).strip()
    # Remove leading account numbers like "6000 " or "6000-"
    s = re.sub(r"^\d{3,5}[\s\-·]*", "", s)
    return s.lower().strip()


def _match_label(label, field_map):
    """Match a cleaned label against a field mapping list.

    Returns the field key if a match is found, else None.
    Excludes composite rows like 'total liabilities and equity' from
    matching individual fields.
    """
    # Skip composite total rows that would cause false matches
    if "liabilities and equity" in label or "liabilities & equity" in label:
        return None

    for field_key, patterns in field_map:
        for pattern in patterns:
            if pattern in label:
                return field_key
    return None


def _extract_year(text):
    """Extract a 4-digit year from a date/period string.

    For ranges like 'Jan 2023 - Dec 2024', returns the end year (2024).
    """
    years = re.findall(r"\b(20\d{2})\b", str(text))
    if years:
        return years[-1]  # Use the latest year for ranges
    return None


def _find_label_col(df):
    """Find the column index that contains account labels (most text values)."""
    best_col = 0
    best_count = 0
    for col_idx in range(min(3, len(df.columns))):
        count = df.iloc[:, col_idx].dropna().apply(
            lambda x: isinstance(x, str) and len(x.strip()) > 2
        ).sum()
        if count > best_count:
            best_count = count
            best_col = col_idx
    return best_col


def _find_value_cols(df, label_col):
    """Find column indices that contain numeric financial data.

    Returns list of (col_index, period_label) tuples.
    """
    value_cols = []
    for col_idx in range(label_col + 1, len(df.columns)):
        col_data = df.iloc[:, col_idx]
        # Check if this column has numeric data
        numeric_count = 0
        for val in col_data:
            if isinstance(val, (int, float)):
                numeric_count += 1
            elif isinstance(val, str):
                cleaned = val.replace(",", "").replace("$", "").replace("(", "-").replace(")", "").strip()
                try:
                    float(cleaned)
                    numeric_count += 1
                except (ValueError, TypeError):
                    pass
        if numeric_count >= 3:
            # Try to find a period label in the header rows for this column
            period_label = ""
            for row_idx in range(min(10, len(df))):
                cell = df.iloc[row_idx, col_idx]
                if isinstance(cell, str) and len(cell.strip()) > 2:
                    period_label = cell.strip()
                    break
            value_cols.append((col_idx, period_label))
    return value_cols


def _extract_org_name(df, label_col):
    """Try to extract the organization/company name from the report header."""
    # Typically in the first 5 rows, in the label column
    for row_idx in range(min(5, len(df))):
        cell = str(df.iloc[row_idx, label_col]).strip()
        lower = cell.lower()
        # Skip report title rows
        if any(skip in lower for skip in [
            "profit and loss", "profit & loss", "balance sheet",
            "income statement", "statement of", "trial balance",
            "total", "as of",
        ]):
            continue
        # Skip date ranges
        if re.search(r"\b(january|february|march|april|may|june|july|august|"
                      r"september|october|november|december|jan|feb|mar|apr|"
                      r"may|jun|jul|aug|sep|oct|nov|dec)\b", lower):
            continue
        # Skip empty or very short
        if len(cell) < 3 or cell.lower() in ("nan", "none", ""):
            continue
        # This is likely the company name
        return cell
    return "Unknown Organization"


def _extract_report_period(df, label_col):
    """Extract the report period/date range from the header rows."""
    for row_idx in range(min(8, len(df))):
        cell = str(df.iloc[row_idx, label_col]).strip()
        year = _extract_year(cell)
        if year:
            return cell, year
    # Also check other columns
    for col_idx in range(len(df.columns)):
        for row_idx in range(min(8, len(df))):
            cell = str(df.iloc[row_idx, col_idx]).strip()
            year = _extract_year(cell)
            if year:
                return cell, year
    return "", ""


def _detect_report_type(df, label_col):
    """Detect whether this is a P&L or Balance Sheet report.

    Returns 'pl', 'bs', or 'unknown'.
    """
    all_labels = " ".join(
        str(df.iloc[i, label_col]).lower()
        for i in range(min(len(df), 50))
        if pd.notna(df.iloc[i, label_col])
    )

    pl_signals = sum(1 for kw in [
        "income", "revenue", "expense", "net income",
        "cost of goods", "gross profit",
    ] if kw in all_labels)

    bs_signals = sum(1 for kw in [
        "assets", "liabilities", "equity", "net assets",
        "accounts payable", "fixed assets", "checking",
    ] if kw in all_labels)

    if pl_signals > bs_signals:
        return "pl"
    if bs_signals > pl_signals:
        return "bs"
    return "unknown"


def _empty_qb_row(org_name="", tax_year=""):
    """Create an empty flat dict with QB-unavailable fields set to None."""
    row = {
        "SourceFile": "",
        "DataSource": "quickbooks",
        "OrganizationName": org_name,
        "EIN": "",
        "TaxYear": tax_year,
        "TaxPeriodBegin": "",
        "TaxPeriodEnd": "",
        "State": "",
        "City": "",
        "Website": "",
    }
    # Set unavailable fields to None (not 0) so KPIs show N/A
    for field in _QB_UNAVAILABLE_FIELDS:
        row[field] = None
    return row


# ─── Main Parsing Functions ───

def parse_quickbooks_report(file_bytes, filename="quickbooks_report"):
    """
    Parse a single QuickBooks Excel or CSV export file.

    Auto-detects whether the file is a Profit & Loss or Balance Sheet
    and extracts financial data into the standard flat dict format.

    Parameters:
        file_bytes: bytes content of the Excel/CSV file
        filename: original filename for reference

    Returns:
        list of dicts — one per period/year found in the report.
        Each dict is a *partial* record (P&L fields OR Balance Sheet fields).

    Raises:
        ValueError: if the file cannot be parsed or is not a recognized QB report
    """
    if not file_bytes or len(file_bytes) == 0:
        raise ValueError(f"{filename}: File is empty.")

    # Read into DataFrame
    try:
        if filename.lower().endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes), header=None)
        else:
            df = pd.read_excel(io.BytesIO(file_bytes), header=None)
    except Exception as e:
        raise ValueError(
            f"{filename}: Could not read file — {str(e)[:120]}. "
            "Please export as Excel (.xlsx) or CSV (.csv) from QuickBooks."
        )

    if df.empty or len(df) < 3:
        raise ValueError(f"{filename}: File appears to be empty or too short.")

    # Detect structure
    label_col = _find_label_col(df)
    report_type = _detect_report_type(df, label_col)

    if report_type == "unknown":
        raise ValueError(
            f"{filename}: Could not determine report type. "
            "Please upload a Profit & Loss or Balance Sheet report from QuickBooks."
        )

    field_map = _PL_FIELD_MAP if report_type == "pl" else _BS_FIELD_MAP

    # Extract metadata
    org_name = _extract_org_name(df, label_col)
    _, default_year = _extract_report_period(df, label_col)

    # Find value columns
    value_cols = _find_value_cols(df, label_col)
    if not value_cols:
        # Fallback: use the column right after labels
        if label_col + 1 < len(df.columns):
            value_cols = [(label_col + 1, "")]
        else:
            raise ValueError(
                f"{filename}: No numeric data columns found. "
                "Please ensure the report includes financial amounts."
            )

    # Parse each period column
    results = []
    for col_idx, period_label in value_cols:
        # Determine year for this column
        year = _extract_year(period_label) or default_year or ""

        row = _empty_qb_row(org_name, year)
        row["SourceFile"] = filename
        row["_report_type"] = report_type

        # Walk through data rows and match labels
        for row_idx in range(len(df)):
            raw_label = df.iloc[row_idx, label_col]
            if pd.isna(raw_label):
                continue
            cleaned = _clean_label(raw_label)
            if not cleaned or len(cleaned) < 2:
                continue

            raw_value = df.iloc[row_idx, col_idx]
            value = safe_float(raw_value)

            matched_field = _match_label(cleaned, field_map)
            if matched_field:
                # For total fields, always overwrite (last match = the total row)
                # For sub-item fields, keep the first match or accumulate
                if matched_field.startswith("Total") or row.get(matched_field) is None:
                    row[matched_field] = value
                elif isinstance(row.get(matched_field), (int, float)) and row[matched_field] == 0:
                    row[matched_field] = value

        results.append(row)

    return results


def merge_quickbooks_data(all_partial_rows):
    """
    Merge partial dicts from multiple QB report files by year.

    When a user uploads both a P&L and a Balance Sheet, this merges
    the fields from each into a single combined record per year.

    Parameters:
        all_partial_rows: list of partial dicts from parse_quickbooks_report()

    Returns:
        list of merged flat dicts (one per year), sorted by TaxYear
    """
    by_year = {}
    org_name = ""

    for row in all_partial_rows:
        year = row.get("TaxYear", "")
        if not org_name:
            org_name = row.get("OrganizationName", "")

        if year not in by_year:
            by_year[year] = _empty_qb_row(org_name, year)

        target = by_year[year]

        # Merge fields: non-None values from the new row overwrite
        for key, value in row.items():
            if key in ("_report_type",):
                continue
            if value is not None and value != "":
                # Don't overwrite a real value with 0
                existing = target.get(key)
                if existing is None or existing == "" or existing == 0:
                    target[key] = value
                elif key == "SourceFile" and value not in existing:
                    target[key] = f"{existing}, {value}"

    # Ensure consistent org name
    for row in by_year.values():
        if not row.get("OrganizationName") or row["OrganizationName"] == "Unknown Organization":
            row["OrganizationName"] = org_name
        # Clean up internal fields
        row.pop("_report_type", None)

    return sorted(by_year.values(), key=lambda r: r.get("TaxYear", ""))


def apply_supplement_data(rows, supplement):
    """
    Apply user-provided supplement data to fill in QuickBooks gaps.

    Parameters:
        rows: list of flat dicts (QB-sourced data)
        supplement: dict with user-entered values from the supplement form

    Returns:
        The rows list, modified in place with supplemental data applied.
    """
    for row in rows:
        if row.get("DataSource") != "quickbooks":
            continue

        # Organization info
        if supplement.get("EIN"):
            row["EIN"] = supplement["EIN"]
        if supplement.get("Mission"):
            row["Mission"] = supplement["Mission"]

        # Governance
        if supplement.get("VotingBoardMembers") is not None:
            row["VotingBoardMembers"] = supplement["VotingBoardMembers"]
        if supplement.get("IndependentBoardMembers") is not None:
            row["IndependentBoardMembers"] = supplement["IndependentBoardMembers"]
        if supplement.get("Volunteers") is not None:
            row["Volunteers"] = supplement["Volunteers"]
        if supplement.get("EmployeeCount") is not None:
            row["EmployeeCount"] = supplement["EmployeeCount"]
        if supplement.get("ExecutiveDirectorCompensation") is not None:
            row["ExecutiveDirectorCompensation"] = supplement[
                "ExecutiveDirectorCompensation"
            ]

        # Functional expense split (percentages applied to TotalExpenses)
        total_exp = row.get("TotalExpenses") or 0
        if total_exp > 0:
            if supplement.get("ProgramExpensePct") is not None:
                row["ProgramExpenses"] = total_exp * (
                    supplement["ProgramExpensePct"] / 100
                )
            if supplement.get("ManagementExpensePct") is not None:
                row["ManagementGeneralExpenses"] = total_exp * (
                    supplement["ManagementExpensePct"] / 100
                )
            if supplement.get("FundraisingExpensePct") is not None:
                row["FundraisingExpenses"] = total_exp * (
                    supplement["FundraisingExpensePct"] / 100
                )

    return rows
