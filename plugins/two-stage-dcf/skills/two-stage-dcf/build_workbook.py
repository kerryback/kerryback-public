"""Write the valuation as an Excel workbook with live formulas.

Not pasted values: every figure on the Model sheet is a formula that references
the Inputs sheet, so the workbook is a model someone can drive rather than a
picture of one. That makes it a third implementation of the recursion, after
``dcf_engine.py`` and the JavaScript in the app, so it carries the same
safeguard: the Check sheet holds the Python engine's base-case numbers beside
formulas that resolve to FAIL and turn red the moment a cell disagrees. Excel
evaluates them on open, so drift announces itself to whoever opens the file.

Sheets: Inputs, Model, Bridge, Sensitivity, Drivers, Historical, NOL schedule,
Check.

One caveat, stated on the sheets themselves. The Sensitivity and Drivers sheets
hold computed values, not formulas, because every cell on them is a complete
re-run of the model at different assumptions and Excel cannot do that from a
formula. They are a snapshot of the Inputs as they stood when the file was
written. Change an Input and the Model, Bridge and NOL sheets follow; those two
do not, until you rebuild.
"""

import os

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from dcf_engine import (LAST_YEAR, N_EXPLICIT, PERPETUITY_YEAR, TRANSITION_YEAR,
                        driver_entries, driver_ranking, one_way_sensitivity,
                        run_model, sensitivity_axes, sensitivity_grid)

TOLERANCE = 1e-6
SHIELD_YEARS = 200          # the horizon dcf_engine._nol_shield_pv uses

HEAD = Font(bold=True, color="FFFFFF")
HEAD_FILL = PatternFill("solid", fgColor="00205B")
GROUP = Font(bold=True, color="00205B")
TOTAL = Font(bold=True)
TOP = Border(top=Side(style="thin"))

PCT = "0.0%"
MULT = "0.00"
NUM = "#,##0.0"
SHARE = "#,##0.00"


def _input_col(year):
    """Inputs columns B..F carry years 1 to 5; G carries the terminal column,
    which years 6 and 7 both read -- that is what makes year 6 the transition."""
    return get_column_letter(2 + (year - 1 if year <= N_EXPLICIT else N_EXPLICIT))


def _model_col(year):
    return get_column_letter(1 + year)


