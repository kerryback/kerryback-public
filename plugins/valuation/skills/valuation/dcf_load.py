"""Read a staged financial statement into a normalised dict.

This module does no network work; ``dcf_fetch.py`` does that. Statements
arrive in two shapes:

    ,2025-12-31,2024-12-31          a yfinance-style CSV, newest first
    Cash,22.9,14.8

    Company - Consolidated Balance Sheets       an EDGAR-derived workbook with
    Fiscal years ending December 31...          metadata rows above the header
    (blank)
    Line item,FY2024,FY2025
    Cash,14.8,22.9

Both have line labels in the first column and fiscal years across the top, so
one loader handles them: scan down for the first row holding a cell
that parses as a fiscal year, treat it as the header, and read everything below.

Deciding which line is which is *not* this module's job. That is the
classification gate, and it belongs to the person running the valuation.
"""

import csv
import os
import re

import pandas as pd

YEAR = re.compile(r"(19|20)\d{2}")


def _as_year(cell):
    """The fiscal year in a header cell, or None.

    Handles '2025-12-31', 'FY2025', '2025', and datetime cells.
    """
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return None
    if hasattr(cell, "year") and not isinstance(cell, str):
        return int(cell.year)
    m = YEAR.search(str(cell))
    return int(m.group(0)) if m else None


def _as_number(cell):
    """A float, or None. Tolerates thousands separators, currency, and the
    accounting convention of parenthesising negatives."""
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return None
    if isinstance(cell, (int, float)):
        return float(cell)
    text = str(cell).strip()
    if not text or text in {"-", "--", "—", "n/a", "N/A", "nan"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()").replace(",", "").replace("$", "").strip()
    try:
        value = float(text)
    except ValueError:
        return None
    return -value if negative else value


def _read_raw(path, sheet=None):
    """A ragged-tolerant grid. Statement files carry title and note rows with
    one cell above a header row with many, which trips pandas' CSV parser, so
    read the rows ourselves and pad them to the widest."""
    ext = os.path.splitext(path)[1].lower()
    if ext in {".xlsx", ".xlsm", ".xls"}:
        return pd.read_excel(path, sheet_name=sheet or 0, header=None)
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    width = max((len(r) for r in rows), default=0)
    return pd.DataFrame([r + [""] * (width - len(r)) for r in rows])


def load_statements(path, sheet=None):
    """Return ``{"years": [...], "lines": {label: {year: value}}, "source": path}``.

    Years come back in ascending order regardless of how the file ordered them.
    """
    raw = _read_raw(path, sheet)

    header_row, year_columns = None, None
    for i in range(len(raw)):
        found = {}
        for j in range(1, raw.shape[1]):
            year = _as_year(raw.iat[i, j])
            if year is not None and year not in found.values():
                found[j] = year
        if found:
            header_row, year_columns = i, found
            break

    if header_row is None:
        raise ValueError(
            f"{path}: no row looks like a fiscal year header. The loader wants "
            f"line-item labels down the first column and fiscal years across "
            f"one row -- '2025-12-31', 'FY2025' or '2025' all parse. Metadata "
            f"rows above the header are fine.")

    lines, seen = {}, {}
    for i in range(header_row + 1, len(raw)):
        label = raw.iat[i, 0]
        label = "" if label is None or pd.isna(label) else str(label).strip()
        if not label:
            continue
        values = {year: _as_number(raw.iat[i, j])
                  for j, year in year_columns.items()}
        values = {y: v for y, v in values.items() if v is not None}
        if not values:
            continue                       # a section header such as 'Current assets:'
        seen[label] = seen.get(label, 0) + 1
        key = label if seen[label] == 1 else f"{label} ({seen[label]})"
        lines[key] = values

    return {
        "years": sorted(set(year_columns.values())),
        "lines": lines,
        "source": path,
    }
