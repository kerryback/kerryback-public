"""The whole pipeline on a real company, from the staged workbook out.

ProFrac Holding (ACDC) is the right case to pin: it lost money in four of its
last five years, carries a tax receivable agreement, operating leases, goodwill,
a mezzanine preferred and a noncontrolling interest, and has two classes of
common. Every awkward branch in the model gets used.

The assumptions here are illustrative, not a view on the company. What is under
test is that real statements flow through classification, footing, history and
the engine into both artifacts, and that the warnings say what this company's
history implies.
"""

import os

import pytest

from build_pages import build_pages
from dcf_engine import run_model
from dcf_history import check_footing, historical_ratios
from dcf_load import load_statements

# The ProFrac (ACDC) statements workbook, as dcf_fetch.py writes it. Not
# shipped with the skill; point DCF_ACDC_WORKBOOK at a copy to run these.
WORKBOOK = os.path.expanduser(os.environ.get("DCF_ACDC_WORKBOOK", ""))

pytestmark = pytest.mark.skipif(
    not WORKBOOK or not os.path.exists(WORKBOOK),
    reason="set DCF_ACDC_WORKBOOK to an ACDC statements workbook to run these")

FY = 2025

# Every reported balance-sheet line, with the call and the reason. The defaults
# in reference/classification.md, applied to this company.
CLASSIFICATION = [
    ("Cash and cash equivalents", "nonoperating_asset", None,
     "Added at book in the bridge."),
    ("Accounts receivable, net", "operating_asset", "receivables",
     "Trade receivables; scale with revenue."),
    ("Accounts receivable - related party, net", "operating_asset", "receivables_rp",
     "Trade balances with affiliates of the sponsor, not financing."),
    ("Inventories", "operating_asset", "inventories",
     "Sand, chemicals and spare parts."),
    ("Prepaid expenses and other current assets", "operating_asset", "prepaid",
     "Scale roughly with activity."),
    ("Total current assets", "excluded", None, "A subtotal, not a line."),
    ("Property, plant, and equipment", "net_ppe", None,
     "The fleet. Driven by the sales-to-PP&E turnover."),
    ("Operating lease right-of-use assets, net", "excluded", None,
     "Its growth tracks the lease liability, not sales."),
    ("Goodwill", "excluded", None,
     "The cash flows of the acquisitions are already in revenue and EBITDA."),
    ("Intangible assets, net", "excluded", None, "As goodwill."),
    ("Deferred tax assets", "excluded", None,
     "The model computes cash taxes from EBIT and the carryforward directly."),
    ("Investments", "nonoperating_asset", None,
     "Equity-method holdings; their income is not in EBITDA, so they enter "
     "through the bridge. Nil at FY2025."),
    ("Other assets", "excluded", None, "Immaterial and not sales-driven."),
    ("Total assets", "excluded", None, "A subtotal, not a line."),
    ("Accounts payable", "operating_liability", "payables", "Trade payables."),
    ("Accounts payable - related party", "operating_liability", "payables_rp",
     "Trade balances with affiliates."),
    ("Accrued expenses", "operating_liability", "accrued", "Scale with activity."),
    ("Current portion of long-term debt", "debt_claim", None, "Debt is debt."),
    ("Current portion of long-term debt- related party", "debt_claim", None,
     "Sponsor debt ranks ahead of common."),
    ("Current portion of operating lease liabilities", "debt_claim", None,
     "EBITDA here is struck before rent, so the obligation belongs in the bridge."),
    ("Other current liabilities", "operating_liability", "other_current_liabs",
     "Accruals of operating costs."),
    ("Other current liabilities - related party", "operating_liability",
     "other_current_liabs_rp", "As above."),
    ("Total current liabilities", "excluded", None, "A subtotal, not a line."),
    ("Long-term debt", "debt_claim", None, "Debt is debt."),
    ("Long-term debt - related party", "debt_claim", None, "Sponsor debt."),
    ("Operating lease liabilities", "debt_claim", None,
     "See the current portion above."),
    ("Deferred tax liabilities", "excluded", None, "As the deferred tax asset."),
    ("Tax receivable agreement liability", "debt_claim", None,
     "An Up-C contractual obligation to pre-IPO holders; cash out before common."),
    ("Other liabilities", "excluded", None, "Not sales-driven."),
    ("Total liabilities", "excluded", None, "A subtotal, not a line."),
    ("Redeemable noncontrolling interest", "equity_claim", None,
     "Mezzanine; ranks ahead of common. Nil at FY2025."),
    ("Members' equity", "excluded", None,
     "Pre-reorganisation common equity; nil from FY2022."),
    ("Series A redeemable convertible preferred stock, $0.01 par value, 50 "
     "thousand shares authorized, issued and outstanding",
     "equity_claim", None, "Ranks ahead of common."),
    ("Class A common stock, $0.01 par value", "excluded", None, "Common equity."),
    ("Class B common stock, $0.01 par value", "excluded", None, "Common equity."),
    ("Additional paid-in capital", "excluded", None, "Common equity."),
    ("Accumulated deficit", "excluded", None, "Common equity."),
    ("Accumulated other comprehensive income", "excluded", None, "Common equity."),
    ("Total stockholders' equity attributable to ProFrac Holding Corp.",
     "excluded", None, "A subtotal, not a line."),
    ("Noncontrolling interests", "equity_claim", None,
     "Consolidated EBITDA includes the whole of the subsidiaries, so the slice "
     "someone else owns has to come out. Book value is a proxy."),
    ("Total stockholders' equity", "excluded", None, "A subtotal, not a line."),
    ("Total liabilities, mezzanine equity, and stockholders' equity",
     "excluded", None, "A subtotal, not a line."),
    ("Total assets \u2212 total liabilities, mezzanine equity, and "
     "stockholders' equity", "excluded", None,
     "The workbook's own footing check, not a reported line."),
]