def _write_inputs(ws, bundle):
    """Return a map from driver name to its row, plus the rows of the singles."""
    a, base, meta = bundle["assumptions"], bundle["base"], bundle["meta"]

    ws["A1"] = f"{meta.get('company', 'Company')} — assumptions"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = (f"Fiscal year {meta.get('fiscal_year_0', '')} is year 0. "
                f"All figures in {meta.get('units', 'the units of the statements')}. "
                f"Working-capital ratios are stated against the same year's sales; "
                f"net PP&E is a turnover on next year's.")
    ws["A2"].font = Font(italic=True, size=9)

    row = 4
    ws.cell(row, 1, "Assumption").font = HEAD
    ws.cell(row, 1).fill = HEAD_FILL
    for t in range(1, N_EXPLICIT + 1):
        c = ws.cell(row, 1 + t, f"Year {t}")
        c.font, c.fill = HEAD, HEAD_FILL
    c = ws.cell(row, 2 + N_EXPLICIT, "Terminal")
    c.font, c.fill = HEAD, HEAD_FILL

    rows, row = {}, row + 1

    def block(title):
        nonlocal row
        ws.cell(row, 1, title).font = GROUP
        row += 1

    def line(key, label, spec, fmt):
        nonlocal row
        ws.cell(row, 1, label)
        for t in range(1, N_EXPLICIT + 1):
            c = ws.cell(row, 1 + t, spec["explicit"][t - 1])
            c.number_format = fmt
        c = ws.cell(row, 2 + N_EXPLICIT, spec["terminal"])
        c.number_format = fmt
        rows[key] = row
        row += 1

    block("Growth and margin")
    line("sales_growth", "Sales growth", a["sales_growth"], PCT)
    line("ebitda_margin", "EBITDA margin", a["ebitda_margin"], PCT)

    block("Property, plant and equipment")
    line("sales_to_net_ppe", "Next-year sales / net PP&E", a["sales_to_net_ppe"], MULT)
    line("depreciation_rate", "Depreciation / prior net PP&E", a["depreciation_rate"], PCT)

    labels = {c.get("key"): c["line"] for c in bundle.get("classification", [])
              if c.get("key")}

    block("Operating assets, as a share of sales")
    asset_rows = []
    for key, spec in a["operating_assets"].items():
        line(f"oa::{key}", labels.get(key, key), spec, PCT)
        asset_rows.append(rows[f"oa::{key}"])

    block("Operating liabilities, as a share of sales")
    liability_rows = []
    for key, spec in a["operating_liabilities"].items():
        line(f"ol::{key}", labels.get(key, key), spec, PCT)
        liability_rows.append(rows[f"ol::{key}"])

    block("Taxes")
    line("cash_tax_rate", "Cash tax rate on taxable income", a["cash_tax_rate"], PCT)

    row += 1
    singles = {}

    def single(key, label, value, fmt):
        nonlocal row
        ws.cell(row, 1, label)
        c = ws.cell(row, 2, value)
        c.number_format = fmt
        singles[key] = row
        row += 1

    ws.cell(row, 1, "Rates and year-0 balances").font = GROUP
    row += 1
    single("wacc", "WACC", bundle["rates"]["wacc"], PCT)
    single("nol_limitation", "NOL limitation",
           bundle["rates"].get("nol_limitation", 0.80), PCT)
    single("nol", "Opening NOL carryforward", float(base.get("nol") or 0.0), NUM)
    single("shares", "Diluted shares", meta.get("diluted_shares") or 0.0, NUM)
    single("sales0", "Sales, year 0", base["sales"], NUM)
    single("nppe0", "Net PP&E, year 0", base["net_ppe"], NUM)
    single("nwc0", "Net working capital, year 0",
           sum(base.get("operating_assets", {}).values())
           - sum(base.get("operating_liabilities", {}).values()), NUM)

    row += 1
    ws.cell(row, 1, "Claims on the enterprise").font = GROUP
    row += 1
    claims = {"nonoperating_assets": [], "debt_claims": [], "equity_claims": []}
    for side, prefix in (("nonoperating_assets", "Plus"),
                         ("debt_claims", "Less"),
                         ("equity_claims", "Less")):
        for key, value in base.get(side, {}).items():
            ws.cell(row, 1, f"{prefix} {key.replace('_', ' ')}")
            ws.cell(row, 2, float(value)).number_format = NUM
            claims[side].append((key, row))
            row += 1

    ws.column_dimensions["A"].width = 38
    for t in range(2, 3 + N_EXPLICIT):
        ws.column_dimensions[get_column_letter(t)].width = 12

    return rows, singles, asset_rows, liability_rows, claims


