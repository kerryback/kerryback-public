---
name: two-stage-dcf
description: >-
  Build a two-stage enterprise valuation of a company from its historical
  financial statements and its text — five explicit forecast years on sales
  growth, EBITDA margin, a sales-to-net-PP&E turnover on next year's sales, a
  depreciation rate, and ratios of each operating asset and liability to that
  year's sales, then those ratios held constant forever. Use this whenever the
  user wants a company valued or a discounted cash flow model built: "value ProFrac", "what is ACDC
  worth", "build me a DCF", "two-stage enterprise valuation", "run a DCF on
  this 10-K", "is this stock cheap on a cash flow basis", or when they point at
  a folder of statements and filings and ask what the business is worth.
  Classifies every reported balance-sheet line and gets that approved before
  forecasting, computes the historical ratios with a script, reads the MD&A,
  risk factors, transcripts and press releases for evidence on each driver,
  suggests assumptions and explains how to choose each one, then writes one
  HTML page with four tabs -- Line items, Forecasts (the evidence), an editable
  Baseline grid, and DCF, which revalues in the browser as the Baseline is
  edited -- and
  waits for the user to settle the numbers. Give it a ticker and it fetches the
  inputs itself -- the statements and 10-Ks from SEC EDGAR, the earnings press
  releases from 8-K filings, and the call transcripts from the Motley Fool -- or
  point it at a folder that already holds them. When the assumptions are
  settled it also delivers an Excel workbook with live formulas plus
  sensitivity and driver-ranking sheets.
---

# Two-stage enterprise valuation

Value a company by forecasting five explicit years and then holding every ratio
constant forever. The arithmetic lives in `dcf_engine.py` and is fixed. Your job
is to decide what the company's balance sheet means, what the drivers should be,
and to argue for those choices from the history and the text.

## The one rule

You never write valuation arithmetic. You write a JSON bundle; the scripts do
the rest. If you find yourself computing an enterprise value in your head, in a
message, or in an ad-hoc script, stop — that number will disagree with the
artifacts and you will not know which is wrong.

Historical ratios come from `dcf_history.py`, not from reading figures off a
page. Forecast figures come from `dcf_engine.py`. The page's in-browser
calculator, `page.js`, is a port of the engine held to it by tests; it exists so
the reader can try numbers, not so you can read answers off it.

## Before you start

The inputs come one of two ways: `dcf_fetch.py` fetches them for a ticker, or
the user points you at a folder that already holds them.
`reference/staging.md` has the folder layout and what each fetch source covers.
Get inputs only through `dcf_fetch.py` or from the user, never by ad-hoc web
searching, and never invent a missing input.

The scripts need `pandas` and `openpyxl`, and fetching also needs `requests`
and `beautifulsoup4`. Run them with whatever Python the project uses.

## The shape of a run

Six steps, in order. Three of them stop and wait, and the fourth stop is the
long one: you build the page and then go round the loop with the user until
they are satisfied. Do not run ahead of a gate -- the whole value of this skill
is that the judgement calls get made by someone who knows the company.

```
  inputs -> classify -> history -> text -> propose, build, and WAIT
                                              |
                                    loop on the numbers
                                              |
                                              v
                                    deliver the workbook
```

### Phase 0 — inputs

If the user gives a ticker and no folder, or a folder with no statements in it,
fetch:

```bash
python dcf_fetch.py JBSS ~/data/jbss --contact "Jane Doe jane@school.edu"
```

EDGAR requires every client to identify itself with a name and an email
address. Use `SEC_USER_AGENT` if it is set; otherwise ask the user for theirs
once and pass it as `--contact`. Do not make one up.

This writes the statements workbook (`<ticker>_financials_10k.xlsx`, three
sheets built from the last five 10-Ks, each year from the most recent 10-K that
reports it), the 10-K documents, the earnings press releases and the call
transcripts. It takes a minute or two. Read out the check rows it reports as
failing, if any: a statement that does not foot is a problem in the inputs, and
it is better found now than at the classification gate. Transcript coverage is
uneven -- the archive misses quarters, more often for small companies -- so say
which quarters came back rather than implying the set is complete.

Either way, take inventory. The user can also point you at a folder, or name
the files:

```bash
python dcf_inputs.py ~/data/jbss
```

```python
from dcf_inputs import inventory, describe
print(describe(inventory(financials="jbss.xlsx",
                         transcripts=["calls/FY2026Q4.txt"])))
```

Report what was found and what was not. Then load the statements and say which
fiscal years each covers and how many line items.

If there are still no statements -- the fetch failed, or the company does not
file with the SEC -- stop and say what you need. If there is no text, carry on
and say that the forecast will rest on history alone; that belongs on the
Forecasts tab, not buried in the conversation.

### Phase 1 — classify (gate)

