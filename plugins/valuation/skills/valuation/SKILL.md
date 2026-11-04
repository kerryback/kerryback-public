---
name: valuation
argument-hint: "[ticker]"
description: >-
  Two-stage DCF valuation of a public company, started with "/valuation {ticker}".
  Runs unattended from start to finish: it never stops to ask. Builds a
  two-stage enterprise valuation of the company from its historical financial
  statements and its text — five explicit forecast years on sales growth,
  EBITDA margin, a sales-to-net-PP&E turnover on next year's sales, a
  depreciation rate, and ratios of each operating asset and liability to that
  year's sales, then those ratios held constant forever. Fetches the statements
  and 10-Ks from SEC EDGAR, the earnings press releases from 8-K filings, and
  the call transcripts from the Motley Fool; classifies every balance-sheet
  line; computes the historical ratios with a script; reads the text for
  evidence on each driver; then writes one HTML page with four tabs (Line
  items, Forecasts, an editable Baseline, and DCF) on which every judgment call
  is flagged for review, and an Excel workbook with live formulas. If
  ~/repos/homepage exists, it publishes the page there by copying it in,
  committing, and pushing; otherwise the page stays local.
---

# Two-stage enterprise valuation, unattended

Value a company by forecasting five explicit years and then holding every ratio
constant forever. The arithmetic lives in `dcf_engine.py` and is fixed. Your job
is to decide what the balance sheet means and what the drivers should be, argue
for those choices from the history and the text, and flag every choice a
reviewer might make differently.

## The two rules

1. You never write valuation arithmetic. You write a JSON bundle; the scripts do
   the rest. Historical ratios come from `dcf_history.py`, forecast figures from
   `dcf_engine.py`. A number you compute yourself will disagree with the
   artifacts and nobody will know which is wrong.

2. You never stop to ask. This skill runs from the ticker to a published page
   and a workbook in one pass, with no question to the user at any point. Where
   the interactive version of this skill would wait for approval, make the call
   yourself, record it as a judgment call in the bundle, and carry on. The page
   flags every judgment call where it was made and lists them all in a panel
   above the tabs, so the review happens on the page, after the run, instead
   of in the conversation. Do not use AskUserQuestion, do not end a turn with a
   question, and do not pause for confirmation between steps.

The only reason to stop early is that the run cannot produce a valuation at
all: no ticker was given, EDGAR has no 10-K for it, or the statements cannot be
loaded. Then say what is missing and stop. Everything short of that is a
judgment call, not a stop.

## What counts as a judgment call

Record one only where a competent analyst could reasonably have chosen
otherwise. Write each as one or two sentences: what you chose, and what the
alternative was and what it would do. "Other non-current assets treated as
operating; `excluded` is the alternative and would raise the value, because
this line is 20% of sales" is a judgment call.

Standard lines with an unambiguous bucket are never judgment calls: accounts
receivable, inventories, accounts payable, accrued liabilities, deferred
revenue, net PP&E, cash, marketable securities, short- and long-term debt,
goodwill. Do not flag them. Flagging an obvious call buries the real ones and
tells the reviewer the run did not know the basics. If you are unsure whether
something is a judgment call, ask whether you can name the alternative a
serious analyst would actually argue for. If you cannot, it is not one.

Where they go in the bundle:

- `classification[i].judgment`: a line that genuinely could go in more than
  one bucket. In practice that is the hard cases in
  `reference/classification.md` (leases, deferred taxes, related-party
  balances, reserves) and mixed "other" lines holding pieces that belong in
  different buckets, since a line takes exactly one bucket.
- `assumptions.<driver>.judgment` (and the same under `operating_assets.<key>`
  and `operating_liabilities.<key>`): a driver where the history and the text
  disagree and you picked one, a ratio you faded or held against its trend, a
  terminal growth rate away from 3.5 percent, or a year-1 ratio set to absorb a
  one-time item.
- `judgments`, a top-level list of `{"tab", "subject", "call"}`, for
  everything else: the WACC placeholder (below), the diluted share count, the
  opening NOL, a statement check that failed in the fetch, a missing input
  (no transcripts, no press releases), and anything the engine warned about
  that you chose to leave in place.

## The run

The skill starts as `/valuation {ticker}`. The ticker is `$ARGUMENTS`. Uppercase it
for `dcf_fetch.py`. If no ticker came with the command, say that one is needed
and stop; do not ask a question.

Work in `~/data/<ticker>`, lowercase. All scripts are in this skill's folder.
They need `pandas` and `openpyxl`, and fetching also needs `requests` and
`beautifulsoup4`. Run them with whatever Python the project uses.

```
  fetch -> inventory -> classify -> history -> text -> propose
        -> build page -> workbook -> publish -> report
```

### 1. Fetch

```bash
python dcf_fetch.py AAPL ~/data/aapl
```