def _write_model(ws, bundle, rows, singles, asset_rows, liability_rows):
    """Every cell here is a formula. Returns a map from line key to row."""
    def inp(row, year):
        return f"Inputs!${_input_col(year)}${row}"

    def one(key):
        return f"Inputs!$B${singles[key]}"

    ws["A1"] = "Forecast — every cell below is a formula over the Inputs sheet"
    ws["A1"].font = Font(bold=True, size=14)

    header = 3
    ws.cell(header, 1, "Forecast").font = HEAD
    ws.cell(header, 1).fill = HEAD_FILL
    for t in range(1, LAST_YEAR + 2):
        label = f"Year {t}"
        if t == TRANSITION_YEAR:
            label += " · transition"
        elif t == PERPETUITY_YEAR:
            label += " · perpetuity"
        elif t == LAST_YEAR + 1:
            label = "Year 8 · for year 7's PP&E"
        c = ws.cell(header, 1 + t, label)
        c.font, c.fill = HEAD, HEAD_FILL
        c.alignment = Alignment(horizontal="right")

    m = {}
    r = header + 1
    for key, label in [
        ("sales", "Sales"), ("next_sales", "Next-year sales"),
        ("ebitda", "EBITDA"), ("net_ppe", "Net PP&E, closing"),
        ("depreciation", "Depreciation"), ("capex", "Capital expenditure"),
        ("nwc", "Net working capital, closing"),
        ("delta_nwc", "Investment in working capital"),
        ("ebit", "EBIT"), ("nol_open", "NOL carryforward, opening"),
        ("nol_used", "NOL used"), ("taxable_income", "Taxable income"),
        ("tax", "Cash taxes"), ("nol_close", "NOL carryforward, closing"),
        ("effective_tax_rate", "Effective tax rate"),
        ("fcf", "Free cash flow"), ("discount_factor", "Discount factor"),
        ("pv_fcf", "PV of free cash flow"),
    ]:
        ws.cell(r, 1, label)
        m[key] = r
        r += 1

    ratio_terms = ("(" + "+".join(f"Inputs!{_input_col(1)}${x}" for x in asset_rows)
                   + (("-" + "-".join(f"Inputs!{_input_col(1)}${x}" for x in liability_rows))
                      if liability_rows else "") + ")")

    for t in range(1, LAST_YEAR + 2):
        col = _model_col(t)
        prev = _model_col(t - 1)

        # Sales runs one year past the schedule because year 7's net PP&E is set
        # by year 8 sales.
        base_sales = one("sales0") if t == 1 else f"{prev}{m['sales']}"
        ws.cell(m["sales"], 1 + t,
                f"={base_sales}*(1+{inp(rows['sales_growth'], min(t, TRANSITION_YEAR))})"
                ).number_format = NUM
        if t == LAST_YEAR + 1:
            continue                       # year 8 carries sales and nothing else

        nxt = _model_col(t + 1)
        ws.cell(m["next_sales"], 1 + t, f"={nxt}{m['sales']}").number_format = NUM
        ws.cell(m["ebitda"], 1 + t,
                f"={inp(rows['ebitda_margin'], t)}*{col}{m['sales']}").number_format = NUM
        ws.cell(m["net_ppe"], 1 + t,
                f"={col}{m['next_sales']}/{inp(rows['sales_to_net_ppe'], t)}"
                ).number_format = NUM

        prior_nppe = one("nppe0") if t == 1 else f"{prev}{m['net_ppe']}"
        ws.cell(m["depreciation"], 1 + t,
                f"={inp(rows['depreciation_rate'], t)}*{prior_nppe}").number_format = NUM
        ws.cell(m["capex"], 1 + t,
                f"={col}{m['net_ppe']}-{prior_nppe}+{col}{m['depreciation']}"
                ).number_format = NUM

        ratios = ratio_terms.replace(f"Inputs!{_input_col(1)}$",
                                     f"Inputs!{_input_col(t)}$")
        # Working capital on this year's sales; net PP&E above is the one line
        # that leads sales by a year.
        ws.cell(m["nwc"], 1 + t, f"={ratios}*{col}{m['sales']}").number_format = NUM
        prior_nwc = one("nwc0") if t == 1 else f"{prev}{m['nwc']}"
        ws.cell(m["delta_nwc"], 1 + t,
                f"={col}{m['nwc']}-{prior_nwc}").number_format = NUM
        ws.cell(m["ebit"], 1 + t,
                f"={col}{m['ebitda']}-{col}{m['depreciation']}").number_format = NUM

        opening = one("nol") if t == 1 else f"{prev}{m['nol_close']}"
        ws.cell(m["nol_open"], 1 + t, f"={opening}").number_format = NUM

        ebit = f"{col}{m['ebit']}"
        openc = f"{col}{m['nol_open']}"
        if t >= PERPETUITY_YEAR:
            # The perpetuity is taxed at the full rate; a carryforward still
            # burning off is not a steady state, so it is valued on the NOL sheet.
            ws.cell(m["nol_used"], 1 + t, 0).number_format = NUM
            ws.cell(m["taxable_income"], 1 + t, f"={ebit}").number_format = NUM
            ws.cell(m["nol_close"], 1 + t, f"={openc}").number_format = NUM
        else:
            ws.cell(m["nol_used"], 1 + t,
                    f"=IF({ebit}<=0,0,MIN({one('nol_limitation')}*{ebit},{openc}))"
                    ).number_format = NUM
            ws.cell(m["taxable_income"], 1 + t,
                    f"=IF({ebit}<=0,0,{ebit}-{col}{m['nol_used']})").number_format = NUM
            ws.cell(m["nol_close"], 1 + t,
                    f"=IF({ebit}<=0,{openc}-{ebit},{openc}-{col}{m['nol_used']})"
                    ).number_format = NUM

        ws.cell(m["tax"], 1 + t,
                f"={inp(rows['cash_tax_rate'], t)}*{col}{m['taxable_income']}"
                ).number_format = NUM
        ws.cell(m["effective_tax_rate"], 1 + t,
                f"=IF({ebit}=0,0,{col}{m['tax']}/{ebit})").number_format = PCT
        ws.cell(m["fcf"], 1 + t,
                f"={col}{m['ebitda']}-{col}{m['tax']}-{col}{m['capex']}"
                f"-{col}{m['delta_nwc']}").number_format = NUM
        ws.cell(m["fcf"], 1 + t).font = TOTAL
        ws.cell(m["discount_factor"], 1 + t,
                f"=1/(1+{one('wacc')})^{t}").number_format = "0.0000"
        ws.cell(m["pv_fcf"], 1 + t,
                f"={col}{m['fcf']}*{col}{m['discount_factor']}").number_format = NUM

    ws.column_dimensions["A"].width = 32
    for t in range(2, LAST_YEAR + 3):
        ws.column_dimensions[get_column_letter(t)].width = 13
    return m