Read the balance sheet and assign every reported line to exactly one bucket:
`net_ppe`, `operating_asset`, `operating_liability`, `nonoperating_asset`,
`debt_claim`, `equity_claim`, `excluded`. Give each non-obvious call a one-line
reason. `reference/classification.md` has the buckets and the recurring hard
cases — leases, goodwill, deferred taxes, tax receivable agreements,
related-party balances, noncontrolling interests, mezzanine preferred.

Then foot it:

```python
from dcf_history import check_footing
check_footing(classification, balance_lines, reported_total)
```

This raises if a reported line is unclassified, and names the line and what it
was worth. That is deliberate: a line quietly left out of the table is exactly
how a real liability goes missing from a valuation. `excluded` is a bucket —
use it rather than omitting a line.

Collect here too: diluted shares, the opening federal NOL carryforward from the
tax footnote, and the preferred and noncontrolling interests.

Show the user the table and wait. Do not compute a ratio until they approve it.

### Phase 2 — history

```python
from dcf_history import historical_ratios
out = historical_ratios(financials, classification, sales_line="Revenues",
                        ebitda_line=..., depreciation_line=...)
```

Present every driver year by year, plus realised capex from the PP&E
roll-forward so the depreciation rate can be sanity-checked against what the
company actually spent. Read `out["notes"]` aloud — it names the anchors that
are unusable. An EBITDA margin from a year with negative EBITDA is not a
starting point, and saying so is more useful than averaging it in.

### Phase 3 — the text (gate)

Read the MD&A, risk factors, transcripts and press releases against the driver
list specifically. `reference/reading-text.md` says what to look for, driver by
driver. Output evidence per driver, each citation naming the file and where in
it — not a general summary of the company.

Show the user the evidence and wait, before you propose numbers from it.

### Phase 4 — propose, then build and wait (gate)

You advise; the user decides. Everything you put in the assumption table is a
suggestion, and the artifacts say so on their face. What the user actually needs
from you is not a defence of your numbers but enough to choose their own.

Before you write a word of guidance, measure:

```python
from dcf_engine import driver_ranking
for row in driver_ranking(bundle):
    print(row["driver"], row["shift"], row["span_share"])
```

This moves each driver one notch each way, in every year at once, and re-runs
the model. Never claim that a driver is what the valuation turns on, or that one
barely matters, without checking it here first. The intuition is wrong often
enough to be worth the twenty seconds: on JBSS the sales-to-PP&E turnover is the
most conspicuous thing on the balance sheet and moves the answer about a seventh
as much as sales growth does.

The ranking goes onto the DCF tab as its own section, as a share of value, and
each driver's own span appears beside its history in its section on the
Forecasts tab. So a claim in your prose that the measured span contradicts will
be contradicted in plain sight, on the same page.

Say what a driver governs, which is often not the same as how much it moves the
answer. A driver with a narrow span is worth a sentence saying so, because
knowing which arguments to skip is as useful as knowing which to have.

So for every driver write, into the bundle:

- `guidance` — how to choose this driver. What makes it move, which of the
  methods below fits this company, what the history is and is not evidence for,
  and what would make you pick a different number. Write it to someone who has
  not read the filings.
- `citations` — the passages that bear on it, each a `{quote, speaker, source}`.
  Quote, do not paraphrase, and name the file. Advice with nothing behind it in
  the documents should say so rather than sounding confident.
- `rationale` — one or two sentences on why the suggested path sits where it
  does, given all of the above.

Ways to project a line, worth naming explicitly when you advise: a constant
percent of sales; a percent of sales varying by year, for a ratio in transition;
a driver other than sales, such as inventory as days of cost of sales or
depreciation as a rate on prior-year PP&E; and flat or zero, for one-time items
and balances with no reason to move.

Terminal sales growth starts at 3.5 percent — `dcf_engine.DEFAULT_TERMINAL_GROWTH`
— unless the company gives you a reason to move it. It is a nominal perpetual
rate, so it carries long-run inflation as well as real growth, which is why it
sits well above any plausible real rate and still below nominal GDP. If you
depart from it, say what the reason was.

Then build the page and stop.

```bash
python serve.py .                     # once, in another shell
python dcf_assumptions.py bundle.json assumptions.csv
python build_pages.py bundle.json . --csv assumptions.csv --live --open
```

This writes one file, `<slug>.html`, with four tabs in a single row:

- Line items: the classification table.
- Forecasts: a section per driver -- history strip, guidance, quoted citations,
  rationale -- plus the history notes when there are any.
- Baseline: the suggested numbers beside five years of history, every forecast
  cell an input, with WACC, NOL limitation, opening NOL and diluted shares
  editable below.
- DCF: headline values, forecast schedule, bridge, sensitivity grid, driver
  ranking, cost of capital, and the model description. It revalues as the
  Baseline is edited.

Every figure is rendered by the engine first, so the page is right before any
script runs. Edits persist in the reader's browser and are dropped
automatically when a rebuild changes the suggested numbers. The Baseline tab
also shows the current grid as `assumptions.csv` text, ready to copy.

`--open` puts the page in front of the user rather than leaving them to go and
find it. Start `serve.py` first so it opens the URL that live-reloads rather
than a `file://` path, which cannot.

