# finance-data

Fetch free financial, market, and economic data and save it as CSV.

Ask for what you want in your own words — "Apple's daily prices since 2015", "the
Fama-French factors", "CPI and unemployment", "the daily Treasury curve" — and
Claude works out which source has it, confirms the choice, fetches it, and saves
a CSV you can use.

## Install

```
/plugin marketplace add kerryback/kerryback-public
/plugin install finance-data@kerryback-public
```

Then just ask for data. It also triggers on its own when data is a step toward
analysis you asked for.

## Requirements

Python. The skill builds its own environment the first time, so it doesn't
disturb whatever you have installed.

## Sources

| you want | where it comes from |
| --- | --- |
| stock, ETF, index prices and OHLCV | Yahoo Finance, Stooq |
| company fundamentals, SEC filings | SEC EDGAR |
| macro and interest-rate series | FRED |
| asset-pricing factor returns | Ken French Data Library |
| the Treasury yield curve | US Treasury |
| company profiles, estimates | FinnHub, Financial Modeling Prep |

Most of these need no key at all. FinnHub and Financial Modeling Prep do —
`FINNHUB_API_KEY` and `FMP_API_KEY`, both free tiers — and Claude offers to help
set them if you ask for something that needs one.

## Why routing matters

Free finance data is a minefield of sources that disagree, quietly change their
terms, or return something subtly different from what you asked for. The skill
picks a source and says which one it picked before fetching, so the provenance of
a number is never a mystery six months later when the result looks odd.

The CSV is the deliverable. It goes in your working directory with a name that
says what it is, and the code that produced it is re-runnable rather than a
one-off in a chat window.

## For research-grade panels

This is for free, quick, public data. For CRSP, Compustat, and IBES — the
survivorship-bias-free panels an empirical asset-pricing paper needs — use the
`wrds` plugin instead. Different data, different care required.