def _write_nol_sheet(ws, bundle, singles, model):
    """The shield on a carryforward that outlives year 6, year by year.

    ``dcf_engine`` runs this as a loop; a worksheet has to unroll it, so the
    horizon here matches the engine's ``max_years``.
    """
    def one(key):
        return f"Inputs!$B${singles[key]}"

    ws["A1"] = "Tax shield on the carryforward surviving year 6"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = ("Year 7 onward is taxed at the full rate in the perpetuity, so the "
                "shield is valued here instead and added to the bridge.")
    ws["A2"].font = Font(italic=True, size=9)

    for j, label in enumerate(["Year", "EBIT", "Opening balance", "Used",
                               "Tax saved", "PV of tax saved", "Closing balance"]):
        c = ws.cell(4, 1 + j, label)
        c.font, c.fill = HEAD, HEAD_FILL

    g = f"Inputs!${_input_col(TRANSITION_YEAR)}${singles['_growth_row']}"
    rate = f"Inputs!${_input_col(PERPETUITY_YEAR)}${singles['_tax_row']}"

    first = 5
    for i in range(SHIELD_YEARS):
        r = first + i
        year = PERPETUITY_YEAR + i
        ws.cell(r, 1, year)
        if i == 0:
            ws.cell(r, 2, f"=Model!{_model_col(PERPETUITY_YEAR)}{model['ebit']}")
            ws.cell(r, 3, f"=Model!{_model_col(TRANSITION_YEAR)}{model['nol_close']}")
        else:
            ws.cell(r, 2, f"=B{r - 1}*(1+{g})")
            ws.cell(r, 3, f"=G{r - 1}")
        ws.cell(r, 4, f"=MIN({one('nol_limitation')}*B{r},C{r})")
        ws.cell(r, 5, f"=IF(B{r}<=0,0,{rate}*D{r})")
        ws.cell(r, 6, f"=E{r}/(1+{one('wacc')})^A{r}")
        ws.cell(r, 7, f"=IF(B{r}<=0,C{r},C{r}-D{r})")
        for j in range(2, 8):
            ws.cell(r, j).number_format = NUM

    last = first + SHIELD_YEARS - 1
    ws.cell(last + 2, 1, "PV of the shield").font = TOTAL
    ws.cell(last + 2, 6, f"=SUM(F{first}:F{last})").font = TOTAL
    ws.cell(last + 2, 6).number_format = NUM
    ws.column_dimensions["A"].width = 8
    for j in "BCDEFG":
        ws.column_dimensions[j].width = 16
    return last + 2