def classification():
    out = []
    for line, bucket, key, note in CLASSIFICATION:
        entry = {"line": line, "bucket": bucket, "note": note}
        if key:
            entry["key"] = key
        out.append(entry)
    return out


@pytest.fixture(scope="module")
def statements():
    return {
        "balance": load_statements(WORKBOOK, sheet="Balance Sheet"),
        "income": load_statements(WORKBOOK, sheet="Income Statement"),
        "cashflow": load_statements(WORKBOOK, sheet="Cash Flow Statement"),
    }


def ebitda_series(income):
    """Revenue less cash operating costs. Impairments and acquisition costs are
    left out; they are not the run-rate cost of the business."""
    lines = income["lines"]
    out = {}
    for year in income["years"]:
        revenue = lines["Revenues"].get(year)
        cost = lines["Cost of revenues, exclusive of depreciation, depletion "
                     "and amortization"].get(year)
        sga = lines["Selling, general, and administrative"].get(year)
        if None not in (revenue, cost, sga):
            out[year] = revenue - cost - sga
    return out


# The lines that actually compose total assets. The rest of the balance sheet is
# subtotals, the liability and equity side, and the workbook's own check row.
ASSET_COMPONENTS = [
    "Cash and cash equivalents", "Accounts receivable, net",
    "Accounts receivable - related party, net", "Inventories",
    "Prepaid expenses and other current assets", "Property, plant, and equipment",
    "Operating lease right-of-use assets, net", "Goodwill", "Intangible assets, net",
    "Investments", "Deferred tax assets", "Other assets",
]


def test_every_reported_line_is_classified(statements):
    lines = statements["balance"]["lines"]
    named = {line for line, *_ in CLASSIFICATION}
    assert named == set(lines), \
        f"unclassified: {sorted(set(lines) - named)}; " \
        f"named but absent: {sorted(named - set(lines))}"


def test_the_asset_components_foot_to_reported_total_assets(statements):
    """A real footing, against ProFrac's own total rather than against itself."""
    lines = statements["balance"]["lines"]
    components = {line: lines[line].get(FY) or 0.0 for line in ASSET_COMPONENTS}
    check_footing([{"line": line, "bucket": "x"} for line in ASSET_COMPONENTS],
                  components,
                  reported_total=lines["Total assets"][FY])


def test_the_footing_check_catches_a_dropped_asset(statements):
    lines = statements["balance"]["lines"]
    components = {line: lines[line].get(FY) or 0.0 for line in ASSET_COMPONENTS}
    short = [{"line": line, "bucket": "x"} for line in ASSET_COMPONENTS
             if line != "Inventories"]
    with pytest.raises(ValueError, match="Inventories"):
        check_footing(short, components, reported_total=lines["Total assets"][FY])





