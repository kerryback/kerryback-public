"""Reading staged statements in the shapes they actually arrive in."""

import pytest

from dcf_load import load_statements


def test_csv_with_iso_date_columns_newest_first(tmp_path):
    p = tmp_path / "balance.csv"
    p.write_text(",2025-12-31,2024-12-31\nCash,22.9,14.8\nInventories,150.0,160.0\n")
    out = load_statements(str(p))
    assert out["years"] == [2024, 2025]
    assert out["lines"]["Cash"][2025] == pytest.approx(22.9)
    assert out["lines"]["Inventories"][2024] == pytest.approx(160.0)


def test_header_row_is_found_below_metadata(tmp_path):
    p = tmp_path / "bs.csv"
    p.write_text("Some Company - Balance Sheets\nnotes about the source\n\n"
                 "Line item,FY2024,FY2025\nCash,14.8,22.9\n")
    out = load_statements(str(p))
    assert out["years"] == [2024, 2025]
    assert out["lines"]["Cash"][2024] == pytest.approx(14.8)


def test_section_headers_and_blank_rows_are_dropped(tmp_path):
    p = tmp_path / "bs.csv"
    p.write_text("Line item,FY2025\nCurrent assets:,\nCash,22.9\n,\n")
    out = load_statements(str(p))
    assert list(out["lines"]) == ["Cash"]


def test_values_with_commas_and_parentheses_parse(tmp_path):
    p = tmp_path / "bs.csv"
    p.write_text('Line item,FY2025\n"Accumulated deficit","(1,234.5)"\n')
    out = load_statements(str(p))
    assert out["lines"]["Accumulated deficit"][2025] == pytest.approx(-1234.5)


def test_duplicate_line_labels_are_disambiguated(tmp_path):
    p = tmp_path / "bs.csv"
    p.write_text("Line item,FY2025\nOther,1.0\nOther,2.0\n")
    out = load_statements(str(p))
    assert out["lines"]["Other"][2025] == pytest.approx(1.0)
    assert out["lines"]["Other (2)"][2025] == pytest.approx(2.0)


def test_unparseable_file_names_what_it_wanted(tmp_path):
    p = tmp_path / "junk.csv"
    p.write_text("no,columns,here\nstill,not,years\n")
    with pytest.raises(ValueError, match="fiscal year"):
        load_statements(str(p))


def test_excel_with_metadata_rows(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    p = tmp_path / "fin.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Balance Sheet"
    ws.append(["ProFrac Holding Corp. - Consolidated Balance Sheets"])
    ws.append(["Fiscal years ending December 31. $ millions."])
    ws.append([])
    ws.append(["Line item", "FY2024", "FY2025"])
    ws.append(["Cash and cash equivalents", 14.8, 22.9])
    wb.save(str(p))
    out = load_statements(str(p), sheet="Balance Sheet")
    assert out["years"] == [2024, 2025]
    assert out["lines"]["Cash and cash equivalents"][2025] == pytest.approx(22.9)