def _write_bridge(ws, bundle, singles, model, shield_row, claims):
    def one(key):
        return f"Inputs!$B${singles[key]}"

    ws["A1"] = "From enterprise value to the shareholders"
    ws["A1"].font = Font(bold=True, size=14)

    g = f"Inputs!${_input_col(TRANSITION_YEAR)}${singles['_growth_row']}"
    pv16 = (f"SUM(Model!{_model_col(1)}{model['pv_fcf']}:"
            f"Model!{_model_col(TRANSITION_YEAR)}{model['pv_fcf']})")

    r = 3
    entries = [
        ("PV of free cash flow, years 1 to 6", f"={pv16}", False),
        ("Terminal value at the end of year 6",
         f"=Model!{_model_col(PERPETUITY_YEAR)}{model['fcf']}/({one('wacc')}-{g})", False),
        ("PV of the terminal value", f"=B4/(1+{one('wacc')})^{TRANSITION_YEAR}", False),
        ("Enterprise value of operations", "=B3+B5", True),
        ("PV of remaining NOL carryforward", f"='NOL schedule'!F{shield_row}", False),
    ]
    for label, formula, bold in entries:
        ws.cell(r, 1, label)
        c = ws.cell(r, 2, formula)
        c.number_format = NUM
        if bold:
            ws.cell(r, 1).font = TOTAL
            c.font = TOTAL
        r += 1

    first_claim = r
    for side, sign in (("nonoperating_assets", "+"), ("debt_claims", "-"),
                       ("equity_claims", "-")):
        for key, input_row in claims[side]:
            prefix = "Plus" if sign == "+" else "Less"
            ws.cell(r, 1, f"{prefix} {key.replace('_', ' ')}")
            ws.cell(r, 2, f"={sign}Inputs!$B${input_row}").number_format = NUM
            r += 1

    ws.cell(r, 1, "Equity value").font = TOTAL
    claim_sum = f"+SUM(B{first_claim}:B{r - 1})" if r > first_claim else ""
    c = ws.cell(r, 2, f"=B6+B7{claim_sum}")
    c.font, c.number_format, c.border = TOTAL, NUM, TOP
    equity_row = r
    r += 1

    ws.cell(r, 1, "Diluted shares")
    ws.cell(r, 2, f"={one('shares')}").number_format = NUM
    r += 1
    ws.cell(r, 1, "Value per share").font = TOTAL
    c = ws.cell(r, 2, f"=IF({one('shares')}=0,\"\",B{equity_row}/{one('shares')})")
    c.font, c.number_format, c.border = TOTAL, SHARE, TOP

    ws.column_dimensions["A"].width = 40
    ws.column_dimensions["B"].width = 16
    return {"ev_ops": 6, "pv_nol": 7, "equity_value": equity_row,
            "terminal_value": 4, "pv_terminal": 5, "pv_explicit": 3}


