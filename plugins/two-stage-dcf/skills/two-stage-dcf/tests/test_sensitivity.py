"""The sensitivity grid, which both artifacts display and neither computes."""

import pytest

from dcf_engine import run_model, sensitivity_axes, sensitivity_grid
from test_schedule import bundle


def test_the_grid_is_rows_of_waccs_by_columns_of_growths():
    b = bundle()
    waccs, growths = [0.09, 0.10, 0.11], [0.02, 0.03]
    grid = sensitivity_grid(b, waccs, growths)
    assert len(grid) == 3 and all(len(row) == 2 for row in grid)


def test_the_centre_of_the_default_grid_is_the_base_case():
    b = bundle()
    waccs, growths = sensitivity_axes(b)
    assert waccs[2] == pytest.approx(b["rates"]["wacc"])
    assert growths[2] == pytest.approx(b["assumptions"]["sales_growth"]["terminal"])
    grid = sensitivity_grid(b, waccs, growths)
    assert grid[2][2] == pytest.approx(run_model(b)["value_per_share"])


def test_value_falls_as_the_discount_rate_rises():
    b = bundle()
    grid = sensitivity_grid(b, [0.08, 0.10, 0.12], [0.05])
    assert grid[0][0] > grid[1][0] > grid[2][0]


def test_a_pair_with_no_perpetuity_is_none_not_an_exception():
    b = bundle()
    grid = sensitivity_grid(b, [0.04], [0.05, 0.02])
    assert grid[0][0] is None          # growth at the discount rate
    assert grid[0][1] is not None


def test_the_grid_does_not_disturb_the_bundle():
    b = bundle()
    before = b["rates"]["wacc"], b["assumptions"]["sales_growth"]["terminal"]
    sensitivity_grid(b, *sensitivity_axes(b))
    assert (b["rates"]["wacc"], b["assumptions"]["sales_growth"]["terminal"]) == before


def test_a_notch_is_a_percentage_point_for_a_rate_and_a_proportion_for_a_turnover():
    from dcf_engine import DEFAULT_SHIFT, NATURAL_SHIFT, shift_label
    assert NATURAL_SHIFT["sales_to_net_ppe"] == ("relative", 0.05)
    assert DEFAULT_SHIFT == ("absolute", 0.01)
    assert shift_label("sales_growth", *DEFAULT_SHIFT) == "1pp"
    assert shift_label("sales_to_net_ppe", *NATURAL_SHIFT["sales_to_net_ppe"]) \
        == "5% of itself"


def test_one_way_sensitivity_moves_every_year_at_once():
    from dcf_engine import one_way_sensitivity
    b = bundle()
    points = one_way_sensitivity(b, "ebitda_margin", shifts=(-0.01, 0.0, 0.01))
    assert [p[0] for p in points] == [-0.01, 0.0, 0.01]
    assert points[1][2] == pytest.approx(run_model(b)["value_per_share"])
    assert points[0][2] < points[1][2] < points[2][2]


def test_a_turnover_shift_is_proportional_not_absolute():
    from dcf_engine import one_way_sensitivity
    points = one_way_sensitivity(bundle(), "sales_to_net_ppe", shifts=(0.05,))
    # The fixture's terminal turnover is 2.0, so +5 percent is 2.1, not 2.05.
    assert points[0][1] == pytest.approx(2.10)


def test_ranking_puts_the_widest_span_first_and_names_the_notch():
    from dcf_engine import driver_ranking
    rows = driver_ranking(bundle())
    assert rows == sorted(rows, key=lambda r: r["span"], reverse=True)
    assert all(r["shift"] for r in rows)
    assert {"sales growth", "ebitda margin"} <= {r["driver"] for r in rows}


def test_ranking_survives_a_driver_the_model_refuses():
    """Growth pushed past the discount rate has no value; it must not crash."""
    from dcf_engine import driver_ranking
    b = bundle()
    b["rates"]["wacc"] = 0.055           # terminal growth 5% -- a 1pp rise breaks it
    rows = driver_ranking(b)
    assert not any(r["driver"] == "sales growth" for r in rows)
    assert rows                          # the others still rank


def test_the_sensitivity_grid_does_not_disturb_the_bundle_either():
    from dcf_engine import driver_ranking
    b = bundle()
    before = b["assumptions"]["ebitda_margin"]["explicit"][:]
    driver_ranking(b)
    assert b["assumptions"]["ebitda_margin"]["explicit"] == before
