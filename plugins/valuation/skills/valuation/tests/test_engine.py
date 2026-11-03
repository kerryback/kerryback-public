"""Terminal value, the surviving NOL shield, the bridge, and the warnings."""

import pytest

from dcf_engine import _nol_shield_pv, run_model
from test_schedule import bundle, const


def test_a_company_already_in_steady_state_matches_closed_form_gordon():
    # The fixture starts at steady state, so every forecast year grows at g and
    # the whole valuation must equal FCF(1) / (r - g) -- computed here without
    # touching the engine's terminal-value code.
    r = run_model(bundle())
    expected = r["schedule"][0]["fcf"] / (0.10 - 0.05)
    assert r["ev_ops"] == pytest.approx(expected, rel=1e-9)


def test_free_cash_flow_grows_at_g_once_in_steady_state():
    rows = run_model(bundle())["schedule"]
    for a, b in zip(rows, rows[1:]):
        assert b["fcf"] == pytest.approx(a["fcf"] * 1.05, rel=1e-9)


def test_year_six_absorbs_the_transition_and_year_seven_is_clean():
    b = bundle()
    b["assumptions"]["sales_to_net_ppe"]["explicit"] = [3.0, 2.8, 2.6, 2.4, 2.2]
    rows = run_model(b)["schedule"]
    # Year 6 and 7 both sit on the terminal turnover, so net PP&E grows at g.
    assert rows[6]["net_ppe"] == pytest.approx(rows[5]["net_ppe"] * 1.05, rel=1e-9)
    # ... which is what makes year 7's capex the steady-state (g + d) figure.
    assert rows[6]["capex"] == pytest.approx((0.05 + 0.10) * rows[5]["net_ppe"])


def test_terminal_value_is_discounted_six_years_not_seven():
    r = run_model(bundle())
    assert r["pv_terminal"] == pytest.approx(
        r["terminal_value"] / 1.10 ** 6, rel=1e-12)


def test_wacc_below_terminal_growth_raises():
    b = bundle()
    b["rates"]["wacc"] = 0.04
    with pytest.raises(ValueError, match="perpetuity does not exist"):
        run_model(b)


def test_no_carryforward_gives_zero_shield_and_no_warning():
    r = run_model(bundle())
    assert r["pv_nol"] == 0.0
    assert not any("carryforward" in w for w in r["warnings"])


def test_a_surviving_carryforward_is_valued_and_flagged():
    b = bundle()
    b["base"]["nol"] = 1_000_000.0
    r = run_model(b)
    assert r["pv_nol"] > 0.0
    assert any("carryforward" in w for w in r["warnings"])


def test_shield_is_tau_times_nol_discounted_when_it_clears_in_one_year():
    # A balance small enough that the 80 percent limitation never binds clears
    # in year 7 alone, so the shield is just tau x NOL discounted seven years.
    pv, unexhausted = _nol_shield_pv(
        nol=100.0, ebit7=1000.0, growth=0.03, rate=0.25, wacc=0.10,
        limitation=0.80)
    assert pv == pytest.approx(0.25 * 100.0 / 1.10 ** 7, rel=1e-12)
    assert not unexhausted


def test_a_binding_limitation_stretches_the_shield_but_spends_all_of_it():
    # EBIT of 100 with an 80 percent limitation shelters at most 80 a year, so
    # a balance of 1000 takes years. Every dollar is used eventually, so the
    # undiscounted shield is exactly tau x NOL, and the PV is strictly less.
    pv, unexhausted = _nol_shield_pv(
        nol=1000.0, ebit7=100.0, growth=0.0, rate=0.25, wacc=0.10,
        limitation=0.80)
    assert not unexhausted
    assert 0.0 < pv < 0.25 * 1000.0
    # Thirteen years of usage, the last one partial: 12 x 80 + 40.
    undiscounted = sum(
        0.25 * used / 1.10 ** s
        for s, used in zip(range(7, 20), [80.0] * 12 + [40.0]))
    assert pv == pytest.approx(undiscounted, rel=1e-12)


def test_a_carryforward_with_negative_terminal_ebit_is_worthless():
    b = bundle()
    b["base"]["nol"] = 500.0
    b["assumptions"]["ebitda_margin"] = {"explicit": [0.01] * 5, "terminal": 0.01}
    r = run_model(b)
    assert r["pv_nol"] == 0.0
    assert any("Terminal EBIT is not positive" in w for w in r["warnings"])


def test_bridge_nets_claims_against_enterprise_value():
    b = bundle()
    b["base"]["nonoperating_assets"] = {"cash": 50.0}
    b["base"]["debt_claims"] = {"long_term_debt": 400.0}
    b["base"]["equity_claims"] = {"noncontrolling_interests": 30.0}
    r = run_model(b)
    assert r["equity_value"] == pytest.approx(
        r["ev_ops"] + r["pv_nol"] + 50.0 - 400.0 - 30.0)
    assert r["value_per_share"] == pytest.approx(r["equity_value"] / 100.0)


def test_negative_implied_capex_warns():
    b = bundle()
    b["assumptions"]["sales_to_net_ppe"] = const(20.0)
    assert any("capex is negative" in w for w in run_model(b)["warnings"])


def test_a_large_year_five_to_terminal_gap_warns():
    b = bundle()
    b["assumptions"]["sales_to_net_ppe"]["explicit"] = [2.0, 2.0, 2.0, 2.0, 4.0]
    assert any("absorbs the whole adjustment" in w for w in run_model(b)["warnings"])


def test_unit_mismatch_warns():
    b = bundle()
    b["base"]["sales"] = 1_941_800_000.0
    assert any("units" in w.lower() for w in run_model(b)["warnings"])
