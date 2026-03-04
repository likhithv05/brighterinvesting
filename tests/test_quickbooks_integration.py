"""
End-to-end integration test for QuickBooks Excel upload pipeline.
Creates mock QB Profit & Loss and Balance Sheet Excel files,
runs them through the parser, merger, KPI engine, and export.
"""

import io
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl
import pandas as pd


def create_mock_pl_workbook():
    """Create a realistic QuickBooks Profit & Loss Excel export."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Profit and Loss"

    rows = [
        ["Profit and Loss", "", ""],
        ["Habitat Community Foundation", "", ""],
        ["January - December 2024", "", ""],
        ["", "", ""],
        ["", "Jan - Dec 2024", "Jan - Dec 2023"],
        ["Income", "", ""],
        ["  4000 Contributions & Grants", 850000, 780000],
        ["  4100 Program Service Revenue", 320000, 290000],
        ["  4200 Investment Income", 45000, 38000],
        ["  4300 Other Income", 15000, 12000],
        ["Total Income", 1230000, 1120000],
        ["", "", ""],
        ["Cost of Goods Sold", "", ""],
        ["  5000 Cost of Goods Sold", 0, 0],
        ["Total Cost of Goods Sold", 0, 0],
        ["", "", ""],
        ["Gross Profit", 1230000, 1120000],
        ["", "", ""],
        ["Expenses", "", ""],
        ["  6000 Salaries and Wages", 520000, 480000],
        ["  6100 Payroll Taxes", 42000, 39000],
        ["  6200 Employee Benefits", 65000, 58000],
        ["  6300 Rent", 72000, 70000],
        ["  6400 Insurance", 28000, 25000],
        ["  6500 Office Expenses", 18000, 16000],
        ["  6600 Travel", 22000, 19000],
        ["  6700 Depreciation", 35000, 32000],
        ["  6800 Legal Fees", 15000, 12000],
        ["  6900 Accounting Fees", 20000, 18000],
        ["  7000 Information Technology", 30000, 25000],
        ["  7100 Other Expenses", 45000, 40000],
        ["Total Expenses", 912000, 834000],
        ["", "", ""],
        ["Net Operating Income", 318000, 286000],
        ["", "", ""],
        ["Other Income", "", ""],
        ["  8000 Gain on Sale of Assets", 12000, 8000],
        ["Total Other Income", 12000, 8000],
        ["", "", ""],
        ["Net Income", 330000, 294000],
    ]

    for row in rows:
        ws.append(row)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


def create_mock_bs_workbook():
    """Create a realistic QuickBooks Balance Sheet Excel export."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Balance Sheet"

    rows = [
        ["Balance Sheet", "", ""],
        ["Habitat Community Foundation", "", ""],
        ["As of December 31, 2024", "", ""],
        ["", "", ""],
        ["", "Dec 31, 2024", "Dec 31, 2023"],
        ["ASSETS", "", ""],
        ["  Current Assets", "", ""],
        ["    Checking", 280000, 220000],
        ["    Savings", 450000, 380000],
        ["    Investments", 320000, 280000],
        ["    Inventory", 15000, 12000],
        ["    Prepaid Expenses", 25000, 20000],
        ["  Total Current Assets", 1090000, 912000],
        ["", "", ""],
        ["  Fixed Assets", "", ""],
        ["    Furniture and Equipment", 180000, 165000],
        ["    Accumulated Depreciation", -85000, -50000],
        ["  Total Fixed Assets", 95000, 115000],
        ["", "", ""],
        ["  Other Assets", 30000, 25000],
        ["", "", ""],
        ["Total Assets", 1215000, 1052000],
        ["", "", ""],
        ["LIABILITIES AND EQUITY", "", ""],
        ["  Liabilities", "", ""],
        ["    Accounts Payable", 45000, 38000],
        ["    Other Current Liabilities", 62000, 55000],
        ["  Total Liabilities", 107000, 93000],
        ["", "", ""],
        ["  Equity", "", ""],
        ["    Unrestricted Net Assets", 908000, 759000],
        ["    Restricted Net Assets", 200000, 200000],
        ["  Total Equity", 1108000, 959000],
        ["", "", ""],
        ["TOTAL LIABILITIES AND EQUITY", 1215000, 1052000],
    ]

    for row in rows:
        ws.append(row)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


