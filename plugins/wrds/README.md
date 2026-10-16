# wrds

A data plugin for building empirical asset-pricing samples from WRDS
(CRSP/Compustat) and Open Source Asset Pricing (Chen-Zimmermann).

It is the domain layer that orchestration plugins (e.g. `coauthor`) stay free of:
coauthor is domain-agnostic and delegates all data-source specifics here. Use this
skill whenever a task pulls or constructs market/accounting data from WRDS.

## What it covers (`skills/wrds/SKILL.md`)

- Connecting to WRDS non-interactively — SQLAlchemy over psycopg2, letting libpq
  read `~/.pgpass`. This avoids the Duo push that `wrds.Connection()` triggers and
  the "Loading library list" step it runs on every connect, so unattended builds
  neither hang nor wait on a phone. Resolve the username at runtime
  (`$WRDS_USER` → `~/.wrds` → `~/.pgpass` field 4); resolver at
  `skills/wrds/wrds_username.py`. The `wrds` package is still what creates
  `~/.pgpass` and is still the nicer way to browse tables while exploring.
- Installing the `wrds` package without letting it downgrade pandas.
- CRSP v2 table conventions (`crsp.msf_v2`) and common-stock screens.
- Why the screens must read `msf_v2`'s inline columns rather than a join to
  `stksecurityinfohist`, whose validity window deletes ~89% of delisting months.
- Computing market cap correctly across share classes — aggregate `mthcap` by
  `permco` so dual-class firms carry their whole equity value (a construction bug
  that a shared panel hides from estimator-convergence checks).
- Putting every choice where the three reference conventions (Ken French,
  Drechsler's WRDS script, OpenAP) disagree to the user instead of picking:
  preferred-stock valuation, the equity cascade, whether negative book equity is
  dropped, alignment, and the 4- vs 6-month reporting lag.
- The CRSP-Compustat link (`ccmxpf_lnkhist`), Compustat filters, and the two
  distinct "firm age" variables.
- Field standards that get papers rejected: look-ahead, delisting, survivorship,
  microcaps (value- vs equal-weighted), overlapping-return standard errors,
  multiple testing.
- OpenAP object conventions (char panel vs `PredictorPortsFull`, signed-vs-raw) and
  a red-team checklist.

## The code (`skills/wrds/wrds_build.py`)

A library of numbered sections — §1 connection, §2 CRSP monthly (v2), §3 market
cap with permco aggregation, §4 Compustat annual with book equity, §5 the CCM
link, §6 accounting-to-month merges, §7 firm age, §8 a worked orchestrator. Copy
the sections a project needs into that project's own build script; don't import
it. No SAS step anywhere — every pull is `wrds.raw_sql`, and every query has been
run against live WRDS.

CRSP v2 / CIZ only. `mthret` is already delisting-adjusted, which removes the
missing-`dlret` imputation that older code resolved three different ways.

### The choices the skill must put to the user

Most of a CRSP/Compustat build is settled practice. A few constructions are not,
and three reference implementations disagree — `french` (the Fama-French data
library), `drechsler` (the WRDS reference script, what most published
replications ran), and `openap` (Chen-Zimmermann). Wherever the three are not
unanimous, the skill asks rather than picking.

| Dimension | french | drechsler | openap |
|---|---|---|---|
| Preferred stock | redemption → liquidation → par | same as french | par → redemption → liquidation |
| Shareholders' equity | `seq` → `ceq+pstk` → `at−lt` | `seq` only | ~same as french |
| Negative book equity | kept, flagged | dropped | kept, flagged |
| Alignment | calendar (July–June) | same as french | monthly, fixed lag on `datadate` |
| Reporting lag | n/a | n/a | 4 months (Hou-Xue-Zhang) or 6 (conservative) |

No convention agrees with both others on everything. Measured impact — the
preferred-stock order changes book equity on 6.4% of firm-years (90th percentile
gap 129%), dropping non-positive book equity costs 11.4%, and alignment moves the
median book-to-market of the whole cross-section about 14%. The equity cascade
turns out to be era-dependent: it recovers 3,474 firm-years over 1965–1975 and
none over 2012–2018.

`build_monthly_panel(convention, lag_months=...)` has no default for
`convention`; passing `lag_months` under a calendar convention raises rather than
being ignored; both are stamped on the frame's `.attrs`. See
[CONVENTIONS.md](skills/wrds/CONVENTIONS.md).

### Bugs the code guards against

- Joining `stksecurityinfohist` for the screens. Its validity window closes on
  the delisting date while the return row is dated month end, so screening on
  the joined columns drops the month whose return is the delisting return — 222
  of 2,004 delistings kept for 2000–2001, against 1,815 reading `msf_v2`'s own
  inline columns. Survivorship bias with a known sign, and silent in v2.
- Market cap not aggregated across share classes. Alphabet is $703.9bn on one
  permno and $1,414bn across its permco; Berkshire $303.4bn versus $745.4bn.
- Cumulative variables built from the analysis window rather than full history,
  which makes every firm look newly born.
- Accounting merges that drop CRSP months with no gvkey, turning "unmatched to
  Compustat" into an unwritten survivorship screen. The row count is asserted.
- In the Fama-French path, using December of year t rather than t−1 for the
  book-to-market denominator, which leaks eight months of future prices.

## Shipped reference scripts (`skills/wrds/reference/`)

Twelve WRDS research scripts — Fama-French 3 factors on both CRSP vintages, the
CRSP-IBES link, PEAD, DGTW benchmarks, momentum, size portfolios, S&P 500
constituents, an event study, and three 13F scripts. Converted from their
original notebooks to plain `.py`: source cells only, so no CRSP or Compustat
values are reproduced. Author bylines intact; mostly Qingyi (Freda) Song
Drechsler, Research Director at WRDS, several also published on
[fredasongdrechsler.com](https://www.fredasongdrechsler.com/data-crunching).

They are a reference, not a dependency — `wrds_build.py` does not import them.
`reference/README.md` indexes what each builds, when to consult it, and their
known defects. Reading `ff3_crspCIZ.py` is what established that CRSP v2 screens
should read `msf_v2`'s inline columns rather than joining `stksecurityinfohist`.

Not shipped, because they are public and fetchable on demand: Open Source Asset
Pricing (data ungated at openassetpricing.com; code is GPL-2.0 and would
conflict with this plugin's MIT license) and Ken French's variable definitions.
The WRDS data dictionary is login-gated and so cannot be fetched mid-task — a
greppable copy would be worth shipping and is not present yet.

## Requirements

- WRDS access: `~/.pgpass` with a wrds line, a resolvable WRDS username, and
  `sqlalchemy` + `psycopg2` for pulls. The `wrds` package is optional once
  `~/.pgpass` exists — keep it for `create_pgpass_file()` and for browsing.
- OpenAP data is public (download directly).
