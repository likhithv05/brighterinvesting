"""
Form 990 XML Parser
Extracts financial data from IRS Form 990 XML filings.

Developed by Epic Intentions for Brighter Investing
Georgia Institute of Technology — Spring 2026
"""

import os
import xmltodict


def safe_float(value):
    """Convert a value to float, handling None, empty strings, and formatting."""
    if value in (None, ""):
        return 0.0
    try:
        return float(str(value).replace(",", "").replace("$", ""))
    except (ValueError, TypeError):
        return 0.0


def get_text(d, *path, default=""):
    """Safely traverse nested dicts to extract text values."""
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    if isinstance(cur, dict) and "#text" in cur:
        return cur["#text"]
    return cur if isinstance(cur, str) else default


def grp_amt(d, grp, field="TotalAmt"):
    """Extract amounts from *Grp nodes, handling both dict and list formats."""
    value = d.get(grp, {})
    if isinstance(value, list):
        return sum(safe_float(item.get(field, 0)) for item in value)
    if isinstance(value, dict):
        return safe_float(value.get(field, 0))
    return 0.0


def extract_other_expenses_by_desc(f990, description):
    """Extract a specific expense line from OtherExpensesGrp by description match."""
    other_expenses = f990.get("OtherExpensesGrp", [])
    if isinstance(other_expenses, dict):
        other_expenses = [other_expenses]
    if not isinstance(other_expenses, list):
        return 0.0
    for expense in other_expenses:
        desc = expense.get("Desc", "")
        if description.upper() in desc.upper():
            return safe_float(expense.get("TotalAmt", 0))
    return 0.0


def extract_executive_director_compensation(f990):
    """Extract Executive Director compensation from Part VII Section A."""
    section_a = f990.get("Form990PartVIISectionAGrp", [])
    if isinstance(section_a, dict):
        section_a = [section_a]
    if not isinstance(section_a, list):
        return 0.0
    for person in section_a:
        title = person.get("TitleTxt", "")
        if "EXECUTIVE DIRECTOR" in title.upper() or "CEO" in title.upper():
            return safe_float(person.get("ReportableCompFromOrgAmt", 0))
    return 0.0


def validate_parsed_row(row):
    """
    Validate critical fields in a parsed Form 990 record.

    Returns:
        (is_valid, list_of_issues)
    """
    issues = []
    if not row.get("EIN"):
        issues.append("Missing EIN (Employer Identification Number)")
    if not row.get("TaxYear"):
        issues.append("Missing Tax Year")
    if not row.get("OrganizationName") or row.get("OrganizationName") == "Unknown":
        issues.append("Missing Organization Name")
    if row.get("TotalRevenue", 0) == 0 and row.get("TotalExpenses", 0) == 0:
        issues.append("Both Total Revenue and Total Expenses are zero — file may be incomplete")
    return (len(issues) == 0, issues)


