# dcf

Two-stage enterprise valuation from a company's financial statements and its
text, fetched for a ticker or read from a folder.

Five explicit forecast years on sales growth, EBITDA margin, a sales-to-net-PP&E
turnover on next year's sales, a depreciation rate, and ratios of each operating
asset and liability to that year's sales; then those ratios held constant
forever. PP&E leads sales by a year because capacity is built ahead of the volume
it serves; working capital arises from the volume itself. Capex is the plug,
so steady-state capex lands at (g + d) times prior net PP&E and cannot go
negative on ordinary inputs. Year 6 runs on the terminal assumptions and absorbs
the balance-sheet transition; the perpetuity sits on year 7, which is genuinely
steady state. A running NOL carryforward shelters the explicit years, and
anything surviving year 6 is valued separately and shown in the bridge rather
than contaminating the perpetuity.

A run classifies every reported balance-sheet line and gets that approved,
computes the historical ratios with a script, reads the MD&A, risk factors,
transcripts and press releases for evidence on each driver, proposes assumptions
and discusses them, then writes:

- `<slug>.html`, one self-contained page with four tabs: Line items (the
  classification), Forecasts (a section per driver with the quoted evidence),
  Baseline (the suggested numbers beside the history, every forecast cell
  editable), and DCF (the forecast, bridge, sensitivity grid and driver
  ranking, which revalue in the browser as the Baseline is edited). The Baseline also shows the grid as `assumptions.csv`
  text, ready to copy back.
- `assumptions.csv`, the numbers and nothing else — the part that changes. Edit
  it and rebuild; everything slow-moving stays in `bundle.json`.
- an Excel workbook whose every model cell is a live formula.

The page carries no network references. `build_pages.py --live` adds a small
reload poller for the edit-and-watch loop, served by `serve.py`; rebuild without
the flag before sending it to anyone. The page and the workbook are separate
deliverables and do not link to each other.

The recursion exists three times -- Python, Excel formulas, and the page's
JavaScript -- and each is held to the Python engine. The workbook carries the
engine's base-case figures on a Check sheet beside formulas that resolve to FAIL
and turn red; the page re-values the suggested numbers on load and warns if it
disagrees with the figures the engine wrote into it; and `tests/test_page_js.py`
runs the JavaScript under node against the engine.

Give it a ticker and `dcf_fetch.py` gets the inputs: the statements and 10-Ks
from SEC EDGAR, earnings press releases from 8-K filings, and call transcripts
from the Motley Fool. EDGAR needs a contact name and email (`--contact` or
`SEC_USER_AGENT`). Or point it at a folder that already holds them.

## Install

```
/plugin marketplace add kerryback/kerryback-public
/plugin install two-stage-dcf@kerryback-public
```

## Tests

```
cd skills/two-stage-dcf && python -m pytest tests/
```

The workbook recalculation test needs LibreOffice; it skips cleanly without it,
and the workbook's own Check sheet covers that case the moment someone opens the
file in Excel.