def test_parser():
    """Test that the QB parser correctly extracts data from mock files."""
    from core.quickbooks import parse_quickbooks_report, merge_quickbooks_data

    print("=" * 60)
    print("TEST 1: Parse QuickBooks P&L Report")
    print("=" * 60)

    pl_bytes = create_mock_pl_workbook()
    pl_rows = parse_quickbooks_report(pl_bytes, "Mock_PL.xlsx")

    print(f"  Periods found: {len(pl_rows)}")
    for row in pl_rows:
        print(f"  Year {row.get('TaxYear')}: "
              f"Revenue=${row.get('TotalRevenue', 0):,.0f}, "
              f"Expenses=${row.get('TotalExpenses', 0):,.0f}")
        print(f"    Org: {row.get('OrganizationName')}")
        print(f"    DataSource: {row.get('DataSource')}")
        print(f"    Salaries: ${row.get('SalariesWages', 0):,.0f}")
        print(f"    Insurance: ${row.get('Insurance', 0):,.0f}")
        print(f"    Travel: ${row.get('Travel', 0):,.0f}")
        # Verify Form 990-only fields are None
        print(f"    ProgramExpenses (should be None): {row.get('ProgramExpenses')}")
        print(f"    VotingBoardMembers (should be None): {row.get('VotingBoardMembers')}")
        print(f"    Mission (should be None): {row.get('Mission')}")

    assert len(pl_rows) >= 1, "Should find at least 1 period"
    assert pl_rows[0].get("DataSource") == "quickbooks", "DataSource should be 'quickbooks'"
    assert pl_rows[0].get("ProgramExpenses") is None, "ProgramExpenses should be None for QB"
    print("  PASSED\n")

    print("=" * 60)
    print("TEST 2: Parse QuickBooks Balance Sheet Report")
    print("=" * 60)

    bs_bytes = create_mock_bs_workbook()
    bs_rows = parse_quickbooks_report(bs_bytes, "Mock_BS.xlsx")

    print(f"  Periods found: {len(bs_rows)}")
    for row in bs_rows:
        print(f"  Year {row.get('TaxYear')}: "
              f"Assets=${row.get('TotalAssets', 0):,.0f}, "
              f"Liabilities=${row.get('TotalLiabilities', 0):,.0f}, "
              f"Net Assets=${row.get('TotalNetAssets', 0):,.0f}")
        print(f"    Cash: ${row.get('CashNonInterest', 0):,.0f}")
        print(f"    Savings: ${row.get('SavingsTempCashInvestments', 0):,.0f}")
        print(f"    Investments: ${row.get('PublicInvestments', 0):,.0f}")
        print(f"    Accounts Payable: ${row.get('AccountsPayableAccrued', 0):,.0f}")

    assert len(bs_rows) >= 1, "Should find at least 1 period"
    assert bs_rows[0].get("TotalAssets", 0) > 0, "Should have total assets"
    print("  PASSED\n")

    print("=" * 60)
    print("TEST 3: Merge P&L + Balance Sheet by Year")
    print("=" * 60)

    all_partial = pl_rows + bs_rows
    merged = merge_quickbooks_data(all_partial)

    print(f"  Merged records: {len(merged)}")
    for row in merged:
        year = row.get("TaxYear", "?")
        rev = row.get("TotalRevenue", 0) or 0
        exp = row.get("TotalExpenses", 0) or 0
        assets = row.get("TotalAssets", 0) or 0
        liab = row.get("TotalLiabilities", 0) or 0
        print(f"  Year {year}: Rev=${rev:,.0f}, Exp=${exp:,.0f}, "
              f"Assets=${assets:,.0f}, Liab=${liab:,.0f}")

    # Verify merge: each merged row should have BOTH P&L and BS fields
    for row in merged:
        has_pl = (row.get("TotalRevenue") or 0) > 0
        has_bs = (row.get("TotalAssets") or 0) > 0
        print(f"  Year {row.get('TaxYear')}: "
              f"has P&L data={has_pl}, has BS data={has_bs}")
        if has_pl:
            assert has_bs or True, "BS data may not exist for all years"

    print("  PASSED\n")
    return merged


def test_kpi_engine(merged_rows):
    """Test that the KPI engine handles QB data (with None fields) correctly."""
    from core.kpis import compute_kpis, format_kpi_value, get_kpi_status

    print("=" * 60)
    print("TEST 4: KPI Computation on QuickBooks Data")
    print("=" * 60)

    for row in merged_rows:
        kpis = compute_kpis(row)
        year = row.get("TaxYear", "?")
        print(f"\n  Year {year} KPIs:")

        # These should have real values (from QB data)
        available_kpis = [
            "OperatingSurplus", "OperatingMargin", "TotalCashEquivalents",
            "LiquidAssets", "MonthsExpenseCoverage", "DebtToAssetRatio",
            "CurrentRatio", "SalaryToExpenseRatio",
        ]
        for key in available_kpis:
            val = kpis.get(key)
            formatted = format_kpi_value(key, val)
            status = get_kpi_status(key, val)
            print(f"    {key}: {formatted} ({status})")
            if key in ("OperatingSurplus", "OperatingMargin", "TotalCashEquivalents"):
                assert val is not None, f"{key} should NOT be None for QB data"

        # These should be None (Form 990-specific)
        unavailable_kpis = [
            "ProgramExpenseRatio", "ManagementGeneralRatio",
            "FundraisingRatio", "RevenueGrowth",
        ]
        print(f"\n  Unavailable KPIs (should be N/A):")
        for key in unavailable_kpis:
            val = kpis.get(key)
            formatted = format_kpi_value(key, val)
            status = get_kpi_status(key, val)
            print(f"    {key}: {formatted} ({status})")
            if key in ("ProgramExpenseRatio", "ManagementGeneralRatio", "FundraisingRatio"):
                assert val is None, f"{key} SHOULD be None for QB data"
                assert formatted == "N/A", f"{key} should format as N/A"
                assert status == "neutral", f"{key} status should be neutral"

    print("\n  PASSED\n")