def parse_single_xml(xml_bytes, filename="uploaded.xml"):
    """
    Parse a single Form 990 XML file and return a flat dict of extracted fields.

    Parameters:
        xml_bytes: bytes content of the XML file
        filename: original filename for reference

    Returns:
        dict with all extracted financial fields

    Raises:
        ValueError: if the file is not valid XML, not a Form 990, or missing critical fields
    """
    if not xml_bytes or len(xml_bytes) == 0:
        raise ValueError(f"{filename}: File is empty.")

    try:
        doc = xmltodict.parse(
            xml_bytes,
            attr_prefix="@",
            cdata_key="#text",
            dict_constructor=dict,
        )
    except Exception as e:
        raise ValueError(f"{filename}: Malformed XML — {str(e)[:120]}")

    if "Return" not in doc:
        raise ValueError(
            f"{filename}: Not a valid IRS Form 990 XML file (missing <Return> root element)."
        )

    ret_hdr = doc.get("Return", {}).get("ReturnHeader", {}) or {}
    ret_dat = doc.get("Return", {}).get("ReturnData", {}) or {}
    f990 = ret_dat.get("IRS990", {}) or ret_dat.get("IRS990EZ", {}) or {}

    if not f990:
        raise ValueError(
            f"{filename}: No IRS990 or IRS990EZ data found. "
            "This may be a different form type (e.g., 990-PF, 990-T)."
        )

    result = {
        "SourceFile": filename,
        "OrganizationName": get_text(
            ret_hdr, "Filer", "BusinessName", "BusinessNameLine1Txt", default="Unknown"
        ),
        "EIN": get_text(ret_hdr, "Filer", "EIN", default=""),
        "TaxYear": get_text(ret_hdr, "TaxYr", default=""),
        "TaxPeriodBegin": get_text(ret_hdr, "TaxPeriodBeginDt", default=""),
        "TaxPeriodEnd": get_text(ret_hdr, "TaxPeriodEndDt", default=""),
        "State": get_text(ret_hdr, "Filer", "USAddress", "StateAbbreviationCd", default=""),
        "City": get_text(ret_hdr, "Filer", "USAddress", "CityNm", default=""),
        "Website": get_text(f990, "WebsiteAddressTxt", default=""),
        "FormationType": get_text(f990, "FormationYr", default=""),
        "Mission": get_text(f990, "MissionDesc", default=""),

        # Revenue
        "TotalRevenue": safe_float(f990.get("CYTotalRevenueAmt")),
        "PriorYearRevenue": safe_float(f990.get("PYTotalRevenueAmt")),
        "GrossReceipts": safe_float(f990.get("GrossReceiptsAmt")),
        "TotalContributionsGrants": safe_float(f990.get("CYContributionsGrantsAmt")),
        "PriorYearContributions": safe_float(f990.get("PYContributionsGrantsAmt")),
        "GovernmentGrants": safe_float(f990.get("GovernmentGrantsAmt")),
        "ContributionsGrantsOther": safe_float(f990.get("AllOtherContributionsAmt")),
        "ProgramServiceRevenue": safe_float(f990.get("CYProgramServiceRevenueAmt")),
        "InvestmentIncome": safe_float(f990.get("CYInvestmentIncomeAmt")),
        "OtherRevenue": safe_float(f990.get("CYOtherRevenueAmt")),
        "UnrelatedBusinessRevenue": safe_float(f990.get("TotalGrossUBIAmt")),
        "NetGainLossInvestments": safe_float(
            f990.get("NetGainOrLossInvestmentsGrp", {}).get("TotalRevenueColumnAmt", 0)
        ),

        # Expenses
        "TotalExpenses": safe_float(f990.get("CYTotalExpensesAmt")),
        "PriorYearExpenses": safe_float(f990.get("PYTotalExpensesAmt")),
        "ProgramExpenses": safe_float(f990.get("TotalProgramServiceExpensesAmt")),
        "ManagementGeneralExpenses": safe_float(
            f990.get("TotalFunctionalExpensesGrp", {}).get("ManagementAndGeneralAmt", 0)
        ),
        "FundraisingExpenses": safe_float(f990.get("CYTotalFundraisingExpenseAmt")),
        "SalariesWages": safe_float(f990.get("CYSalariesCompEmpBnftPaidAmt")),
        "PensionRetirementContributions": grp_amt(f990, "PensionPlanContributionsGrp"),
        "EmployeeBenefits": grp_amt(f990, "OtherEmployeeBenefitsGrp"),
        "PayrollTaxes": grp_amt(f990, "PayrollTaxesGrp"),
        "LegalFees": grp_amt(f990, "FeesForServicesLegalGrp"),
        "AccountingFees": grp_amt(f990, "FeesForServicesAccountingGrp"),
        "OfficeExpenses": grp_amt(f990, "OfficeExpensesGrp"),
        "InformationTechnology": grp_amt(f990, "InformationTechnologyGrp"),
        "Occupancy": grp_amt(f990, "OccupancyGrp"),
        "Travel": grp_amt(f990, "TravelGrp"),
        "DepreciationAmortization": grp_amt(f990, "DepreciationDepletionGrp"),
        "Insurance": grp_amt(f990, "InsuranceGrp"),
        "GrantsAndSimilarPaid": safe_float(f990.get("CYGrantsAndSimilarPaidAmt")),
        "OtherExpenses": grp_amt(f990, "OtherExpensesGrp"),

        # Assets
        "CashNonInterest": grp_amt(f990, "CashNonInterestBearingGrp", "EOYAmt"),
        "SavingsTempCashInvestments": grp_amt(f990, "SavingsAndTempCashInvstGrp", "EOYAmt"),
        "PublicInvestments": grp_amt(f990, "InvestmentsPubTradedSecGrp", "EOYAmt"),
        "Inventory": grp_amt(f990, "InventoriesForSaleOrUseGrp", "EOYAmt"),
        "PrepaidExpenses": grp_amt(f990, "PrepaidExpensesDefrdChargesGrp", "EOYAmt"),
        "PropertyEquipmentNet": grp_amt(f990, "LandBldgEquipBasisNetGrp", "EOYAmt"),
        "OtherAssets": grp_amt(f990, "OtherAssetsTotalGrp", "EOYAmt"),
        "TotalAssets": safe_float(f990.get("TotalAssetsEOYAmt")),
        "TotalAssetsBOY": safe_float(f990.get("TotalAssetsBOYAmt")),

        # Liabilities & Net Assets
        "AccountsPayableAccrued": grp_amt(f990, "AccountsPayableAccrExpnssGrp", "EOYAmt"),
        "OtherLiabilities": grp_amt(f990, "OtherLiabilitiesGrp", "EOYAmt"),
        "TotalLiabilities": safe_float(f990.get("TotalLiabilitiesEOYAmt")),
        "TotalLiabilitiesBOY": safe_float(f990.get("TotalLiabilitiesBOYAmt")),
        "NetAssetsWithoutDonorRestrictions": grp_amt(
            f990, "NoDonorRestrictionNetAssetsGrp", "EOYAmt"
        ),
        "NetAssetsWithDonorRestrictions": grp_amt(
            f990, "DonorRestrictionNetAssetsGrp", "EOYAmt"
        ),
        "TotalNetAssets": safe_float(f990.get("NetAssetsOrFundBalancesEOYAmt")),
        "TotalNetAssetsBOY": safe_float(f990.get("NetAssetsOrFundBalancesBOYAmt")),

        # Governance & Workforce
        "EmployeeCount": safe_float(f990.get("TotalEmployeeCnt") or f990.get("EmployeeCnt")),
        "Volunteers": safe_float(f990.get("TotalVolunteersCnt")),
        "VotingBoardMembers": safe_float(f990.get("VotingMembersGoverningBodyCnt")),
        "IndependentBoardMembers": safe_float(
            f990.get("VotingMembersIndependentCnt") or f990.get("IndependentVotingMemberCnt")
        ),
        "ExecutiveDirectorCompensation": extract_executive_director_compensation(f990),
        "DonatedServicesFacilities": safe_float(f990.get("NoncashContributionsAmt")),

        # Investment detail fields (for expanded KPIs)
        "RealizedGainsSecurities": safe_float(
            f990.get("GainOrLossFromSaleOtherAssets", {}).get("TotalRevenueColumnAmt", 0)
        ) if isinstance(f990.get("GainOrLossFromSaleOtherAssets"), dict) else 0.0,
        "UnrealizedGainsSecurities": safe_float(
            f990.get("NetUnrealizedGainsInvestmentsGrp", {}).get("EOYAmt", 0)
        ) if isinstance(f990.get("NetUnrealizedGainsInvestmentsGrp"), dict) else 0.0,
        "RealEstateAssets": (
            grp_amt(f990, "LandBldgEquipBasisNetGrp", "EOYAmt")
            + safe_float(f990.get("OtherLandBuildingsAmt", 0))
        ),
    }

    # Validate critical fields and warn (but don't block)
    is_valid, issues = validate_parsed_row(result)
    if not is_valid:
        import warnings
        for issue in issues:
            warnings.warn(f"{filename}: {issue}")

    return result


