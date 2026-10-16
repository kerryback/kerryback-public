# The choices that are not common practice

Most of what goes into a CRSP/Compustat panel is settled: which tables to join,
which screens define common stock, that market cap aggregates across share
classes, that accounting data has to be lagged, that deferred taxes are `txditc`
with 0 for missing. None of that needs a citation.

A handful of constructions are not settled. Three reference implementations
specify them and disagree:

| | |
|---|---|
| `french` | Ken French, as documented in the Fama-French data library |
| `drechsler` | the WRDS reference script — what most published replications actually ran |
| `openap` | Open Source Asset Pricing (Chen-Zimmermann) |

The rule: wherever the three are not unanimous, ask. Never pick silently, and
record the answer. `describe_conventions()` prints the choices;
`DIVERGENCES` in `wrds_build.py` is the machine-readable version.

## The four divergences

| Dimension | french | drechsler | openap |
|---|---|---|---|
| Preferred stock | redemption → liquidation → par | redemption → liquidation → par | par → redemption → liquidation |
| Shareholders' equity | `seq` → `ceq+pstk` → `at−lt` | `seq` only | `seq` → `ceq+preferred` → `at−lt` |
| Negative book equity | kept, flagged | dropped | kept, flagged |
| Alignment | calendar (July–June) | calendar (July–June) | monthly, fixed lag on `datadate` |

No convention agrees with both others on everything. French and Drechsler agree
on preferred stock and alignment; French and OpenAP agree on the equity cascade
and on keeping negative book equity.

## What each divergence actually costs

Measured on `comp.funda` (INDL/STD/D/C/USD), 65,635 firm-years over 2012–2018
unless noted.

### Preferred stock — french/drechsler vs openap

A values difference, not a coverage difference. Coverage is identical at 75.4%.

| | |
|---|---|
| Firm-years where the orders pick different values | 3,156 (6.4%) |
| Median difference in book equity, where it differs | 5.8% |
| 90th percentile | 129% |

A minority of firm-years, but where it bites it bites hard — at the 90th
percentile the choice more than doubles book equity. Those are firms whose
preferred stock is large relative to equity, exactly the tail a book-to-market
sort is sensitive to.

### Shareholders' equity cascade — french/openap vs drechsler

Era-dependent, and worth checking against your own sample window before treating
it as a live choice. Count of firm-years the cascade recovers that `seq`-only
would lose:

| Window | `seq` missing | Recovered by the cascade |
|---|---|---|
| 1965–1975 | 6,158 | 3,474 |
| 1985–1995 | 14,952 | 8 |
| 2012–2018 | 16,176 | 0 |

In modern Compustat the cascade never fires: when `seq` is missing, `ceq`, `at`
and `lt` are missing too, so those firm-years are empty records rather than
records with a usable fallback. In early Compustat it recovers more than half of
them. So this dimension matters for a long sample starting before about 1980 and
not at all for a recent one.

### Negative book equity — french/openap vs drechsler

Drechsler sets book equity missing where it is not positive: 7,485 firm-years,
11.4% of those with computable book equity. In modern data this is the *entire*
French-vs-Drechsler difference — where both produce a value, the values are
identical.

The effect is to remove distressed firms from the sample rather than flag them.
That is defensible for a book-to-market sort, where negative book-to-market is
uninterpretable, and less defensible if the sample is used for anything else.
`french` and `openap` keep the value and expose `be_positive` so the caller
screens deliberately.

### Alignment — french/drechsler vs openap

| | Rule | Book-to-market denominator |
|---|---|---|
| calendar | fiscal year ending in calendar t−1 used from July of t through June of t+1 | December t−1 market cap |
| monthly | fixed reporting lag on `datadate` | market cap lagged to `datadate` |

Calendar alignment is what reproduces published Fama-French factor sorts; the
monthly panel is what you want for a monthly characteristic panel. Neither is
more correct.

On a finished monthly panel, 2010–2011, 105,148 permno-months with an identical
CRSP universe under both:

| | calendar | monthly, 6mo | monthly, 4mo |
|---|---|---|---|
| Book-to-market coverage | 89.0% | 92.1% | 92.3% |
| Median book-to-market | 0.6959 | 0.6118 | 0.6190 |

Book equity differs on 25.4% of months with a median gap of 12.6%, and
book-to-market differs on essentially every month that has one, because the
denominators are different objects. The median book-to-market of the whole
cross-section moves about 14%. Any value sort inherits that.

Calendar's lower coverage is not a defect — it requires a December market-cap
observation, which a mid-year listing does not have.

Two traps in the calendar version, both of which yield a plausible wrong number
rather than an error: the fiscal year ending in calendar t−1 maps to `ffyear` t
(Compustat join key `datadate.year + 1`), and the December cap is December of
t−1, not t (CRSP join key also `+1`). Using December of t leaks eight months of
future prices. The asymmetry that is *not* a trap: book-to-market uses December
t−1 cap while the size sort uses June t cap.

## The reporting lag — a separate choice

Applies only under `monthly` alignment; the calendar conventions supply their own
lag through the June/December structure.

| | Source | Trade-off |
|---|---|---|
| 4 months | Hou-Xue-Zhang (2015) | signal enters two months sooner; tighter timing, more exposure if a filing was late |
| 6 months | conservative standard | the fiscal year is comfortably public |

On a 2016–2018 monthly panel: 4 months gives 95.84% book-equity coverage against
95.68% at 6 months, and the median age of the attached fiscal year drops from
307 days to 246. The coverage difference is negligible; the 61 days of fresher
data bought with 61 days of extra look-ahead exposure is the whole point.

Worth knowing: `comp.fundq.rdq` is the actual report date, so an rdq-based lag is
tighter than any fixed rule. It is only reliably populated from the early 1970s,
which is why fixed lags survive.

## In the code

```python
CONVENTIONS['french'] | CONVENTIONS['drechsler'] | CONVENTIONS['openap']
DIVERGENCES           # dimension -> what each convention does
LAG_CHOICES           # {4: ..., 6: ...}

build_monthly_panel(convention, lag_months=None, ...)
describe_conventions()
```

`convention` has no default — a default is how a decision gets made silently.
Passing `lag_months` under a calendar convention raises rather than being
ignored. Both are stamped on the returned frame's `.attrs`.

One behavior deliberately not offered as a convention: Drechsler's script
collapses the permco market-cap aggregation onto the largest-cap permno via an
inner merge on the cap value, which duplicates rows when two classes tie and
drops permcos whose caps are all missing. `add_market_cap` attaches the permco
total to every row and flags the largest with `is_primary_cap`, so filtering on
that flag reproduces the collapse without the two defects.
