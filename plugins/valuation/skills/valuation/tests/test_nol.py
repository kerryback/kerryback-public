"""Taxes on EBIT, and the running NOL carryforward."""

import pytest

from dcf_engine import apply_taxes, build_schedule
from test_schedule import bundle


def taxed(b):
    return apply_taxes(build_schedule(b), b)


def flat(values, terminal):
    return {"explicit": list(values), "terminal": terminal}


def no_growth_no_depreciation(b):
    """Strip growth and depreciation so EBIT equals EBITDA equals margin x 1000."""
    b["assumptions"]["sales_growth"] = flat([0.0] * 5, 0.0)
    b["assumptions"]["depreciation_rate"] = flat([0.0] * 5, 0.0)
    return b


def test_no_tax_in_a_loss_year_and_the_loss_is_banked():
    b = bundle()
    b["assumptions"]["ebitda_margin"] = flat([0.01] * 5, 0.01)
    rows = taxed(b)
    assert rows[0]["ebit"] < 0
    assert rows[0]["tax"] == 0.0
    assert rows[0]["nol_close"] == pytest.approx(-rows[0]["ebit"])


def test_carryforward_shelters_eighty_percent_of_later_income():
    b = bundle()
    b["base"]["nol"] = 1_000_000.0
    r = taxed(b)[0]
    assert r["nol_used"] == pytest.approx(0.80 * r["ebit"])
    assert r["tax"] == pytest.approx(0.25 * 0.20 * r["ebit"])


def test_carryforward_is_exhausted_not_overdrawn():
    b = bundle()
    b["base"]["nol"] = 1.0
    rows = taxed(b)
    assert rows[0]["nol_used"] == pytest.approx(1.0)
    assert rows[0]["nol_close"] == pytest.approx(0.0)


def test_hand_worked_two_loss_years_then_profit():
    # EBIT of -100, -50, +500 with an 80 percent limitation and tau of 0.25.
    # Entering year 3 the carryforward is 150. Usable is min(0.8 x 500, 150) =
    # 150, so taxable income is 350 and tax is 87.5, clearing the balance.
    b = no_growth_no_depreciation(bundle())
    b["assumptions"]["ebitda_margin"] = flat([-0.10, -0.05, 0.50, 0.50, 0.50], 0.50)
    rows = taxed(b)
    assert [round(r["ebit"], 6) for r in rows[:3]] == [-100.0, -50.0, 500.0]
    assert rows[1]["nol_close"] == pytest.approx(150.0)
    assert rows[2]["nol_used"] == pytest.approx(150.0)
    assert rows[2]["taxable_income"] == pytest.approx(350.0)
    assert rows[2]["tax"] == pytest.approx(87.5)
    assert rows[2]["nol_close"] == pytest.approx(0.0)


def test_year_seven_ignores_the_carryforward():
    b = bundle()
    b["base"]["nol"] = 1_000_000.0
    r7 = taxed(b)[6]
    assert r7["nol_used"] == 0.0
    assert r7["tax"] == pytest.approx(0.25 * r7["ebit"])


def test_free_cash_flow_identity():
    for r in taxed(bundle()):
        assert r["fcf"] == pytest.approx(
            r["ebitda"] - r["tax"] - r["capex"] - r["delta_nwc"])


def test_no_depreciation_no_growth_gives_ebitda_after_tax():
    r = taxed(no_growth_no_depreciation(bundle()))[3]
    assert r["capex"] == pytest.approx(0.0)
    assert r["delta_nwc"] == pytest.approx(0.0)
    assert r["fcf"] == pytest.approx(r["ebitda"] * (1 - 0.25))


def test_effective_rate_is_below_the_marginal_rate_while_sheltered():
    b = bundle()
    b["base"]["nol"] = 1_000_000.0
    r = taxed(b)[0]
    assert r["effective_tax_rate"] == pytest.approx(0.25 * 0.20)