# Field groupings for display and export
FIELD_GROUPS = {
    "Organization Info": [
        "SourceFile", "OrganizationName", "EIN", "TaxYear",
        "TaxPeriodBegin", "TaxPeriodEnd", "State", "City",
        "Website", "FormationType",
    ],
    "Revenue": [
        "TotalRevenue", "PriorYearRevenue", "GrossReceipts",
        "TotalContributionsGrants", "PriorYearContributions",
        "GovernmentGrants", "ContributionsGrantsOther",
        "ProgramServiceRevenue", "InvestmentIncome",
        "OtherRevenue", "UnrelatedBusinessRevenue",
        "NetGainLossInvestments",
    ],
    "Expenses": [
        "TotalExpenses", "PriorYearExpenses", "ProgramExpenses",
        "ManagementGeneralExpenses", "FundraisingExpenses",
        "SalariesWages", "PensionRetirementContributions",
        "EmployeeBenefits", "PayrollTaxes", "LegalFees",
        "AccountingFees", "OfficeExpenses", "InformationTechnology",
        "Occupancy", "Travel", "DepreciationAmortization",
        "Insurance", "GrantsAndSimilarPaid", "OtherExpenses",
    ],
    "Assets": [
        "CashNonInterest", "SavingsTempCashInvestments",
        "PublicInvestments", "Inventory", "PrepaidExpenses",
        "PropertyEquipmentNet", "OtherAssets",
        "TotalAssets", "TotalAssetsBOY",
    ],
    "Liabilities & Net Assets": [
        "AccountsPayableAccrued", "OtherLiabilities",
        "TotalLiabilities", "TotalLiabilitiesBOY",
        "NetAssetsWithoutDonorRestrictions",
        "NetAssetsWithDonorRestrictions",
        "TotalNetAssets", "TotalNetAssetsBOY",
    ],
    "Governance & Workforce": [
        "EmployeeCount", "Volunteers", "VotingBoardMembers",
        "IndependentBoardMembers", "ExecutiveDirectorCompensation",
        "DonatedServicesFacilities",
    ],
    "Investment Detail": [
        "RealizedGainsSecurities", "UnrealizedGainsSecurities",
        "RealEstateAssets",
    ],
}