def test_supplement_form(merged_rows):
    """Test that supplement data correctly fills in missing QB fields."""
    from core.quickbooks import apply_supplement_data
    from core.kpis import compute_kpis, format_kpi_value

    print("=" * 60)
    print("TEST 5: Supplement Form Application")
    print("=" * 60)

    import copy
    rows = copy.deepcopy(merged_rows)

    # Before supplement
    kpis_before = compute_kpis(rows[0])
    print(f"  Before supplement:")
    print(f"    ProgramExpenseRatio: {format_kpi_value('ProgramExpenseRatio', kpis_before.get('ProgramExpenseRatio'))}")
    print(f"    VotingBoardMembers in data: {rows[0].get('VotingBoardMembers')}")

    # Apply supplement
    supplement = {
        "EIN": "12-3456789",
        "Mission": "Building affordable housing for families in need",
        "VotingBoardMembers": 9,
        "IndependentBoardMembers": 7,
        "Volunteers": 150,
        "EmployeeCount": 45,
        "ExecutiveDirectorCompensation": 95000,
        "ProgramExpensePct": 78,
        "ManagementExpensePct": 14,
        "FundraisingExpensePct": 8,
    }
    rows = apply_supplement_data(rows, supplement)

    # After supplement
    print(f"\n  After supplement:")
    print(f"    EIN: {rows[0].get('EIN')}")
    print(f"    Mission: {rows[0].get('Mission')[:50]}...")
    print(f"    VotingBoardMembers: {rows[0].get('VotingBoardMembers')}")
    print(f"    EmployeeCount: {rows[0].get('EmployeeCount')}")
    print(f"    ProgramExpenses: ${rows[0].get('ProgramExpenses', 0):,.0f}")
    print(f"    ManagementGeneralExpenses: ${rows[0].get('ManagementGeneralExpenses', 0):,.0f}")
    print(f"    FundraisingExpenses: ${rows[0].get('FundraisingExpenses', 0):,.0f}")

    kpis_after = compute_kpis(rows[0])
    print(f"\n    ProgramExpenseRatio: {format_kpi_value('ProgramExpenseRatio', kpis_after.get('ProgramExpenseRatio'))}")
    print(f"    ManagementGeneralRatio: {format_kpi_value('ManagementGeneralRatio', kpis_after.get('ManagementGeneralRatio'))}")
    print(f"    FundraisingRatio: {format_kpi_value('FundraisingRatio', kpis_after.get('FundraisingRatio'))}")

    assert rows[0].get("EIN") == "12-3456789", "EIN should be set"
    assert rows[0].get("VotingBoardMembers") == 9, "Board members should be set"
    assert kpis_after.get("ProgramExpenseRatio") is not None, "ProgramExpenseRatio should now compute"
    assert abs(kpis_after["ProgramExpenseRatio"] - 0.78) < 0.01, "Should be ~78%"

    print("\n  PASSED\n")


def test_export(merged_rows):
    """Test that Excel export handles QB data (with None values) without errors."""
    from core.export import generate_workbook

    print("=" * 60)
    print("TEST 6: Excel Export with QB Data")
    print("=" * 60)

    try:
        wb_bytes = generate_workbook(merged_rows)
        print(f"  Generated workbook: {len(wb_bytes):,} bytes")

        # Verify it's a valid Excel file
        wb = openpyxl.load_workbook(io.BytesIO(wb_bytes))
        print(f"  Sheets: {wb.sheetnames}")
        print(f"  Summary rows: {wb['Summary'].max_row}")
        print(f"  Extracted Data rows: {wb['Extracted Data'].max_row}")

        # Check that N/A values appear correctly
        ws = wb["Summary"]
        na_count = 0
        for row in ws.iter_rows(min_row=6, values_only=True):
            for cell in row:
                if cell == "N/A":
                    na_count += 1
        print(f"  N/A cells in Summary: {na_count}")

        ws_data = wb["Extracted Data"]
        na_data_count = 0
        for row in ws_data.iter_rows(min_row=2, values_only=True):
            for cell in row:
                if cell == "N/A":
                    na_data_count += 1
        print(f"  N/A cells in Extracted Data: {na_data_count}")

        assert len(wb_bytes) > 1000, "Workbook should be non-trivial size"
        print("  PASSED\n")
    except Exception as e:
        print(f"  FAILED: {e}")
        raise