def acdc_bundle(statements):
    balance, income, cashflow = (statements["balance"], statements["income"],
                                 statements["cashflow"])
    b, i = balance["lines"], income["lines"]

    def bal(line):
        return b[line].get(FY) or 0.0

    ebitda = ebitda_series(income)
    financials = {
        "years": balance["years"],
        "lines": dict(b, Revenues=i["Revenues"], EBITDA=ebitda,
                      Depreciation=cashflow["lines"][
                          "Depreciation, depletion and amortization"]),
    }
    history = historical_ratios(
        financials, classification(), sales_line="Revenues",
        ebitda_line="EBITDA", depreciation_line="Depreciation")

    def group(bucket):
        return [c for c in classification() if c["bucket"] == bucket]

    def spec(explicit, terminal, rationale=""):
        return {"explicit": list(explicit), "terminal": terminal,
                "rationale": rationale}

    operating_assets = {c["key"]: bal(c["line"]) for c in group("operating_asset")}
    operating_liabilities = {c["key"]: bal(c["line"])
                             for c in group("operating_liability")}
    sales0 = i["Revenues"][FY]

    return {
        "meta": {"company": "ProFrac Holding Corp.", "ticker": "ACDC",
                 "fiscal_year_0": FY, "fiscal_year_end": "2025-12-31",
                 "units": "USD millions", "diluted_shares": 168.3},
        "classification": classification(),
        "base": {
            "sales": sales0,
            "net_ppe": bal("Property, plant, and equipment"),
            "operating_assets": operating_assets,
            "operating_liabilities": operating_liabilities,
            "nonoperating_assets": {c["line"].split(",")[0].lower().replace(" ", "_"):
                                    bal(c["line"]) for c in group("nonoperating_asset")},
            "debt_claims": {"debt": sum(bal(c["line"]) for c in group("debt_claim"))},
            "equity_claims": {"preferred_and_noncontrolling":
                              sum(bal(c["line"]) for c in group("equity_claim"))},
            "nol": 500.0,
        },
        "assumptions": {
            "sales_growth": spec([-0.05, 0.04, 0.05, 0.04, 0.03], 0.025,
                                 "A further step down as pressure pumping "
                                 "absorbs the completions slowdown, then a "
                                 "recovery fading to nominal GDP."),
            "ebitda_margin": spec([0.13, 0.15, 0.17, 0.18, 0.18], 0.18,
                                  "FY2025 ran at 15.2 percent. The forecast "
                                  "holds below the FY2022 peak."),
            "sales_to_net_ppe": spec([1.35, 1.40, 1.45, 1.50, 1.50], 1.50,
                                     "FY2025 turnover is 1.33 on a fleet with "
                                     "spare capacity."),
            "depreciation_rate": spec([0.26, 0.25, 0.24, 0.23, 0.22], 0.22,
                                      "FY2025 depreciation is 26 percent of "
                                      "opening net PP&E, fading as the "
                                      "acquired intangibles run off."),
            "cash_tax_rate": spec([0.25] * 5, 0.25,
                                  "Federal plus a blended state rate."),
            "operating_assets": {k: spec([v / sales0] * 5, v / sales0)
                                 for k, v in operating_assets.items()},
            "operating_liabilities": {k: spec([v / sales0] * 5, v / sales0)
                                      for k, v in operating_liabilities.items()},
        },
        "rates": {"wacc": 0.12,
                  "wacc_derivation": "Illustrative. Not a view on the company.",
                  "nol_limitation": 0.80},
        "history": history,
    }


def test_the_pipeline_runs_on_real_statements(statements):
    result = run_model(acdc_bundle(statements))
    assert result["schedule"][0]["sales"] == pytest.approx(1941.8 * 0.95)
    assert result["value_per_share"] is not None
    # Year 1 EBIT is negative on these assumptions, so no tax is paid and the
    # carryforward grows -- which is the whole reason the NOL mechanism exists.
    assert result["schedule"][0]["ebit"] < 0
    assert result["schedule"][0]["tax"] == 0.0
    assert result["schedule"][0]["nol_close"] > result["schedule"][0]["nol_open"]


def test_the_history_names_the_years_depreciation_swallowed(statements):
    """ACDC's EBITDA is positive in all five years; its EBIT is not.

    Depreciation ran above twenty percent of revenue on a fleet built through
    acquisitions, so 2021 and 2025 show positive EBITDA and negative EBIT. That
    is precisely the case the carryforward exists for, and the history has to
    say so rather than leaving a forecaster to notice it.
    """
    history = acdc_bundle(statements)["history"]
    margins = history["ratios"]["ebitda_margin"]
    assert all(m > 0 for m in margins.values())
    assert any("did not cover depreciation" in n for n in history["notes"])


def test_the_bridge_carries_this_company_s_claims(statements):
    result = run_model(acdc_bundle(statements))
    labels = [item["label"] for item in result["bridge"]]
    assert "Less debt" in labels
    assert "Less preferred and noncontrolling" in labels
    assert "Plus cash and cash equivalents" in labels


def test_all_three_artifacts_build(statements, tmp_path):
    pytest.importorskip("openpyxl")
    from build_workbook import build_workbook
    from dcf_assumptions import apply_assumptions_csv, write_assumptions_csv

    bundle = acdc_bundle(statements)
    page = build_pages(bundle, str(tmp_path), slug="acdc")
    xlsx = tmp_path / "acdc-dcf.xlsx"
    build_workbook(bundle, str(xlsx))
    csv_path = write_assumptions_csv(bundle, tmp_path / "assumptions.csv")

    assert xlsx.exists()
    text = open(page, encoding="utf-8").read()
    assert "http://" not in text and "https://" not in text
    assert ".xlsx" not in text
    assert "ProFrac" in text
    assert "Tax receivable agreement liability" in text

    # The CSV is authoritative for the numbers once written, and stable: apply
    # it, write it again, and nothing moves.
    from dcf_engine import run_model
    once = apply_assumptions_csv(bundle, str(csv_path))
    again = write_assumptions_csv(once, tmp_path / "assumptions2.csv")
    twice = apply_assumptions_csv(once, str(again))
    assert run_model(twice)["ev_ops"] == pytest.approx(run_model(once)["ev_ops"])
    assert open(csv_path).read() == open(again).read()
