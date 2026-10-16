---
name: wrds
description: Build empirical asset-pricing samples from WRDS (CRSP v2/Compustat) and Open Source Asset Pricing, with vetted Python building blocks in wrds_build.py. Use whenever a task pulls or constructs market/accounting data from WRDS — connecting non-interactively, installing the wrds package without breaking pandas, CRSP v2/CIZ table conventions, the window-join trap that silently deletes delisting months, market cap across share classes (permco), the CRSP-Compustat link, firm age, and the field-level standards (delisting, survivorship, microcaps, overlapping-return standard errors) and pitfalls (OpenAP signed-vs-raw, char-panel vs. portfolio-returns) that get asset-pricing papers rejected. Always puts the choices to the user rather than picking silently: wherever the three reference conventions (Ken French, Drechsler's WRDS script, OpenAP) disagree — preferred-stock valuation, the shareholders'-equity cascade, whether negative book equity is dropped, and accounting-to-month alignment — plus the 4- vs 6-month reporting lag.
---

# wrds — building asset-pricing data from WRDS and OpenAP

This skill is the domain guidance for pulling and constructing empirical
asset-pricing data. It pairs with any orchestration that asks for a sample (e.g.
the coauthor plugin, whose Analyst and Replicator each build the sample
independently and reconcile it before analysis). Keep every pull re-runnable and
standalone, and state exactly which sources, objects, and vintages you used.

## Start from `wrds_build.py` — do not write a pull from scratch
`wrds_build.py` is a library of numbered SECTIONS covering connect, pull, merge,
and standard variable construction. Every query in it has been run against live
WRDS. Work with it like this:

1. Read the section index at the top and pick the minimum set the task needs. A
   momentum sort needs §1-§3 and stops there.
2. COPY those sections into the project's own build script. Do not import the
   module — the project's script must be standalone and re-runnable years later
   without this plugin on the path.
3. Keep the comment blocks on the sections you take. They record which
   convention was picked and why, which is most of a data appendix.

`build_monthly_panel()` in §8 is a worked example showing how the sections
compose. Read it; do not call it from a project.

## For a query this skill doesn't already cover
Discover structure live before guessing — it is free, current, and needs no
shipped documentation:
```python
conn.list_libraries()                    # crsp, comp, ibes, tfn, ...
conn.list_tables(library='comp')         # funda, fundq, company, secm, ...
conn.describe_table('crsp', 'msf_v2')    # column names, types, row count
```
`describe_table` is how you confirm a column exists and what it is called before
writing SQL against it — it is what established that `msf_v2` carries `siccd`
and `ticker` inline. Cheap; use it freely.

What introspection does NOT give is what a column MEANS. The WRDS data
dictionary is behind the `wrds-www` login, so it cannot be fetched mid-task. If
a variable's meaning is load-bearing and not obvious, say so and ask the user to
paste the definition rather than inferring it from the name — `ajex`, `epsfxq`
vs `epspxq`, and the `dlstcd` code ranges are all cases where a plausible guess
is wrong. (A shipped, greppable dictionary would close this; not present yet.)

Then check `reference/` — twelve WRDS scripts covering CRSP, Compustat, IBES,
13F and event studies, which between them touch most of the tables a new
question will need.

Two sources deliberately not shipped, because unlike the WRDS dictionary they
are public and can be fetched when needed:
- Open Source Asset Pricing — data at openassetpricing.com (public, ungated),
  code at github.com/OpenSourceAP/CrossSection (GPL-2.0, so do not vendor it).
- Ken French's variable definitions — the data library's definitions page. The
  load-bearing sentences are quoted in `CONVENTIONS.md`.

## The WRDS reference scripts in `reference/`
Twelve WRDS research scripts (Drechsler et al.), converted to plain `.py`. They
are a REFERENCE, not a dependency — `wrds_build.py` does not import them. Read
`reference/README.md` for the index of what each builds and when to consult it.

Reach for them when a construction is in doubt, and especially:
- `ff3_crspCIZ.py` for anything touching CRSP v2 screens, book equity, the
  June/December calendar, or NYSE breakpoints. This is the file that established
  that v2 screens read `msf_v2`'s inline columns rather than joining
  `stksecurityinfohist`.
- `iclink_v2.py` before any IBES work — it is the CRSP-IBES link methodology.
- `pead_v4.py` for earnings surprise and announcement-window returns.

Read them critically. `reference/README.md` lists their known defects — missing
returns filled with zero, a permco collapse that duplicates on ties, and in the
legacy version an exchange screen inside the SQL that drops delisting months.
Their choices are what `CONVENTIONS['drechsler']` encodes.

## ALWAYS ask the user when the three conventions disagree
Most of this is settled practice and needs no discussion. A few constructions
are not, and three reference implementations disagree on them:

- `french` — Ken French, as documented in the Fama-French data library
- `drechsler` — the WRDS reference script, what most published replications ran
- `openap` — Open Source Asset Pricing (Chen-Zimmermann)

The rule: wherever these three are NOT unanimous, ask the person building the
sample. Never pick silently, and record the answer. Call
`describe_conventions()` to print the choices, or read `DIVERGENCES` in
`wrds_build.py`. `CONVENTIONS.md` has the measured impact of each.

| Dimension | french | drechsler | openap |
|---|---|---|---|
| Preferred stock | redemption → liquidation → par | same as french | par → redemption → liquidation |
| Shareholders' equity | `seq` → `ceq+pstk` → `at−lt` | `seq` only | ~same as french |
| Negative book equity | kept, flagged | dropped | kept, flagged |
| Alignment | calendar (July–June) | same as french | monthly, fixed lag |

Nobody agrees with everyone. What each costs, measured:

- Preferred stock order changes book equity on 6.4% of firm-years; where it
  differs the median gap is 5.8% and the 90th percentile is 129%.
- The equity cascade is era-dependent — it recovers 3,474 firm-years over
  1965-1975, 8 over 1985-1995, and 0 over 2012-2018 (in modern data, when `seq`
  is missing `ceq`/`at`/`lt` are missing too). Only a live choice for long
  samples starting before ~1980.
- Dropping non-positive book equity removes 11.4% of firm-years, and in modern
  data is the ENTIRE french/drechsler difference — where both produce a value,
  the values are identical.
- Alignment moves the median book-to-market of the whole cross-section ~14%
  (0.6959 calendar vs 0.6118 monthly), and changes book-to-market on
  essentially every month, because the denominators are different objects.

Separately, under `openap` (monthly) alignment only, the reporting lag:
4 months (Hou-Xue-Zhang) or 6 months (conservative). The calendar conventions
supply their own lag through the June/December structure, so passing
`lag_months` with them raises rather than being ignored.

`build_monthly_panel(convention, lag_months=...)` takes no default for
`convention`. Both choices are stamped on the returned frame's `.attrs`. State
them in the paper.

## Connecting to WRDS non-interactively (or an unattended run HANGS or 2FAs)
For any SCRIPTED pull, connect with SQLAlchemy over psycopg2 and let libpq read
`~/.pgpass`. Do NOT use `wrds.Connection()` in a pipeline.

```python
from sqlalchemy import create_engine
import pandas as pd
# (paste the wrds_username() resolver from wrds_username.py here)
eng = create_engine(
    f"postgresql+psycopg2://{wrds_username()}@wrds-pgdata.wharton.upenn.edu:9737/wrds",
    connect_args={"sslmode": "require", "connect_timeout": 45})
df = pd.read_sql("select gvkey, conm from comp.company limit 3", eng)
```

No password appears in the code: libpq finds `~/.pgpass` by itself from the host,
port, database and user in the URL. Still resolve the username rather than
hardcoding it — same rule as before, `$WRDS_USER` → `~/.wrds` → `~/.pgpass`
field 4 — so the script works for anyone.

WHY THIS AND NOT `wrds.Connection()`. Three reasons, all measured:
- **2FA.** The wrds library's own connection path triggers a Duo push. The
  libpq/`.pgpass` route does not — it authenticates straight through. An
  unattended run that fires a Duo prompt at 3am is a failed run.
- **Speed.** `wrds.Connection()` runs a "Loading library list" step on EVERY
  connect. The engine above is ready in about a second.
- **It is a real SQLAlchemy engine**, so `pandas.read_sql` takes it without the
  "not a valid connection" warning you get from a bare DBAPI connection.

WHAT THE `wrds` LIBRARY IS STILL FOR. It is not redundant — it is just the wrong
tool inside a pipeline:
- **Creating `~/.pgpass` in the first place.** `wrds.Connection().create_pgpass_file()`
  is the bootstrap, and that one-time step is where the 2FA approval belongs.
  Everything above assumes the file already exists.
- **Discovery while you are still exploring**: `list_libraries()`, `list_tables()`,
  `describe_table()`. `list_libraries()` in particular reflects what your account
  can actually reach, not merely what exists.
- **`get_table()`** for a quick look without writing SQL.

The discovery calls have plain-SQL equivalents when you want them in a script:
```sql
-- columns of a table (describe_table)
select column_name, data_type from information_schema.columns
 where table_schema='crsp' and table_name='msf_v2' order by ordinal_position;
-- what is in a library (list_tables)
select table_name from information_schema.tables where table_schema='crsp';
```
Rule of thumb: explore in a notebook with the `wrds` package, then pull with the
engine. If you keep the package only for `create_pgpass_file`, that is fine and
is a good reason not to uninstall it.

## Installing wrds — do NOT let it downgrade pandas
The `wrds` package pins an OLD pandas in its metadata; installed normally it
uninstalls your current pandas and drops to that old version, which breaks numpy /
statsmodels / much else. wrds runs fine on current pandas, so never accept the
downgrade. Pick one approach:
- Clean install (preferred): install wrds alone, touching nothing else —
  `<interp> -m pip install --no-deps wrds` — then, only if `import wrds` reports a
  genuinely missing module (e.g. `psycopg2`, `sqlalchemy`, `mock`), install just
  that one package. NEVER reinstall/downgrade pandas.
- Snapshot + restore: `<interp> -m pip freeze > /tmp/env-before.txt` BEFORE
  installing wrds; `pip install wrds`; then restore the downgraded packages
  (`<interp> -m pip install -r /tmp/env-before.txt`). Ignore pip's "wrds requires
  pandas==X" conflict warnings — harmless here.
Verify: `<interp> -c "import wrds, pandas; print(pandas.__version__)"` — pandas
should be your CURRENT version and wrds should import.

## CRSP: v2 only
Use the CRSP v2 monthly file `crsp.msf_v2` (`permno, permco, mthcaldt, yyyymm,
mthcap, mthret, mthprc, shrout, mthretflg, mthdelflg`) joined to
`crsp.stksecurityinfohist`. Common-stock screens: `sharetype='NS'`,
`securitytype='EQTY'`, `securitysubtype='COM'`, `issuertype in ('CORP','ACOR')`,
`primaryexch in ('N','A','Q')`, `conditionaltype in ('RW','NW')`,
`tradingstatusflg='A'`.

`mthret` is ALREADY delisting-adjusted — do NOT merge `crsp.msedelist` on top of
it, that double counts. Delisting months are visible via `mthretflg` ('DE') and
`mthdelflg`. This is the main reason to be on v2: it removes the missing-`dlret`
imputation entirely, which older code resolved variously as -0.30, -0.35/-0.55,
or not at all, with results that moved accordingly. Do not fall back to the v1
tables (`crsp.msf` + `crsp.msenames`) — the two vintages also disagree slightly
on dividend-month returns, so mixing them in one panel is a further error.

### Do NOT join `stksecurityinfohist` for the screens
`crsp.msf_v2` carries the screen columns inline — `sharetype`, `securitytype`,
`securitysubtype`, `issuertype`, `primaryexch`, `conditionaltype`,
`tradingstatusflg`, `usincflg`, `siccd`, `ticker` are all columns on `msf_v2`.
Screen on those.

Joining `crsp.stksecurityinfohist` over its validity window
(`secinfostartdt <= mthcaldt <= secinfoenddt`) looks natural and introduces a
survivorship bug. The window closes on the DELISTING DATE while the return row
is dated MONTH END, so for a stock that stops trading mid-month the join returns
NULL for every screen column in the one month whose return IS the delisting
return — and screening then drops it.

Measured on 2000-2001 against the 2,004 delistings in `crsp.msedelist`:

| Approach | Delistings kept | For-cause |
|---|---|---|
| `msf_v2` inline columns | 1,815 | 710 |
| left join + forward-fill identifiers | 1,588 | 549 |
| inner join on the window, then screen | 222 | 49 |

Permno 10039, delisted 2001-06-26: its `stksecurityinfohist` record runs to
06-26 and the next covers only 06-27, while the `msf_v2` return row is dated
06-29 — outside both. Read inline, that row reports NS/EQTY/COM/CORP/Q/RW/A and
`mthret = -0.923077` flagged 'DE'.

Join `stksecurityinfohist` only for its historical industry code, as a LEFT join
no screen depends on.

## Market cap done right — aggregate across share classes (permco)
CRSP `mthcap` is per-PERMNO — one share CLASS. A company with multiple share
classes (dual-class firms: Alphabet's GOOGL+GOOG, Berkshire's BRK.A+BRK.B, Fox,
News Corp, …) has several permnos under ONE `permco`, and the CRSP-Compustat link
maps a gvkey to a single (primary) permno. If you take that permno's `mthcap` as
the firm's market cap, you get only one class and understate the company — often by
roughly half. This silently corrupts market cap and everything derived from it
(enterprise value, size, book-to-market, breakpoints, value-weighting).

The fix: a company's market cap = the SUM of `mthcap` over all permnos sharing its
`permco` in that month; FLAG the largest-cap permno as the representative rather
than collapsing to it. Pull `permco` in the msf query, aggregate per
`(permco, month)`, and attach the permco-total to the gvkey. Apply it consistently
to the current cap, any LAGGED cap used for matching/sorting, AND to NYSE
breakpoints (compute breakpoints on permco-aggregated caps too). This is exactly
the kind of construction bug that two estimators reading one shared panel both
inherit and never catch — so it belongs in the independent data build and the
build-reconciliation check. `wrds_build.py` §3.

Verified live for June 2023: Alphabet (permco 45483) is $703.9bn on permno 14542
and $710.3bn on 90319 — $1,414bn together. Berkshire (permco 540) is $303.4bn +
$441.9bn = $745.4bn. Half the firm, in both cases, if you take the linked permno
alone. Flag rather than collapse: collapsing via an inner merge on the max cap
value duplicates rows on a tie and drops permcos whose caps are all missing.

Two more ways to left-censor a panel by accident, both worth checking every time:
- Build cumulative variables (firm age, lagged cap, most-recent fiscal year) from
  the FULL history, then subset to the analysis window. Pulling CRSP or Compustat
  only for the analysis window makes every firm look newly born — a panel starting
  in 2010 whose firms are all "1 year old" is this bug.
- Merging accounting data must not drop CRSP months with no gvkey. Those stocks
  still have returns and market caps; dropping them turns "unmatched to
  Compustat" into an unwritten survivorship screen. Assert the row count is
  unchanged across the merge.

## The CRSP-Compustat link
Use `crsp.ccmxpf_lnkhist` (`gvkey, lpermno as permno, linktype, linkprim, linkdt,
linkenddt`), keep `linktype in ('LC','LU')` and `linkprim in ('P','C')`, and respect
the date validity window (`linkdt`/`linkenddt`). Note the link is gvkey↔permno; the
permco-aggregation above is what carries a firm's full equity value across its
classes. `crsp.ccmxpf_linktable` is the older flat view — prefer `lnkhist`.
Fill a NULL `linkenddt` with a fixed far-future date, not with today's date, or the
same script run on two days produces two different panels.

## Compustat
- `indfmt='INDL'`, `datafmt='STD'`, `consol='C'`, `popsrc='D'` — consolidated,
  standardized, industrial-format domestic statements.
- `curcd='USD'` — `comp.funda` carries Canadian filers reporting in CAD, which
  would otherwise be mixed with CRSP's USD market equity.
- Book equity and accounting-to-month alignment are the French/OpenAP choice
  above. Do not pick one for the user.
- Deferred taxes are `txditc`, 0 when missing, under both conventions. A
  `txdb + itcb` reconstruction is common elsewhere and recovers firm-years where
  `txditc` is unpopulated, but it is neither French nor OpenAP — if a project
  wants it, that is a third choice to state explicitly.
- "Firm age" names two different variables: annual Compustat record count and
  months in CRSP. Both are row counts, not date differences — a listing gap
  should not credit a firm with age it did not trade through. Report which one,
  under a name that says which.

## Standards (these are what get asset-pricing papers rejected — get them right)
- No look-ahead: signals available at t predict returns at t+1; align timing and
  lags explicitly. Accounting data is public only after a reporting lag.
- Use delisting returns; don't silently drop delisted firms (survivorship).
- Handle microcaps deliberately — report BOTH value- and equal-weighted, and a
  price/size screen; a result that lives only equal-weighted in microcaps is a
  small-firm effect, say so.
- Overlapping returns → Newey-West / correct standard errors.
- Winsorize/trim deliberately and state it; the target/return is usually not
  winsorized.
- If you touch many signals/specs, acknowledge multiple-testing exposure.
- State every sample decision in a short data appendix as you go.

## Open Source Asset Pricing (openassetpricing.com, Chen-Zimmermann)
~200 documented predictor signals with code and portfolio returns, public and
un-gated (download directly). Be explicit about which object you use and its
pitfalls:
- The firm-level characteristic panel vs. `PredictorPortsFull` (portfolio returns) —
  don't confuse the two.
- Signed-vs-raw versions of a signal.
- Don't use a "not predictor" flagged signal as if validated.
- Watch sample/rebalancing alignment against your own return series and vintage.

## Red-team an asset-pricing result (run these explicitly)
- Look-ahead / timing: is the signal genuinely lagged relative to the return?
- Survivorship / delisting: are delisted firms handled? drop them and see if it moves.
- Microcaps: does the effect survive value-weighting and a price/size screen?
- Overlapping returns / t-stat inflation: are the standard errors correct?
- Data-snooping: how many signals/specs were tried to get here?
- Market cap / identifiers: is cap aggregated across share classes (permco)? are
  links and merges keeping the rows you think they are?
- OpenAP pitfalls: signed-vs-raw, char-panel vs. portfolio-returns, sample and
  rebalancing misalignment.
