"""The assumptions CSV: the numbers, and only the numbers."""

import pytest

from dcf_assumptions import (apply_assumptions_csv, read_assumptions_csv,
                             write_assumptions_csv)
from dcf_engine import run_model
from test_pages import rich_bundle


@pytest.fixture
def csv_path(tmp_path):
    return str(write_assumptions_csv(rich_bundle(), tmp_path / "assumptions.csv"))


def test_a_round_trip_changes_nothing(csv_path):
    """Write it out, read it back, and the valuation must not move."""
    before = run_model(rich_bundle())
    after = run_model(apply_assumptions_csv(rich_bundle(), csv_path))
    assert after["value_per_share"] == pytest.approx(before["value_per_share"])
    assert after["ev_ops"] == pytest.approx(before["ev_ops"])


def test_writing_the_csv_again_is_byte_for_byte_stable(csv_path, tmp_path):
    """The CSV is authoritative once written; applying it must not drift it."""
    once = apply_assumptions_csv(rich_bundle(), csv_path)
    again = write_assumptions_csv(once, tmp_path / "again.csv")
    assert open(csv_path).read() == open(again).read()


def test_percents_are_written_as_percents(csv_path):
    text = open(csv_path).read()
    assert "sales_growth,,%,30,15,8,5,4,5" in text        # not 0.30, 0.15, ...
    assert "sales_to_net_ppe,,x,1.6,1.7,1.8,1.9,2.4,2" in text


def test_editing_a_cell_moves_the_valuation(csv_path):
    before = run_model(rich_bundle())["value_per_share"]
    text = open(csv_path).read().replace(
        "ebitda_margin,,%,-5,2,12,18,21,20",
        "ebitda_margin,,%,-5,2,12,18,21,30")
    open(csv_path, "w").write(text)
    after = run_model(apply_assumptions_csv(rich_bundle(), csv_path))["value_per_share"]
    assert after > before * 1.2


def test_the_csv_carries_numbers_and_nothing_else(csv_path):
    """Guidance and citations stay in the bundle; the CSV stays small."""
    text = open(csv_path).read()
    assert "How to think about" not in text
    assert "Nut costs" not in text
    assert len(text.splitlines()) < 30


def test_guidance_survives_the_overlay(csv_path):
    out = apply_assumptions_csv(rich_bundle(), csv_path)
    assert out["assumptions"]["sales_growth"]["guidance"]
    assert out["assumptions"]["sales_growth"]["citations"]
    assert out["classification"]


def test_comments_are_ignored(tmp_path):
    p = tmp_path / "a.csv"
    write_assumptions_csv(rich_bundle(), p)
    body = p.read_text()
    p.write_text("# a note to myself\n" + body + "\n# and another\n")
    apply_assumptions_csv(rich_bundle(), str(p))       # must not raise


def test_a_missing_row_is_an_error_not_a_silent_fallback(csv_path):
    kept = [ln for ln in open(csv_path) if not ln.startswith("ebitda_margin")]
    open(csv_path, "w").writelines(kept)
    with pytest.raises(ValueError, match="ebitda_margin"):
        apply_assumptions_csv(rich_bundle(), csv_path)


def test_a_row_the_bundle_does_not_know_is_an_error(csv_path):
    with open(csv_path, "a") as fh:
        fh.write("operating_assets,goodwill,%,1,1,1,1,1,1\n")
    with pytest.raises(ValueError, match="goodwill"):
        apply_assumptions_csv(rich_bundle(), csv_path)


def test_the_wrong_number_of_years_is_an_error(csv_path):
    text = open(csv_path).read().replace(
        "sales_growth,,%,30,15,8,5,4,5", "sales_growth,,%,30,15,8")
    open(csv_path, "w").write(text)
    with pytest.raises(ValueError, match="sales_growth"):
        apply_assumptions_csv(rich_bundle(), csv_path)


def test_a_non_number_names_the_row_and_the_line(csv_path):
    text = open(csv_path).read().replace(
        "sales_growth,,%,30,15,8,5,4,5", "sales_growth,,%,30,tbd,8,5,4,5")
    open(csv_path, "w").write(text)
    with pytest.raises(ValueError, match="sales_growth"):
        apply_assumptions_csv(rich_bundle(), csv_path)


def test_singles_are_read_from_their_own_short_rows(csv_path):
    text = open(csv_path).read().replace("wacc,,%,10", "wacc,,%,12")
    open(csv_path, "w").write(text)
    out = apply_assumptions_csv(rich_bundle(), csv_path)
    assert out["rates"]["wacc"] == pytest.approx(0.12)


def test_a_single_given_a_whole_row_is_an_error(csv_path):
    text = open(csv_path).read().replace("wacc,,%,10", "wacc,,%,10,10,10,10,10,10")
    open(csv_path, "w").write(text)
    with pytest.raises(ValueError, match="wacc"):
        apply_assumptions_csv(rich_bundle(), csv_path)


def test_the_file_uses_unix_line_endings(csv_path):
    """It gets edited with sed and read in git diffs, not only in Excel."""
    assert b"\r\n" not in open(csv_path, "rb").read()