# Human-readable labels
FIELD_LABELS = {
    "SourceFile": "Source File",
    "OrganizationName": "Organization Name",
    "EIN": "EIN",
    "TaxYear": "Tax Year",
    "TaxPeriodBegin": "Tax Period Start",
    "TaxPeriodEnd": "Tax Period End",
    "State": "State",
    "City": "City",
    "Website": "Website",
    "FormationType": "Formation Year",
    "Mission": "Mission Statement",
    "TotalRevenue": "Total Revenue",
    "PriorYearRevenue": "Prior Year Revenue",
    "GrossReceipts": "Gross Receipts",
    "TotalContributionsGrants": "Contributions & Grants",
    "PriorYearContributions": "Prior Year Contributions",
    "GovernmentGrants": "Government Grants",
    "ContributionsGrantsOther": "Other Contributions",
    "ProgramServiceRevenue": "Program Service Revenue",
    "InvestmentIncome": "Investment Income",
    "OtherRevenue": "Other Revenue",
    "UnrelatedBusinessRevenue": "Unrelated Business Revenue",
    "NetGainLossInvestments": "Net Gain/Loss on Investments",
    "TotalExpenses": "Total Expenses",
    "PriorYearExpenses": "Prior Year Expenses",
    "ProgramExpenses": "Program Service Expenses",
    "ManagementGeneralExpenses": "Management & General",
    "FundraisingExpenses": "Fundraising Expenses",
    "SalariesWages": "Salaries & Wages",
    "PensionRetirementContributions": "Pension Contributions",
    "EmployeeBenefits": "Employee Benefits",
    "PayrollTaxes": "Payroll Taxes",
    "LegalFees": "Legal Fees",
    "AccountingFees": "Accounting Fees",
    "OfficeExpenses": "Office Expenses",
    "InformationTechnology": "Information Technology",
    "Occupancy": "Occupancy",
    "Travel": "Travel",
    "DepreciationAmortization": "Depreciation & Amortization",
    "Insurance": "Insurance",
    "GrantsAndSimilarPaid": "Grants & Similar Paid",
    "OtherExpenses": "Other Expenses",
    "CashNonInterest": "Cash (Non-Interest Bearing)",
    "SavingsTempCashInvestments": "Savings & Temp Investments",
    "PublicInvestments": "Publicly Traded Securities",
    "Inventory": "Inventory",
    "PrepaidExpenses": "Prepaid Expenses",
    "PropertyEquipmentNet": "Property & Equipment (Net)",
    "OtherAssets": "Other Assets",
    "TotalAssets": "Total Assets (EOY)",
    "TotalAssetsBOY": "Total Assets (BOY)",
    "AccountsPayableAccrued": "Accounts Payable",
    "OtherLiabilities": "Other Liabilities",
    "TotalLiabilities": "Total Liabilities (EOY)",
    "TotalLiabilitiesBOY": "Total Liabilities (BOY)",
    "NetAssetsWithoutDonorRestrictions": "Unrestricted Net Assets",
    "NetAssetsWithDonorRestrictions": "Donor-Restricted Net Assets",
    "TotalNetAssets": "Total Net Assets (EOY)",
    "TotalNetAssetsBOY": "Total Net Assets (BOY)",
    "EmployeeCount": "Number of Employees",
    "Volunteers": "Number of Volunteers",
    "VotingBoardMembers": "Voting Board Members",
    "IndependentBoardMembers": "Independent Board Members",
    "ExecutiveDirectorCompensation": "Exec. Director Compensation",
    "DonatedServicesFacilities": "Donated Services & Facilities",
    "RealizedGainsSecurities": "Realized Gains (Securities)",
    "UnrealizedGainsSecurities": "Unrealized Gains (Securities)",
    "RealEstateAssets": "Real Estate & Land Assets",
}
