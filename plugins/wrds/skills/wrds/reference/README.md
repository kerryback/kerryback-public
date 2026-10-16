# WRDS reference scripts

Twelve WRDS research scripts, converted from their original Jupyter notebooks to
plain `.py` (source cells only — no executed outputs, so no CRSP or Compustat
values are reproduced here). Author bylines are intact at the top of each file.

Almost all are by Qingyi (Freda) Song Drechsler, Research Director at WRDS;
`13f_io_breadth_v2.py` and `mom_fix2.py` are co-credited to Alex Malek, and
`evtstudy.py` is the WRDS event-study code. Most are also published on
[fredasongdrechsler.com/data-crunching](https://www.fredasongdrechsler.com/data-crunching);
the rest are WRDS Research Applications. They require a WRDS subscription to
run. Jupyter magics (`%%time`, `%matplotlib inline`) are commented out so each
file is valid Python.

These are a REFERENCE, not a dependency. `wrds_build.py` does not import them.
Consult them when a construction is in doubt — they are the closest thing the
field has to a house standard, and reading `ff3_crspCIZ.py` is what established
that CRSP v2 screens should read `msf_v2`'s inline columns rather than joining
`stksecurityinfohist`.

## When to reach for which

| File | What it builds | Consult it when |
|---|---|---|
| `ff3_crspCIZ.py` | Fama-French 3 factors on CRSP v2 / CIZ (Aug 2022) | Anything touching CRSP v2 screens, book equity, the June/December calendar, or NYSE breakpoints. The single most useful file here. |
| `ff3_v2.py` | Same, on legacy CRSP (Apr 2018, upd Jun 2020) | Reconciling against an older published replication, or reading v1 code someone else wrote |
| `iclink_v2.py` | CRSP↔IBES link, the ICLINK macro in Python (`crsp.stocknames`, `ibes.id`) | Any IBES work. This is the link-score methodology, not a lookup table |
| `pead_v4.py` | Post-earnings announcement drift (`comp.fundq`, `ibes.actu_epsus`, `ibes.detu_epsus`, `crsp.dsf`) | Earnings surprise / SUE construction, announcement-window returns, IBES actuals vs estimates |
| `dgtw_v4.py` | DGTW characteristic-based benchmarks (May 2018, upd Apr 2021) | Characteristic-matched benchmark returns; also a second opinion on book-to-market handling of division by zero |
| `mom_fix2.py` | Jegadeesh-Titman momentum portfolios | Momentum signal construction, skip-month conventions, portfolio rebalancing |
| `size1.py` | Size portfolios for CRSP securities (`crsp.msf`, `crsp.msix`) | Size sorts and NYSE size breakpoints |
| `sp500_crsp.py` | S&P 500 constituents from CRSP (`crsp.msp500list`) | Index membership. Note its header: S&P pulled `comp.idxcst_his` from WRDS, so CRSP is now the route |
| `evtstudy.py` | WRDS event study — abnormal returns, market model | Event studies; estimation/event window conventions and test statistics |
| `13f_io_breadth_v2.py` | Institutional ownership, concentration and breadth (`tfn.s34type1`) | 13F holdings, breadth-of-ownership signals |
| `13f_turnover_prod.py` | Institutional trades, flows, turnover ratios | Institutional turnover and flow measures from 13F |
| `13f_intro.py` | Count of 13F institutions by manager type over time | Orientation to `tfn.s34type1` structure and manager-type codes |

## Read them critically

They are a reference, not an authority. Known issues, all verified:

- `ff3_crspCIZ.py` and `ff3_v2.py` both do `mthret.fillna(0)` / `ret.fillna(0)`,
  which converts missing returns into zero returns rather than leaving them
  missing.
- `ff3_crspCIZ.py` computes `me = mthprc * shrout` with no `abs()`. Harmless on
  v2, where price is positive, but wrong if carried back to v1.
- The permco market-cap aggregation collapses to the largest-cap permno via an
  inner merge on the cap value, which duplicates rows when two share classes tie
  and drops permcos whose caps are all missing. `add_market_cap` in
  `wrds_build.py` attaches the total and flags the largest instead; filter on
  `is_primary_cap` to reproduce the collapse without the two defects.
- `ff3_v2.py` filters `exchcd between 1 and 3` inside the SQL against
  `msenames`, which drops delisting months. The CIZ version does not have this
  problem because it screens on `msf_v2`'s inline columns.
- `ff3_crspCIZ.py` queries `crsp.ccmxpf_linktable`, the older flat link view;
  prefer `crsp.ccmxpf_lnkhist`.

Their book-equity and screen choices are what `CONVENTIONS['drechsler']`
encodes: preferred stock at redemption → liquidation → par, shareholders' equity
from `seq` alone, non-positive book equity dropped, `conditionaltype='RW'` and
`usincflg='Y'`.

## Not shipped here

Deliberately, because both are a download away and neither needs vendoring:

- Open Source Asset Pricing — code at
  [github.com/OpenSourceAP/CrossSection](https://github.com/OpenSourceAP/CrossSection),
  data at [openassetpricing.com](https://www.openassetpricing.com/). The data is
  public and ungated, so the code is rarely needed. It is also GPL-2.0, which
  would conflict with this plugin's MIT license if vendored.
- Ken French's variable definitions —
  [the data library's definitions page](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/variable_definitions.html).
  The sentences that matter are quoted in `CONVENTIONS.md`.

## A note on how these connect

Every script here opens WRDS with `wrds.Connection()`, which is the right idiom
for the notebooks they came from: interactive, exploratory, and the library's
table-browsing helpers are genuinely useful there. It is the WRONG idiom inside a
pipeline — it triggers a Duo push and reloads the library list on every connect.

These files are kept AS PUBLISHED, bylines and all, so that line is left alone.
When you lift code from one of them into a build script, swap the connection for
the SQLAlchemy engine in `../SKILL.md` ("Connecting to WRDS non-interactively")
and leave the SQL as it is.
