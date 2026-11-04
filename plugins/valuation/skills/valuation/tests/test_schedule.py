"""The forecast schedule: sales through EBIT, before taxes."""

import pytest

from dcf_engine import N_EXPLICIT, build_schedule, driver, sales_path, validate_bundle


def const(v):
    return {"explicit": [v] * N_EXPLICIT, "terminal": v}


def bundle(**over):
    """A company that is already in steady state at year 0.

    Sales 1000, growth 5 percent, so year-1 sales are 1050. Net PP&E is a
    turnover on next year's sales, so steady state needs 1050/2 = 525 at year 0.
    Working capital is stated against the same year's sales, so it needs 10
    percent of 1000 at year 0. Starting there makes year 1 itself steady state,
    which is what the closed-form Gordon test relies on.
    """
    b = {
        "meta": {"company": "Test", "fiscal_year_0": 2025,
                 "units": "USD millions", "diluted_shares": 100.0},
        "base": {"sales": 1000.0, "net_ppe": 525.0,
                 "operating_assets": {"receivables": 200.0},
                 "operating_liabilities": {"payables": 100.0},
                 "nonoperating_assets": {}, "debt_claims": {}, "equity_claims": {},
                 "nol": 0.0},
        "assumptions": {
            "sales_growth": const(0.05), "ebitda_margin": const(0.20),
            "sales_to_net_ppe": const(2.0), "depreciation_rate": const(0.10),
            "cash_tax_rate": const(0.25),
            "operating_assets": {"receivables": const(0.20)},
            "operating_liabilities": {"payables": const(0.10)},
        },
        "rates": {"wacc": 0.10, "nol_limitation": 0.80},
    }
    for k, v in over.items():
        b[k] = v
    return b


def test_driver_uses_explicit_then_terminal():
    spec = {"explicit": [1, 2, 3, 4, 5], "terminal": 9}
    assert [driver(spec, t) for t in range(1, 9)] == [1, 2, 3, 4, 5, 9, 9, 9]


def test_sales_compound_from_year_zero():
    s = sales_path(1000.0, const(0.10), through=3)
    assert s[0] == pytest.approx(1000.0)
    assert s[3] == pytest.approx(1331.0)


def test_net_ppe_is_next_year_sales_over_turnover():
    r1 = build_schedule(bundle())[0]
    assert r1["net_ppe"] == pytest.approx(r1["next_sales"] / 2.0)


def test_depreciation_is_rate_times_prior_net_ppe():
    rows = build_schedule(bundle())
    assert rows[0]["depreciation"] == pytest.approx(0.10 * 525.0)
    assert rows[1]["depreciation"] == pytest.approx(0.10 * rows[0]["net_ppe"])


def test_capex_is_the_plug():
    rows = build_schedule(bundle())
    assert rows[0]["capex"] == pytest.approx(
        rows[0]["net_ppe"] - 525.0 + rows[0]["depreciation"])


def test_steady_state_capex_is_growth_plus_depreciation_rate():
    rows = build_schedule(bundle())
    assert rows[6]["capex"] == pytest.approx((0.05 + 0.10) * rows[5]["net_ppe"])


def test_schedule_runs_to_year_seven():
    assert [r["year"] for r in build_schedule(bundle())] == [1, 2, 3, 4, 5, 6, 7]


def test_working_capital_is_stated_against_the_same_year_s_sales():
    rows = build_schedule(bundle())
    r1 = rows[0]
    assert r1["nwc"] == pytest.approx((0.20 - 0.10) * r1["sales"])
    assert r1["nwc"] != pytest.approx((0.20 - 0.10) * r1["next_sales"])


def test_net_ppe_is_the_exception_and_leads_sales_by_a_year():
    r1 = build_schedule(bundle())[0]
    assert r1["net_ppe"] == pytest.approx(r1["next_sales"] / 2.0)


def test_empty_operating_liabilities_is_fine():
    b = bundle()
    b["base"]["operating_liabilities"] = {}
    b["assumptions"]["operating_liabilities"] = {}
    rows = build_schedule(b)
    assert rows[0]["nwc"] == pytest.approx(0.20 * rows[0]["sales"])


def test_wrong_length_explicit_array_raises_with_driver_name():
    b = bundle()
    b["assumptions"]["ebitda_margin"]["explicit"] = [0.2, 0.2]
    with pytest.raises(ValueError, match="ebitda_margin"):
        validate_bundle(b)


def test_base_and_assumption_keys_must_agree():
    b = bundle()
    b["assumptions"]["operating_assets"]["inventories"] = const(0.05)
    with pytest.raises(ValueError, match="operating_assets"):
        validate_bundle(b)


def test_a_key_on_both_sides_of_nwc_raises():
    b = bundle()
    b["base"]["operating_liabilities"]["receivables"] = 10.0
    b["assumptions"]["operating_liabilities"]["receivables"] = const(0.01)
    with pytest.raises(ValueError, match="both sides"):
        validate_bundle(b)
