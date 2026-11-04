"""Fetching: the fiscal calendar, picking statements, and building the workbook.

All offline. One live test fetches JBSS from EDGAR and the Motley Fool; it runs
only with DCF_NETWORK_TESTS=1 and SEC_USER_AGENT set.
"""

import os

import pytest

from dcf_fetch import _statement_reports, fiscal_quarter
from dcf_statements import build_workbook, clean, merge, parse_report


# --------------------------------------------------------------------------
# fiscal calendar
# --------------------------------------------------------------------------

@pytest.mark.parametrize("when, fye, want", [
    ("2026-08-20", 6, (2026, 4)),     # JBSS: June year end, Q4 call in August
    ("2025-10-29", 6, (2026, 1)),     # September quarter opens the next fiscal year
    ("2026-01-29", 6, (2026, 2)),
    ("2024-05-01", 6, (2024, 3)),
    ("2023-03-15", 12, (2022, 4)),    # calendar year: Q4 reported in March
    ("2023-05-10", 12, (2023, 1)),
    ("2024-02-03", 1, (2024, 3)),     # January year end closed three days ago: not yet reportable
    ("2024-03-20", 1, (2024, 4)),     # ... reported six weeks later, as FY2024
    ("2023-12-05", 9, (2023, 4)),     # September year end, reported in December
])
def test_fiscal_quarter(when, fye, want):
    assert fiscal_quarter(when, fye) == want


def test_a_quarter_is_not_over_the_day_it_closes():
    # Filed on July 2 for a June year end: June has not been reported yet.
    assert fiscal_quarter("2026-07-02", 6) == (2026, 3)


# --------------------------------------------------------------------------
# choosing statements from FilingSummary.xml
# --------------------------------------------------------------------------

def summary(*reports):
    rows = "".join(
        f"<Report><MenuCategory>{cat}</MenuCategory><ShortName>{name}</ShortName>"
        f"<HtmlFileName>{html}</HtmlFileName></Report>" for cat, name, html in reports)
    return f"<FilingSummary><MyReports>{rows}</MyReports></FilingSummary>".encode()


def test_statements_are_picked_by_name():
    got = _statement_reports(summary(
        ("Cover", "Cover Page", "R1.htm"),
        ("Statements", "Consolidated Balance Sheets", "R2.htm"),
        ("Statements", "Consolidated Balance Sheets (Parenthetical)", "R3.htm"),
        ("Statements", "Consolidated Statements of Operations", "R4.htm"),
        ("Statements", "Consolidated Statements of Comprehensive Income", "R5.htm"),
        ("Statements", "Consolidated Statements of Stockholders' Equity", "R6.htm"),
        ("Statements", "Consolidated Statements of Cash Flows", "R7.htm"),
    ))
    assert {k: v[0] for k, v in got.items()} == {"BS": "R2.htm", "IS": "R4.htm", "CF": "R7.htm"}


def test_a_combined_comprehensive_income_statement_is_the_fallback():
    """JBSS files only a statement of comprehensive income."""
    got = _statement_reports(summary(
        ("Statements", "Consolidated Statements of Comprehensive Income", "R4.htm"),
        ("Statements", "Consolidated Balance Sheets", "R2.htm"),
        ("Statements", "Consolidated Statements of Cash Flows", "R7.htm"),
    ))
    assert got["IS"][0] == "R4.htm"


# --------------------------------------------------------------------------
# statement pages
# --------------------------------------------------------------------------

def report(unit, years, rows):
    """A minimal rendered XBRL statement page, in EDGAR's markup."""
    heads = "".join(f"<th class='th'>Jun. 28, {y}</th>" for y in years)
    body = []
    for concept, label, vals, total in rows:
        cls = " class='reu'" if total else ""
        cells = "".join(f"<td class='nump'>{v}</td>" for v in vals)
        body.append(
            f"<tr{cls}><td class='pl'><a onclick=\"top.Show.showAR( this, 'defref_us-gaap_{concept}', window );\">"
            f"{label}</a></td>{cells}</tr>")
    return (f"<table class='report'><tr><th>Consolidated Balance Sheets - USD ($) {unit}</th></tr>"
            f"<tr>{heads}</tr>{''.join(body)}</table>")


