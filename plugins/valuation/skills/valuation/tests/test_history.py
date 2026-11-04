"""Historical driver ratios, and the footing check that guards the classification."""

import pytest

from dcf_history import check_footing, historical_ratios

FIN = {
    "years": [2023, 2024, 2025],
    "lines": {
        "Revenues": {2023: 1000.0, 2024: 1200.0, 2025: 1500.0},
        "EBITDA": {2023: 200.0, 2024: 240.0, 2025: 300.0},
        "Depreciation": {2023: 50.0, 2024: 55.0, 2025: 60.0},
        "Receivables": {2023: 200.0, 2024: 240.0, 2025: 300.0},
        "Payables": {2023: 100.0, 2024: 120.0, 2025: 150.0},
        "Property, plant and equipment, net": {2023: 500.0, 2024: 550.0, 2025: 600.0},
    },
}

CLASSIFICATION = [
    {"line": "Receivables", "bucket": "operating_asset", "key": "receivables"},
    {"line": "Payables", "bucket": "operating_liability", "key": "payables"},
    {"line": "Property, plant and equipment, net", "bucket": "net_ppe"},
]


def test_unfooted_classification_names_the_difference():
    classification = [{"line": "Cash", "bucket": "nonoperating_asset"}]
    with pytest.raises(ValueError, match="150"):
        check_footing(classification,
                      {"Cash": 100.0, "Inventories": 150.0},
                      reported_total=250.0)


def test_unfooted_classification_names_the_missing_line():
    classification = [{"line": "Cash", "bucket": "nonoperating_asset"}]
    with pytest.raises(ValueError, match="Inventories"):
        check_footing(classification,
                      {"Cash": 100.0, "Inventories": 150.0},
                      reported_total=250.0)


def test_footed_classification_passes():
    classification = [{"line": "Cash", "bucket": "nonoperating_asset"},
                      {"line": "Inventories", "bucket": "operating_asset"}]
    check_footing(classification,
                  {"Cash": 100.0, "Inventories": 150.0},
                  reported_total=250.0)


def test_a_classified_line_absent_from_the_statement_raises():
    classification = [{"line": "Goodwill", "bucket": "excluded"}]
    with pytest.raises(ValueError, match="Goodwill"):
        check_footing(classification, {"Cash": 100.0}, reported_total=100.0)


def test_working_capital_ratios_use_their_own_year_s_sales():
    out = historical_ratios(FIN, CLASSIFICATION, sales_line="Revenues",
                            ebitda_line="EBITDA", depreciation_line="Depreciation")
    receivables = out["ratios"]["operating_assets"]["receivables"]
    assert receivables[2023] == pytest.approx(200.0 / 1000.0)
    # Needing no next year, the final year carries a ratio too.
    assert receivables[2025] == pytest.approx(300.0 / 1500.0)


def test_net_ppe_is_the_exception_and_uses_next_year_sales():
    """Capacity is built ahead of the sales it supports, so PP&E leads by a year."""
    out = historical_ratios(FIN, CLASSIFICATION, sales_line="Revenues",
                            ebitda_line="EBITDA", depreciation_line="Depreciation")
    turnover = out["ratios"]["sales_to_net_ppe"]
    assert turnover[2023] == pytest.approx(1200.0 / 500.0)
    # ... and the final year has no next year, so it carries no turnover.
    assert 2025 not in turnover


def test_income_ratios_use_their_own_year():
    out = historical_ratios(FIN, CLASSIFICATION, sales_line="Revenues",
                            ebitda_line="EBITDA", depreciation_line="Depreciation")
    assert out["ratios"]["ebitda_margin"][2025] == pytest.approx(300.0 / 1500.0)
    assert out["ratios"]["sales_growth"][2025] == pytest.approx(1500.0 / 1200.0 - 1)
    assert 2023 not in out["ratios"]["sales_growth"]


def test_depreciation_rate_is_on_prior_year_net_ppe():
    out = historical_ratios(FIN, CLASSIFICATION, sales_line="Revenues",
                            ebitda_line="EBITDA", depreciation_line="Depreciation")
    assert out["ratios"]["depreciation_rate"][2024] == pytest.approx(55.0 / 500.0)


def test_realized_capex_comes_out_of_the_roll_forward():
    out = historical_ratios(FIN, CLASSIFICATION, sales_line="Revenues",
                            ebitda_line="EBITDA", depreciation_line="Depreciation")
    # 550 = 500 + capex - 55
    assert out["ratios"]["realized_capex"][2024] == pytest.approx(105.0)


def test_a_loss_year_margin_is_flagged_as_unusable():
    fin = dict(FIN, lines=dict(FIN["lines"], EBITDA={2023: -50.0, 2024: 240.0,
                                                    2025: 300.0}))
    out = historical_ratios(fin, CLASSIFICATION, sales_line="Revenues",
                            ebitda_line="EBITDA", depreciation_line="Depreciation")
    assert any("2023" in note and "margin" in note.lower() for note in out["notes"])