DRIVERS_CAPTION = (
    "How much a change in each driver moves the equity value, given the baseline "
    "assumptions. Each driver is moved by the amount shown in EVERY forecast year "
    "at once -- the five explicit years and the perpetuity together, not the "
    "perpetuity alone. These are a local measure around the current baseline and "
    "will shift somewhat as the assumptions are refined. The percentages are the "
    "same for the equity value and for the value per share, since the share count "
    "does not move.")

SNAPSHOT = ("A snapshot, not a formula: every cell is a full re-run of the model "
            "at different assumptions, which Excel cannot do from a formula. "
            "Change an Input and rebuild to refresh this sheet.")


def _write_sensitivity(ws, bundle):
    """WACC against terminal growth, the two the answer is most exposed to."""
    ws["A1"] = "Sensitivity — value per share"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = SNAPSHOT
    ws["A2"].font = Font(italic=True, size=9)
    ws["A2"].alignment = Alignment(wrap_text=True)

    waccs, growths = sensitivity_axes(bundle)
    grid = sensitivity_grid(bundle, waccs, growths)
    base_wacc = bundle["rates"]["wacc"]
    base_growth = bundle["assumptions"]["sales_growth"]["terminal"]

    header = 5
    c = ws.cell(header, 1, "WACC \\ terminal growth")
    c.font, c.fill = HEAD, HEAD_FILL
    for j, growth in enumerate(growths):
        c = ws.cell(header, 2 + j, growth)
        c.font, c.fill, c.number_format = HEAD, HEAD_FILL, PCT

    centre = None
    for i, wacc in enumerate(waccs):
        r = header + 1 + i
        c = ws.cell(r, 1, wacc)
        c.number_format = PCT
        c.font = TOTAL
        for j, growth in enumerate(growths):
            cell = ws.cell(r, 2 + j, grid[i][j])
            cell.number_format = SHARE
            here = (abs(wacc - base_wacc) < 1e-12
                    and abs(growth - base_growth) < 1e-12)
            if here:
                cell.font = TOTAL
                cell.fill = PatternFill("solid", fgColor="EEF2F9")
                centre = cell.coordinate

    ws.column_dimensions["A"].width = 24
    for j in range(2, 2 + len(growths)):
        ws.column_dimensions[get_column_letter(j)].width = 13
    return centre


def _write_drivers(ws, bundle):
    """Which drivers move the answer, and one-way tables for each."""
    ws["A1"] = "Drivers — what actually moves the answer"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = DRIVERS_CAPTION
    ws["A2"].font = Font(italic=True, size=9)
    ws["A2"].alignment = Alignment(wrap_text=True)
    ws["A3"] = SNAPSHOT
    ws["A3"].font = Font(italic=True, size=9)
    ws["A3"].alignment = Alignment(wrap_text=True)

    ranking = driver_ranking(bundle)
    base = ranking[0]["base"] if ranking else None

    r = 5
    ws.cell(r, 1, "Moved one notch each way, in every year at once").font = GROUP
    r += 1
    for j, label in enumerate(["Driver", "Notch", "Down", "Base", "Up", "Span"]):
        c = ws.cell(r, 1 + j, label)
        c.font, c.fill = HEAD, HEAD_FILL
    r += 1
    for row in ranking:
        ws.cell(r, 1, row["driver"])
        ws.cell(r, 2, row["shift"])
        for j, key in enumerate(("low",)):
            ws.cell(r, 3, row["low"]).number_format = SHARE
        ws.cell(r, 4, base).number_format = SHARE
        ws.cell(r, 5, row["high"]).number_format = SHARE
        ws.cell(r, 6, row["span"]).number_format = SHARE
        r += 1

    r += 2
    ws.cell(r, 1, "One-way tables, two notches each way").font = GROUP
    r += 1
    ws.cell(r, 1, "The notch is applied to every forecast year. The level row "
                  "shows where the terminal ends up; the explicit years move by "
                  "the same amount.").font = Font(italic=True, size=9)
    r += 2
    for name, key, label in driver_entries(bundle):
        points = one_way_sensitivity(bundle, name, key)
        ws.cell(r, 1, label).font = TOTAL
        ws.cell(r + 1, 1, "terminal level (explicit years move too)")
        ws.cell(r + 2, 1, "value per share")
        for j, (shift, level, value) in enumerate(points):
            ws.cell(r, 2 + j, "base" if shift == 0 else f"{shift * 100:+g}")
            ws.cell(r, 2 + j).font = HEAD
            ws.cell(r, 2 + j).fill = HEAD_FILL
            lvl = ws.cell(r + 1, 2 + j, level)
            lvl.number_format = MULT if name == "sales_to_net_ppe" else PCT
            val = ws.cell(r + 2, 2 + j, value)
            val.number_format = SHARE
        r += 4

    ws.column_dimensions["A"].width = 30
    for j in "BCDEF":
        ws.column_dimensions[j].width = 14


