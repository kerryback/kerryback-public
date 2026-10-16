"""Actually evaluate the workbook's formulas and compare them to the engine.

openpyxl reads formulas but does not compute them, so the other workbook tests
can only check shape. This one hands the file to LibreOffice, which recalculates
on conversion, and reads the results back. Without it the Excel port would be
the one implementation nobody had ever run.

Skipped where LibreOffice is absent; the Check sheet inside the workbook is then
the guarantee, and it fires the moment anyone opens the file in Excel.
"""

import json
import shutil
import subprocess

import pytest

openpyxl = pytest.importorskip("openpyxl")

from build_workbook import build_workbook          # noqa: E402
from dcf_engine import run_model                   # noqa: E402
from test_pages import rich_bundle                 # noqa: E402

SOFFICE = shutil.which("soffice") or shutil.which("libreoffice")

pytestmark = pytest.mark.skipif(
    not SOFFICE,
    reason="LibreOffice is not installed, so the workbook's formulas cannot be "
           "evaluated here; the Check sheet inside the file covers this")


def recalculate(path, tmp_path):
    out = tmp_path / "recalculated"
    out.mkdir(exist_ok=True)
    proc = subprocess.run(
        [SOFFICE, "--headless", "--calc", "--convert-to", "xlsx",
         "--outdir", str(out), str(path)],
        capture_output=True, text=True, timeout=180)
    result = out / path.name
    if not result.exists():
        raise AssertionError("LibreOffice did not convert the workbook:\n"
                             + proc.stdout + proc.stderr)
    return openpyxl.load_workbook(str(result), data_only=True)


def cell_named(ws, label, column=2):
    for r in range(1, ws.max_row + 1):
        if ws.cell(r, 1).value == label:
            return ws.cell(r, column).value
    raise AssertionError(f"no row labelled {label!r}")


@pytest.mark.parametrize(
    "nol, ident", [(0.0, "no-carryforward"), (4000.0, "surviving-carryforward")])
def test_the_workbook_computes_what_the_engine_computes(nol, ident, tmp_path):
    b = rich_bundle()
    b["base"]["nol"] = nol
    path = tmp_path / f"{ident}.xlsx"
    build_workbook(b, str(path))

    wb = recalculate(path, tmp_path)
    want = run_model(b)

    # The workbook's own verdict on itself.
    assert wb["Check"]["B4"].value == "ok", "the Check sheet reports a FAIL"
    fails = [(wb["Check"].cell(c.row, 1).value, c.coordinate)
             for row in wb["Check"].iter_rows() for c in row if c.value == "FAIL"]
    assert not fails, f"failing checks: {fails}"

    # And an independent comparison, in case the Check sheet is the broken part.
    bridge = wb["Bridge"]
    assert cell_named(bridge, "Enterprise value of operations") == \
        pytest.approx(want["ev_ops"], rel=1e-9)
    assert cell_named(bridge, "PV of remaining NOL carryforward") == \
        pytest.approx(want["pv_nol"], rel=1e-9, abs=1e-9)
    assert cell_named(bridge, "Equity value") == \
        pytest.approx(want["equity_value"], rel=1e-9)
    assert cell_named(bridge, "Value per share") == \
        pytest.approx(want["value_per_share"], rel=1e-9)


def test_the_check_sheet_fires_when_the_model_is_tampered_with(tmp_path):
    """A check that cannot fail is worse than no check."""
    b = rich_bundle()
    path = tmp_path / "tampered.xlsx"
    build_workbook(b, str(path))

    wb = openpyxl.load_workbook(str(path))
    ws = wb["Model"]
    row = next(r for r in range(1, 30) if ws.cell(r, 1).value == "Depreciation")
    ws.cell(row, 2).value = ws.cell(row, 2).value + "*1.0001"
    wb.save(str(path))

    recalculated = recalculate(path, tmp_path)
    assert recalculated["Check"]["B4"].value == "FAIL"