Give the user the link and wait. Do not build the workbook yet -- it is the
finished deliverable, not a working document.

### The loop

The user can try numbers on the Baseline tab themselves and watch the DCF tab
move. When they want a set kept, they either tell you the numbers or paste the
CSV from the Baseline tab. Either way: write them into `assumptions.csv`,
rebuild with `--live`, and say what moved and by how much. A rebuild makes the
kept numbers the new suggested column. Never hand-edit the HTML, and never edit
the numbers inside `bundle.json` -- the CSV is where numbers live.

If the user overrules a suggestion, update that driver's `rationale` in the
bundle so the Forecasts tab says what was chosen and why, rather than arguing
for a number nobody is using.

When the user asks whether a driver is worth arguing about, the ranking on the
DCF tab already answers it, and it re-measures as they edit.

Keep going until they say the assumptions are settled.

Sanity rules worth stating out loud when you propose:

- Terminal growth is a nominal perpetual rate. Above nominal GDP means the
  company eventually becomes the economy.
- Terminal growth must be below the WACC or there is no perpetuity, and the
  engine will refuse.
- Year 6 runs on the terminal assumptions and absorbs any gap between year 5's
  balance-sheet ratios and the terminal ones. A large gap makes year 6's capex
  lumpy; the engine warns when it exceeds ten percent.
- Working capital is a ratio to the same year's sales. Net PP&E is the one
  exception, a turnover on next year's sales, because capacity is built ahead of
  the volume it serves.
- The WACC is a single number, editable on the workbook's Inputs sheet. Put
  the CAPM and cost-of-debt derivation in `rates.wacc_derivation` so the
  reasoning travels with both artifacts.

Discuss, iterate, and only move on when the user is satisfied.

### Phase 5 — deliver

Only once the user says the assumptions are settled. Rebuild the page
*without* `--live`, so it carries no reload poller, and write the workbook:

```bash
python build_pages.py bundle.json . --csv assumptions.csv
python build_workbook.py bundle.json <slug>-dcf.xlsx --csv assumptions.csv --open
```

`--open` launches the workbook. On a machine with no desktop it says so and
prints the path instead, which is all anyone can do; it never fails the run.

Three artifacts, with different jobs.

`<slug>.html` is the page: the argument on the Line items and Forecasts tabs,
the answer on DCF, and an editable Baseline that lets anyone holding the file try their own numbers
without you. It is self-contained -- no network references -- so it opens
anywhere. If this session can publish an HTML page as a shareable artifact,
publish it and give the user the link as well as the file.

`assumptions.csv` holds the numbers and nothing else. It is the thing that
changes. Everything slow-moving stays in `bundle.json`.

The page and the workbook are separate deliverables. Do not link either from
the other: the page never names the workbook, and the workbook never points at
the page.

The workbook is the deliverable. Eight sheets: Inputs, Model, Bridge,
Sensitivity, Drivers, Historical, NOL schedule, Check. Every cell on Model,
Bridge and NOL schedule is a live formula over Inputs, so the user can drive it
without you. Sensitivity and Drivers hold computed values — each cell there is a
whole re-run of the model, which Excel cannot do from a formula — and both
sheets say so on their face.

Report the enterprise value, the bridge, the value per share, every warning, and
the two or three drivers the Drivers sheet says the answer actually turns on.

Warnings are not decoration — a negative implied capex or a non-positive
terminal EBIT means the assumptions are describing a company that does not
exist. If they settle on
different assumptions, edit the CSV and rebuild both rather than hand-editing
either artifact — and update the `rationale` to match what they chose, including
where they overruled you.

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
| `build_pages.py` | the tabbed page, `<slug>.html` |
| `build_workbook.py` | the Excel workbook with live formulas |
| `serve.py` | a no-cache static server for the watch loop |
| `dcf_open.py` | hand a built artifact to the browser or to Excel |
| `page.html`, `styles.css` | the page's shell and styles |
| `page.js` | the page's tabs, editable Baseline, and in-browser port of the engine |
| `reference/model.md` | the arithmetic and the bundle schema |
| `reference/classification.md` | the buckets, and the cases that are genuinely hard |
| `reference/staging.md` | the folder layout, and what each fetch source covers |
| `reference/reading-text.md` | what to look for in the filings, driver by driver |

## Why the workbook checks itself

The recursion exists three times: in Python, in the workbook's Excel formulas,
and in `page.js`. Each copy is held to the Python engine.

The workbook carries the engine's base-case figures on a Check sheet, beside
formulas that resolve to FAIL and turn red. The page carries the engine's
figures in its data block and re-values the suggested numbers on load; if the
two disagree it puts a warning at the top of the DCF tab. If you ever see
either, the numbers are not to be trusted -- say so plainly rather than working
around it.

`tests/test_page_js.py` runs `page.js` under node against `run_model` --
schedule, bridge, warnings, sensitivity and ranking. Run `python -m pytest
tests/` after changing any of the three.
