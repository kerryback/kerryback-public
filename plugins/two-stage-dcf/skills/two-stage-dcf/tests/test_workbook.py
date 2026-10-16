"""The workbook is a model, not a picture of one, and it checks itself."""

import pytest

openpyxl = pytest.importorskip("openpyxl")

from build_workbook import build_workbook          # noqa: E402
from test_pages import rich_bundle                 # noqa: E402
from test_schedule import bundle                   # noqa: E402


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    path = tmp_path_factory.mktemp("wb") / "model.xlsx"
    build_workbook(rich_bundle(), str(path))
    return str(path)


def formulas(ws):
    return [c.value for row in ws.iter_rows() for c in row
            if isinstance(c.value, str) and c.value.startswith("=")]


def test_the_expected_sheets_are_there(built):
    wb = openpyxl.load_workbook(built)
    assert {"Inputs", "Model", "Bridge", "Historical", "NOL schedule", "Check"} \
        <= set(wb.sheetnames)


def test_model_cells_are_formulas_not_values(built):
    wb = openpyxl.load_workbook(built)
    assert len(formulas(wb["Model"])) > 80


def test_every_model_formula_reaches_back_to_inputs_or_the_model(built):
    wb = openpyxl.load_workbook(built)
    for f in formulas(wb["Model"]):
        assert "Inputs!" in f or any(ch.isdigit() for ch in f), f


def test_inputs_hold_values_the_user_can_type_over(built):
    wb = openpyxl.load_workbook(built)
    ws = wb["Inputs"]
    numeric = [c.value for row in ws.iter_rows() for c in row
               if isinstance(c.value, (int, float))]
    assert len(numeric) > 20
    assert not formulas(ws)


def test_check_sheet_compares_against_the_python_baseline(built):
    wb = openpyxl.load_workbook(built)
    text = " ".join(str(c.value) for row in wb["Check"].iter_rows()
                    for c in row if c.value is not None)
    assert "FAIL" in text
    assert "Model!" in text and "Bridge!" in text
    assert "COUNTIF" in text


def test_check_sheet_has_a_red_rule(built):
    wb = openpyxl.load_workbook(built)
    assert wb["Check"].conditional_formatting


def test_years_six_and_seven_read_the_terminal_column(built):
    wb = openpyxl.load_workbook(built)
    ws = wb["Model"]
    # Column G on Inputs is the terminal column; years 6 and 7 are Model G and H.
    sales_row = next(r for r in range(1, 30) if ws.cell(r, 1).value == "Sales")
    assert "Inputs!$G$" in ws.cell(sales_row, 7).value    # year 6
    assert "Inputs!$G$" in ws.cell(sales_row, 8).value    # year 7
    assert "Inputs!$F$" in ws.cell(sales_row, 6).value    # year 5


def test_sales_runs_one_year_past_the_schedule(built):
    wb = openpyxl.load_workbook(built)
    ws = wb["Model"]
    sales_row = next(r for r in range(1, 30) if ws.cell(r, 1).value == "Sales")
    # Year 8 carries sales, because year 7's net PP&E is set by year 8 sales.
    assert isinstance(ws.cell(sales_row, 9).value, str)
    ebitda_row = next(r for r in range(1, 30) if ws.cell(r, 1).value == "EBITDA")
    assert ws.cell(ebitda_row, 9).value is None


def test_a_company_with_no_claims_still_builds(tmp_path):
    out = tmp_path / "plain.xlsx"
    build_workbook(bundle(), str(out))
    wb = openpyxl.load_workbook(str(out))
    assert wb["Bridge"]["B3"].value.startswith("=")


def test_the_sensitivity_and_drivers_sheets_are_there(built):
    wb = openpyxl.load_workbook(built)
    assert "Sensitivity" in wb.sheetnames
    assert "Drivers" in wb.sheetnames


def test_the_sheets_read_in_a_sensible_order(built):
    wb = openpyxl.load_workbook(built)
    assert wb.sheetnames == ["Inputs", "Model", "Bridge", "Sensitivity",
                             "Drivers", "Historical", "NOL schedule", "Check"]


def test_the_snapshot_sheets_say_they_are_snapshots(built):
    """They hold values, not formulas, and must not pretend otherwise."""
    wb = openpyxl.load_workbook(built)
    for name in ("Sensitivity", "Drivers"):
        head = " ".join(str(wb[name].cell(r, 1).value or "") for r in (2, 3)).lower()
        assert "snapshot" in head
        assert "rebuild" in head


def test_the_drivers_sheet_says_what_it_varies(built):
    """The sheet once showed only the terminal level, which read as though the
    perpetuity alone was moving. It has to say that every year moves."""
    wb = openpyxl.load_workbook(built)
    ws = wb["Drivers"]
    caption = str(ws["A2"].value)
    assert "EVERY forecast year" in caption
    assert "not the perpetuity alone" in caption
    assert "equity value" in caption
    assert "refined" in caption
    body = " ".join(str(c.value) for row in ws.iter_rows() for c in row
                    if c.value is not None)
    assert "explicit years move too" in body


def test_the_drivers_sheet_ranks_widest_first(built):
    wb = openpyxl.load_workbook(built)
    ws = wb["Drivers"]
    spans = []
    for r in range(7, 40):
        if ws.cell(r, 1).value and isinstance(ws.cell(r, 6).value, (int, float)):
            spans.append(ws.cell(r, 6).value)
        elif spans:
            break
    assert spans == sorted(spans, reverse=True)
    assert len(spans) >= 5


def test_the_check_sheet_verifies_the_sensitivity_centre(built):
    wb = openpyxl.load_workbook(built)
    text = " ".join(str(c.value) for row in wb["Check"].iter_rows()
                    for c in row if c.value is not None)
    assert "Sensitivity!" in text
