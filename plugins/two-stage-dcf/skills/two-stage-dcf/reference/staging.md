# Where the inputs come from

Either the skill fetches them for a ticker, or you point it at a folder that
already holds them, or you name the files directly.

## Fetching

```bash
python dcf_fetch.py JBSS ~/data/jbss --contact "Jane Doe jane@school.edu"
```

| What | Source | Notes |
|---|---|---|
| `<ticker>_financials_10k.xlsx` | SEC EDGAR, the XBRL statement pages (`R` files) of the last five 10-Ks | Each year from the most recent 10-K that reports it, so restated. $ thousands. Footing checks at the foot of each sheet; failures are printed. |
| `10k/` | SEC EDGAR, the 10-K documents | For the MD&A, risk factors and footnotes. |
| `press_releases/` | SEC EDGAR, Exhibit 99.1 of each 8-K with item 2.02 | `.htm` as filed and `.txt` for reading. Back three years before the oldest 10-K. |
| `transcripts/` | The Motley Fool transcript archive, found through the quote page and monthly sitemaps; plus any transcript a company filed with an 8-K | Coverage is uneven, worst for small companies and 2023-2025. Copyrighted: fine for coursework, not for redistribution. |

EDGAR requires a User-Agent with a name and an email address: `--contact`, or
the `SEC_USER_AGENT` environment variable. Fiscal quarters in file names come
from EDGAR's fiscal-year-end date and the filing or call date, so a release and
its call share a label; the fiscal year is named for the calendar year it ends
in. Re-running skips what is already there. Raw statement pages are cached in
`.edgar/` inside the folder.

Not every company can be fetched: one that does not file with the SEC has no
10-Ks, and a foreign private issuer files a 20-F, which this does not read.
Then stage the statements by hand in the layout below.

## A folder you already have

```bash
python dcf_inputs.py ~/data/jbss
```

```python
from dcf_inputs import inventory, describe
print(describe(inventory(financials="jbss.xlsx",
                         filings=["10k/FY2026.htm"],
                         transcripts=["calls/FY2026Q4.txt"])))
```

A folder is searched for the shapes these bundles arrive in. Naming files
directly overrides whatever the search found, so a folder with two workbooks in
it is not a problem -- say which one.

## The layout

```
<company>/
  financials.xlsx          three sheets, or three CSVs — see below
  10k/            *.htm    the filings themselves
  transcripts/    *        earnings call transcripts
  press/          *        press releases
```

Nothing but the statements is required. With no text, the skill forecasts off
history alone and says that is what it did.

## Statement shape

Line labels down the first column, fiscal years across one row. Both of these
parse, and the loader finds the header row itself:

```
,2025-12-31,2024-12-31,2023-12-31
Cash and cash equivalents,22.9,14.8,25.3
Accounts receivable, net,266.8,312.7,346.1
```

```
ProFrac Holding Corp. — Consolidated Balance Sheets
Fiscal years ending December 31. $ millions.
Source: SEC EDGAR, XBRL financial statements.

Line item,FY2023,FY2024,FY2025
Cash and cash equivalents,25.3,14.8,22.9
```

Metadata rows above the header are fine. Blank rows and section headers such as
`Current assets:` are dropped. Values may carry thousands separators, currency
symbols, or the accounting convention of parenthesising negatives.

A workbook is read one sheet at a time:

```python
from dcf_load import load_statements
balance = load_statements("financials.xlsx", sheet="Balance Sheet")
income  = load_statements("financials.xlsx", sheet="Income Statement")
cash    = load_statements("financials.xlsx", sheet="Cash Flow Statement")
```

Fiscal years come back ascending however the file ordered them. Duplicate line
labels are disambiguated as `Other`, `Other (2)`.

## What gets used

- Balance sheet: every line, classified. This is the gate.
- Income statement: revenue, and enough to construct EBITDA and depreciation.
- Cash flow statement: reported depreciation and capex, to check the PP&E
  roll-forward against what the company actually spent.
- Tax footnote: the opening federal NOL carryforward, and whether there is a
  valuation allowance against it.
- Cover or equity note: diluted shares.

## When it will not load

```
no row looks like a fiscal year header
```

means no row had a cell that parses as a year in any column but the first.
Check that the years are across a row rather than down a column, and that the
file is the statement rather than a summary of it.

## A note for the course

Five or six fiscal years is the right window. Fewer than three and the
historical ratios have nothing to say; more and you are averaging across a
different company.

Where each year comes from matters. The ACDC workbook takes each year from the
most recent 10-K that reports it, so the figures are restated. That is the right
choice for valuation, where you want the best current estimate of what happened,
and the wrong one for backtesting a signal, where you want what was knowable at
the time.