EDGAR needs a contact name and email. The script reads it from `--contact`
or the `SEC_USER_AGENT` environment variable. If neither is set, the fetch
exits with a message. Do not ask for a contact: report the message, tell the
user to set `SEC_USER_AGENT="Their Name their@email"`, and stop.

This writes the statements workbook, the 10-Ks, the earnings press releases and
the call transcripts. If a folder for the ticker already holds them, the fetch
skips what is present. A failed statement check ("CHECK" lines) goes in
`judgments`, with the line and the amount. Transcript coverage is uneven, so
record which quarters came back.

### 2. Inventory

```bash
python dcf_inputs.py ~/data/aapl
```

Load the three statements with `dcf_load.load_statements(path, sheet=...)` and
note the fiscal years each covers. Year 0 is the latest fiscal year on the
balance sheet. If the text is missing, carry on and record in `judgments` that
the forecast rests on history alone.

### 3. Classify

Assign every reported balance-sheet line to exactly one bucket: `net_ppe`,
`operating_asset`, `operating_liability`, `nonoperating_asset`, `debt_claim`,
`equity_claim`, `excluded`. Give each line a one-line `note`, and a `judgment`
where the call is not obvious. `reference/classification.md` has the buckets and
the hard cases. Read the 10-K's balance-sheet, lease and tax footnotes for the
contents of any "other" line before you bucket it.

Foot it, assets against total assets and liabilities against total liabilities:

```python
from dcf_history import check_footing
check_footing(asset_entries, {line: value_fy0, ...}, total_assets_fy0)
check_footing(liability_entries, {line: value_fy0, ...}, total_liabilities_fy0)
```

Common-equity lines are not classified. If the footing check raises, fix the
classification and run it again. It is a defect in your table, not a question
for the user.

Collect here too, each recorded in `judgments` with its source:

- diluted shares. Use year-end shares outstanding plus dilutive securities
  from the equity footnote, not the weighted average. Say which.
- the opening federal NOL carryforward from the tax footnote (zero if none).
- preferred stock and noncontrolling interests.

### 4. History

```python
from dcf_history import historical_ratios
out = historical_ratios(financials, classification, sales_line=...,
                        ebitda_line=..., depreciation_line=...)
```

If the statements report no EBITDA line, add an EBITDA series to the loaded
lines as operating income plus depreciation and amortisation from the cash-flow
statement, and say so in the `ebitda_margin` guidance. Put `out` in the
bundle's `history`. Its `notes` are rendered on the Forecasts tab. Cross-check
the depreciation rate against `realized_capex`.

### 5. Read the text

Read the MD&A, risk factors, tax and lease footnotes, transcripts and press
releases against the driver list. `reference/reading-text.md` says what to look
for, driver by driver. Collect quotes with their file and location. You will
put them in the bundle as `citations`, so collect quotes, not paraphrases.

### 6. Propose

Write `bundle.json` to the schema in `reference/model.md`, with a suggestion for
every driver. For each driver write:

- `guidance`: how to choose this driver. What makes it move, which projection
  method fits (a constant percent of sales; a percent varying by year; a
  driver other than sales; flat or zero for one-time items), what the history
  is and is not evidence for, and what would justify a different number. Write
  it for someone who has not read the filings.
- `citations`: `{quote, speaker, source}` for each passage that bears on it.
  Quote, do not paraphrase. If nothing in the documents bears on a driver, say
  so in the guidance.
- `rationale`: one or two sentences on why the suggested path sits where it
  does.
- `judgment`, where the choice is one (see above).

Terminal sales growth starts at 3.5 percent
(`dcf_engine.DEFAULT_TERMINAL_GROWTH`), a nominal perpetual rate. If you move
it, that is a judgment call.

The WACC: set `rates.wacc` to 0.10 for every company. Do not estimate it. Set
`rates.wacc_derivation` to "A placeholder of 10 percent, not an estimate for
this company. The true WACC should be calculated (cost of equity from CAPM,
after-tax cost of debt, market-value weights) and entered on the Baseline tab
or in the workbook's Inputs sheet." Add this entry to `judgments`:

```json
{"tab": "DCF", "subject": "WACC",
 "call": "10 percent is a placeholder, not an estimate for this company. The true WACC should be calculated and entered before the value is relied on."}
```

The sensitivity grid on the DCF tab shows the value across a range of WACCs
around 10 percent, so a reader can see how much the placeholder matters.

Then measure before you write any claim about what matters:

```python
from dcf_engine import driver_ranking, run_model
for row in driver_ranking(bundle):
    print(row["driver"], row["shift"], row["span_share"])
```

Never say a driver is what the valuation turns on, or that one barely matters,
unless this ranking supports it. The page shows the ranking beside your prose,
so a contradiction is visible. Then run `run_model(bundle)` once and read the
warnings. A negative implied capex, non-positive terminal EBIT, or a terminal
growth at or above the WACC describes a company that does not exist. Revise
the assumptions that cause it, and record what you changed as a judgment call.
Do not leave a warning in place unflagged.