def _write_historical(ws, bundle):
    ws["A1"] = "Historical driver ratios"
    ws["A1"].font = Font(bold=True, size=14)
    history = bundle.get("history") or {}
    years = history.get("years") or []
    ratios = history.get("ratios") or {}

    if not years:
        ws["A3"] = "No history was carried in the bundle."
        return

    for j, y in enumerate(years):
        c = ws.cell(3, 2 + j, y)
        c.font, c.fill = HEAD, HEAD_FILL
    ws.cell(3, 1, "Ratio").font = HEAD
    ws.cell(3, 1).fill = HEAD_FILL

    r = 4
    for name, series in ratios.items():
        if isinstance(series, dict) and series and isinstance(
                next(iter(series.values())), dict):
            for key, inner in series.items():
                ws.cell(r, 1, f"{name}: {key}")
                for j, y in enumerate(years):
                    if y in inner or str(y) in inner:
                        ws.cell(r, 2 + j, inner.get(y, inner.get(str(y))))
                r += 1
        else:
            ws.cell(r, 1, name)
            for j, y in enumerate(years):
                if y in series or str(y) in series:
                    ws.cell(r, 2 + j, series.get(y, series.get(str(y))))
            r += 1
    ws.column_dimensions["A"].width = 38


def _write_check(ws, bundle, result, model, bridge_rows, sensitivity_centre=None):
    """The workbook's own parity check against the Python engine."""
    ws["A1"] = "Does this workbook still agree with the engine that wrote it?"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = (f"Every cell below compares a formula on the Model or Bridge sheet "
                f"against the number dcf_engine.py computed when this file was "
                f"written. Anything but 'ok' means the workbook has been edited in "
                f"a way that changed the arithmetic, not just the assumptions. "
                f"Tolerance {TOLERANCE}.")
    ws["A2"].font = Font(italic=True, size=9)
    ws["A2"].alignment = Alignment(wrap_text=True)

    ws["A4"] = "Overall"
    ws["A4"].font = TOTAL
    summary = ws["B4"]

    keys = ["sales", "ebitda", "net_ppe", "depreciation", "capex", "nwc",
            "delta_nwc", "ebit", "nol_used", "taxable_income", "tax",
            "nol_close", "fcf", "pv_fcf"]

    header = 6
    ws.cell(header, 1, "Model line").font = HEAD
    ws.cell(header, 1).fill = HEAD_FILL
    for t in range(1, LAST_YEAR + 1):
        c = ws.cell(header, 1 + t, f"Year {t}")
        c.font, c.fill = HEAD, HEAD_FILL

    r = header + 1
    for key in keys:
        ws.cell(r, 1, key)
        for t in range(1, LAST_YEAR + 1):
            baseline = result["schedule"][t - 1][key]
            ws.cell(r, 1 + t,
                    f"=IF(ABS(Model!{_model_col(t)}{model[key]}-({baseline!r}))"
                    f">{TOLERANCE},\"FAIL\",\"ok\")")
        r += 1

    r += 1
    ws.cell(r, 1, "Bridge figure").font = HEAD
    ws.cell(r, 1).fill = HEAD_FILL
    ws.cell(r, 2, "Check").font = HEAD
    ws.cell(r, 2).fill = HEAD_FILL
    r += 1
    for key, row in bridge_rows.items():
        ws.cell(r, 1, key)
        ws.cell(r, 2,
                f"=IF(ABS(Bridge!B{row}-({result[key]!r}))>{TOLERANCE},\"FAIL\",\"ok\")")
        r += 1

    if sensitivity_centre and result["value_per_share"] is not None:
        # The middle of the sensitivity grid is the base case by construction.
        # If it is not, the snapshot was written from different inputs.
        ws.cell(r, 1, "sensitivity grid centre = base case")
        ws.cell(r, 2,
                f"=IF(ABS(Sensitivity!{sensitivity_centre}-"
                f"({result['value_per_share']!r}))>{TOLERANCE},\"FAIL\",\"ok\")")
        r += 1

    last = r - 1
    body = f"B{header + 1}:{get_column_letter(1 + LAST_YEAR)}{last}"
    summary.value = f'=IF(COUNTIF({body},"FAIL")>0,"FAIL","ok")'
    summary.font = TOTAL

    ws.conditional_formatting.add(
        f"A4:{get_column_letter(1 + LAST_YEAR)}{last}",
        CellIsRule(operator="equal", formula=['"FAIL"'],
                   font=Font(bold=True, color="9C0006"),
                   fill=PatternFill("solid", fgColor="FFC7CE")))
    ws.column_dimensions["A"].width = 26