def test_a_page_parses_into_millions_with_concepts():
    title, years, rows = parse_report(report("$ in Thousands", [2026, 2025], [
        ("AssetsCurrentAbstract", "Current assets:", [], False),
        ("Cash", "Cash", ["$ 1,147", "$ 1,580"], False),
        ("InventoryNet", "Inventories", ["245,826", "(10)"], False),
        ("Assets", "TOTAL ASSETS", ["$ 600,000", "$ 590,000"], True),
    ]))
    assert years == [2026, 2025]
    cash = next(r for r in rows if r["concept"] == "us-gaap:Cash")
    assert cash["vals"] == {2026: pytest.approx(1.147), 2025: pytest.approx(1.580)}
    inv = next(r for r in rows if r["concept"] == "us-gaap:InventoryNet")
    assert inv["vals"][2025] == pytest.approx(-0.010)          # parentheses are negative
    assert next(r for r in rows if r["concept"] == "us-gaap:Assets")["total"]
    assert rows[0]["abstract"]


def test_each_year_comes_from_the_newest_filing_that_reports_it():
    newer = report("$ in Thousands", [2026, 2025], [("Cash", "Cash", ["100", "90"], False)])
    older = report("$ in Thousands", [2025, 2024], [("Cash", "Cash", ["80", "70"], False)])
    years, src, rows = merge([("2026_10-K", newer), ("2025_10-K", older)])
    assert years == [2024, 2025, 2026]
    assert src == {2026: "2026_10-K", 2025: "2026_10-K", 2024: "2025_10-K"}
    cash = dict(rows)[("us-gaap:Cash", 1)]
    assert cash["vals"][2025] == pytest.approx(0.090)          # restated, not the original 80


def test_labels_lose_dollar_amounts_and_share_counts():
    assert clean("Accounts receivable, less allowances of $1,234") == "Accounts receivable"
    assert clean("Treasury stock; 117,900 shares") == "Treasury stock"
    assert clean("Segments [Member]") == "Segments"


def test_the_workbook_has_three_statements_and_footing_checks(tmp_path):
    bs = report("$ in Thousands", [2026, 2025], [
        ("Cash", "Cash", ["100", "90"], False),
        ("Assets", "Total assets", ["100", "90"], True),
        ("LiabilitiesAndStockholdersEquity", "Total liabilities and equity", ["100", "95"], True),
    ])
    filings = [dict(key="k1", form="10-K", fy="2026", filed="2026-08-19",
                    url="https://www.sec.gov/x", stmts={"BS": "Balance Sheets"})]
    co = {"ticker": "TEST", "name": "Test Co", "fiscal_year_end": "0628"}
    path, problems = build_workbook(co, filings, {"BS": [("k1", bs)]}, str(tmp_path / "t.xlsx"))

    from dcf_load import load_statements
    balance = load_statements(path, sheet="Balance Sheet")
    assert balance is not None
    # The 2025 balance sheet does not foot, and the build says so.
    assert any("FY2025" in p and "Total assets" in p for p in problems)
    assert not any("FY2026" in p for p in problems)


# --------------------------------------------------------------------------
# live
# --------------------------------------------------------------------------

@pytest.mark.skipif(not (os.environ.get("DCF_NETWORK_TESTS") and os.environ.get("SEC_USER_AGENT")),
                    reason="network test: set DCF_NETWORK_TESTS=1 and SEC_USER_AGENT")
def test_jbss_end_to_end(tmp_path):
    from dcf_fetch import fetch
    from dcf_inputs import inventory

    result = fetch("JBSS", str(tmp_path), years=5, log=lambda *_: None)
    assert result["problems"] == []
    found = inventory(str(tmp_path))
    assert found["sufficient"]
    assert len(found["filings"]) >= 5
    assert len(found["press_releases"]) >= 20
    assert any("FY2026Q4" in p for p in found["transcripts"])