Write the numbers out as the CSV, which is where numbers live from here on:

```bash
python dcf_assumptions.py bundle.json assumptions.csv
```

### 7. Build the page and the workbook

```bash
python build_pages.py bundle.json . --csv assumptions.csv --open
python build_workbook.py bundle.json <slug>-dcf.xlsx --csv assumptions.csv
```

Do not use `--live`. No one is watching a reload loop on an unattended run, and
the published copy must not carry the poller. `<slug>` is the lowercase ticker.

The page has four tabs: Line items (the classification), Forecasts (a section
per driver with history, guidance, quotes and rationale), Baseline (the
suggested numbers beside history, every cell editable, with WACC, NOL and
shares below), and DCF (headline values, schedule, bridge, sensitivity, driver
ranking, cost of capital). A panel above the tabs lists every judgment call,
and each one is also flagged where it was made.

The workbook has eight sheets: Inputs, Model, Bridge, Sensitivity, Drivers,
Historical, NOL schedule, Check. Every cell on Model, Bridge and NOL schedule is
a live formula. The page and the workbook do not link to each other.

### 8. Publish

```bash
python publish.py <slug>.html
```

If `~/repos/homepage` is not a Quarto site repo, the script does nothing and
says the page was not published. Pass that on in the report and carry on.
Otherwise it copies the page to `~/repos/homepage/<slug>.html` and
`~/repos/homepage/docs/<slug>.html`, lists it under `project.resources` in
`_quarto.yml`, commits only those paths, and pushes. It does not run
`quarto render` and does not stage anything else, so uncommitted work already
in the homepage repo is left alone and does not block the run. If
`_quarto.yml` had its own uncommitted changes, the script edits the file but
does not commit it, and says so. Pass that line on in the report. A failed
push is reported, not retried.

Publish only the page. The workbook stays local.

### 9. Report

Finish with one message:

- the page's local path, and its published URL if `publish.py` printed one
- the workbook's path
- enterprise value, the bridge, and value per share
- every engine warning
- the two or three drivers the ranking says the answer turns on
- the number of judgment calls, and the three with the largest effect on value
  (the full list is on the page)
- anything `publish.py` reported as not done

Then stop. Do not offer a menu of next steps and do not ask whether the numbers
look right. The page is where they get reviewed.

## Afterwards, if the user comes back

The user may return with different numbers, as a message or as the CSV text
copied from the Baseline tab. Write them into `assumptions.csv`, update the
`rationale` (and `judgment`, if the user has now settled it, delete it) for
each driver they changed, rebuild the page and the workbook, run `publish.py`
again, and report what moved and by how much. Never hand-edit the HTML and
never edit numbers inside `bundle.json`. The CSV is where numbers live.

To watch edits live while iterating locally, run `python serve.py .` in the
background and build with `--live --open`. Build again without `--live` before
publishing.

## What is in the folder

| File | What it does |
|---|---|
| `dcf_engine.py` | the recursion, the terminal value, the NOL, the bridge. Pure. |
| `dcf_fetch.py` | fetch a ticker's statements, 10-Ks, press releases and transcripts |
| `dcf_statements.py` | the statements workbook, from the 10-Ks' XBRL statement pages |
| `dcf_inputs.py` | find the inputs, from a folder or filenames |
| `dcf_load.py` | staged statements into a normalised dict |
| `dcf_history.py` | the footing check, and the historical driver ratios |
| `dcf_assumptions.py` | the numbers, to and from `assumptions.csv` |
| `build_pages.py` | the tabbed page, `<slug>.html`, with the judgment calls flagged |
| `build_workbook.py` | the Excel workbook with live formulas |
| `publish.py` | copy the page into ~/repos/homepage if it exists, commit only its own paths, push |
| `serve.py` | a no-cache static server for an optional watch loop |
| `dcf_open.py` | hand a built artifact to the browser or to Excel |
| `page.html`, `styles.css` | the page's shell and styles |
| `page.js` | the page's tabs, editable Baseline, and in-browser port of the engine |
| `reference/model.md` | the arithmetic and the bundle schema |
| `reference/classification.md` | the buckets, and the cases that are genuinely hard |
| `reference/staging.md` | the folder layout, and what each fetch source covers |
| `reference/reading-text.md` | what to look for in the filings, driver by driver |

## Why the artifacts check themselves

The recursion exists three times: in Python, in the workbook's Excel formulas,
and in `page.js`. Each copy is held to the Python engine. The workbook's Check
sheet resolves to FAIL and turns red if a formula disagrees with the engine.
The page re-values the suggested numbers on load and puts a warning at the top
of the DCF tab if it disagrees. If either fires, the numbers are not to be
trusted. Say so in the report.

`tests/test_page_js.py` runs `page.js` under node against `run_model`. Run
`python -m pytest tests/` after changing the engine, the workbook builder, or
`page.js`.