def build_workbook(bundle, out_path):
    """Render the workbook for ``bundle`` and return the path written."""
    result = run_model(bundle)

    wb = Workbook()
    inputs = wb.active
    inputs.title = "Inputs"

    rows, singles, asset_rows, liability_rows, claims = _write_inputs(inputs, bundle)
    # The NOL and Bridge sheets need the terminal growth and tax cells by row.
    singles["_growth_row"] = rows["sales_growth"]
    singles["_tax_row"] = rows["cash_tax_rate"]

    model = _write_model(wb.create_sheet("Model"), bundle, rows, singles,
                         asset_rows, liability_rows)
    shield_row = _write_nol_sheet(wb.create_sheet("NOL schedule"), bundle,
                                  singles, model)
    bridge_rows = _write_bridge(wb.create_sheet("Bridge"), bundle, singles,
                                model, shield_row, claims)
    centre = _write_sensitivity(wb.create_sheet("Sensitivity"), bundle)
    _write_drivers(wb.create_sheet("Drivers"), bundle)
    _write_historical(wb.create_sheet("Historical"), bundle)
    _write_check(wb.create_sheet("Check"), bundle, result, model, bridge_rows,
                 sensitivity_centre=centre)

    # Reading order: what you assume, what it produces, what it is worth, what
    # it is sensitive to, what the history was, and finally the machinery.
    order = ["Inputs", "Model", "Bridge", "Sensitivity", "Drivers", "Historical",
             "NOL schedule", "Check"]
    wb._sheets = [wb[name] for name in order]

    wb.save(out_path)
    return out_path


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bundle")
    ap.add_argument("out")
    ap.add_argument("--csv", help="assumptions CSV to overlay onto the bundle")
    ap.add_argument("--open", dest="open_it", action="store_true",
                    help="open the workbook when it is written")
    args = ap.parse_args()

    with open(args.bundle, encoding="utf-8") as fh:
        bundle = json.load(fh)
    if args.csv:
        from dcf_assumptions import apply_assumptions_csv
        bundle = apply_assumptions_csv(bundle, args.csv)
    written = build_workbook(bundle, args.out)
    print(written)

    if args.open_it:
        from dcf_open import open_path
        open_path(written)