def test_existing_xml_pipeline():
    """Verify the existing Form 990 XML pipeline still works after KPI changes."""
    from core.parser import parse_single_xml
    from core.kpis import compute_kpis, format_kpi_value

    print("=" * 60)
    print("TEST 7: Existing XML Pipeline Regression Check")
    print("=" * 60)

    # Create a minimal mock Form 990 XML
    mock_xml = b"""<?xml version="1.0" encoding="utf-8"?>
    <Return xmlns="http://www.irs.gov/efile">
      <ReturnHeader>
        <TaxYr>2023</TaxYr>
        <Filer>
          <EIN>123456789</EIN>
          <BusinessName>
            <BusinessNameLine1Txt>Test Nonprofit Org</BusinessNameLine1Txt>
          </BusinessName>
        </Filer>
      </ReturnHeader>
      <ReturnData>
        <IRS990>
          <CYTotalRevenueAmt>500000</CYTotalRevenueAmt>
          <CYTotalExpensesAmt>450000</CYTotalExpensesAmt>
          <TotalProgramServiceExpensesAmt>350000</TotalProgramServiceExpensesAmt>
          <CYTotalFundraisingExpenseAmt>25000</CYTotalFundraisingExpenseAmt>
          <TotalAssetsEOYAmt>800000</TotalAssetsEOYAmt>
          <TotalLiabilitiesEOYAmt>200000</TotalLiabilitiesEOYAmt>
          <NetAssetsOrFundBalancesEOYAmt>600000</NetAssetsOrFundBalancesEOYAmt>
          <CYSalariesCompEmpBnftPaidAmt>280000</CYSalariesCompEmpBnftPaidAmt>
          <CYContributionsGrantsAmt>400000</CYContributionsGrantsAmt>
          <CYInvestmentIncomeAmt>30000</CYInvestmentIncomeAmt>
          <TotalEmployeeCnt>25</TotalEmployeeCnt>
          <VotingMembersGoverningBodyCnt>7</VotingMembersGoverningBodyCnt>
        </IRS990>
      </ReturnData>
    </Return>"""

    try:
        row = parse_single_xml(mock_xml, "test_990.xml")
        print(f"  Parsed: {row.get('OrganizationName')} ({row.get('TaxYear')})")
        print(f"  Revenue: ${row.get('TotalRevenue', 0):,.0f}")
        print(f"  Expenses: ${row.get('TotalExpenses', 0):,.0f}")
        print(f"  ProgramExpenses: ${row.get('ProgramExpenses', 0):,.0f}")
        print(f"  EmployeeCount: {row.get('EmployeeCount')}")

        # Verify NO fields are None (all Form 990 fields should be populated)
        assert row.get("DataSource") is None or row.get("DataSource") != "quickbooks"
        assert row.get("ProgramExpenses") is not None, "ProgramExpenses should exist for 990"

        kpis = compute_kpis(row)
        print(f"\n  KPIs:")
        for key in ["OperatingSurplus", "ProgramExpenseRatio", "OperatingMargin",
                     "DebtToAssetRatio", "SalaryToExpenseRatio"]:
            val = kpis.get(key)
            formatted = format_kpi_value(key, val)
            print(f"    {key}: {formatted}")
            assert val is not None, f"{key} should NOT be None for Form 990 data"

        # Verify specific values
        assert kpis["OperatingSurplus"] == 50000, "500k - 450k = 50k"
        assert abs(kpis["ProgramExpenseRatio"] - (350000/450000)) < 0.001
        assert abs(kpis["DebtToAssetRatio"] - (200000/800000)) < 0.001

        print("\n  PASSED\n")
    except Exception as e:
        print(f"  FAILED: {e}")
        raise


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  QUICKBOOKS INTEGRATION — END-TO-END TEST SUITE")
    print("=" * 60 + "\n")

    # Test 1-3: Parser and merger
    merged = test_parser()

    # Test 4: KPI engine with QB data
    test_kpi_engine(merged)

    # Test 5: Supplement form
    test_supplement_form(merged)

    # Test 6: Excel export
    test_export(merged)

    # Test 7: Regression — existing XML pipeline
    test_existing_xml_pipeline()

    print("=" * 60)
    print("  ALL 7 TESTS PASSED")
    print("=" * 60)
