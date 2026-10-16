# The model, and the bundle schema

## Timing

Year 0 is the last actual fiscal year. Balance-sheet quantities in forecast year
`t` are the balance at the *end* of year `t`.

Working capital is stated against that same year's sales. Net PP&E is the one
exception: it is entered as a turnover on the *following* year's sales,
`S(t+1) / NPPE(t)`, because capacity is built ahead of the sales it supports.
That asymmetry is deliberate — a plant comes on line before the volume does,
whereas receivables and payables arise from the volume itself.

Years 6 and later take the terminal value of every driver. That is what makes
year 6 the transition year and year 7 a clean steady state.

## The recursion

```
  S(t)      = S(t-1) (1 + g(t))
  EBITDA(t) = m(t) S(t)
  NPPE(t)   = S(t+1) / k(t)                       capacity built ahead
  D(t)      = d(t) NPPE(t-1)
  X(t)      = NPPE(t) - NPPE(t-1) + D(t)          capex, the plug
  A(t,i)    = a_i(t) S(t)                         each operating asset
  L(t,j)    = l_j(t) S(t)                         each operating liability
  NWC(t)    = sum_i A(t,i) - sum_j L(t,j)
  EBIT(t)   = EBITDA(t) - D(t)
  FCF(t)    = EBITDA(t) - Tax(t) - X(t) - (NWC(t) - NWC(t-1))
```

`NPPE(0)`, `NWC(0)`, `S(0)` and the opening NOL are actuals, so year 1's capex
and working-capital investment are anchored to the real balance sheet rather
than to a ratio.

Capex is the plug rather than an assumption because in steady state it lands at
`(g + d)` times prior net PP&E, which is positive for any sensible growth rate.
Make depreciation the plug instead and it can go negative on perfectly ordinary
inputs.

## Taxes

Unlevered — computed on EBIT, with the interest shield left in the discount
rate. `tau(t)` is the marginal cash rate on taxable income, not an effective
rate; the effective rate is derived and displayed.

A running federal carryforward, for years 1 through 6:

```
  EBIT(t) <= 0:   Tax(t)  = 0
                  NOL(t)  = NOL(t-1) - EBIT(t)
  EBIT(t) >  0:   used(t) = min( L * EBIT(t), NOL(t-1) )
                  Tax(t)  = tau(t) * (EBIT(t) - used(t))
                  NOL(t)  = NOL(t-1) - used(t)
```

`L` is the post-2017 federal limitation, default 0.80, editable.

## Terminal value

Unless year 5's ratios already equal the terminal ratios, year 6's capex and
working-capital investment carry a one-time level adjustment. Capitalising that
into a perpetuity would be wrong.

Year 6 therefore runs on terminal assumptions and absorbs the transition, and
the perpetuity sits on year 7, whose net PP&E and working capital are both set
by terminal ratios — PP&E on year-7 sales, working capital on year-6 sales:

```
  EV = sum over t = 1..6 of FCF(t) / (1+r)^t
       + [ FCF(7) / (r - g) ] / (1+r)^6
```

Set year 5's ratios equal to the terminal ratios and year 6 is already steady
state, collapsing this to the textbook formula. The user still fills in five
explicit columns plus a terminal column; year 6 is computed.

## The surviving carryforward

The perpetuity is taxed at the full rate with no carryforward usage, because a
perpetuity whose tax rate keeps rising as a balance burns off is not a steady
state. Anything alive after year 6 is valued separately, from `NOL(6)` and
`EBIT(7)` growing at `g`:

```
  for s = 7, 8, ...:
      used(s)   = min( L * EBIT(s), NOL(s-1) )
      PV       += tau_T * used(s) / (1+r)^s
      NOL(s)    = NOL(s-1) - used(s)
  until NOL = 0, or 200 iterations
```

and added to the bridge as its own line. If `EBIT(7)` is not positive the shield
is worth zero and the engine warns, because a company with negative terminal
EBIT has a negative enterprise value and the model is being asked a question it
cannot answer.

## The bridge

```
  Enterprise value of operations
  + PV of remaining NOL carryforward
  + non-operating assets
  - debt claims
  - other equity claims
  = equity value to common
  / diluted shares                = value per share
```

Items classified `excluded` contribute nothing. They are classified only to keep
them out of the sales ratios.

## Valuation date

The end of fiscal year 0. Comparing that to a current market price is comparing
across a gap, and the report says so on its face. There is no mid-year convention.

## The bundle

```json
{
  "meta": {
    "company": "ProFrac Holding Corp.",
    "ticker": "ACDC",
    "fiscal_year_0": 2025,
    "fiscal_year_end": "2025-12-31",
    "units": "USD millions",
    "diluted_shares": 180.9
  },
  "classification": [
    {"line": "Accounts receivable, net", "bucket": "operating_asset",
     "key": "receivables", "note": "Trade receivables; scales with revenue."}
  ],
  "base": {
    "sales": 1941.8,
    "net_ppe": 1234.5,
    "operating_assets": {"receivables": 266.8},
    "operating_liabilities": {"payables": 180.0},
    "nonoperating_assets": {"cash": 22.9},
    "debt_claims": {"long_term_debt": 1185.6},
    "equity_claims": {"noncontrolling_interests": 40.0},
    "nol": 400.0
  },
  "assumptions": {
    "sales_growth":      {"explicit": [0.05, 0.04, 0.03, 0.03, 0.025],
                          "terminal": 0.02,
                          "guidance": "how to choose this driver",
                          "citations": [{"quote": "...", "speaker": "...",
                                         "source": "transcripts/..."}],
                          "rationale": "why the suggestion sits where it does"},
    "ebitda_margin":     {"explicit": [...], "terminal": 0.0, "rationale": "..."},
    "sales_to_net_ppe":  {"explicit": [...], "terminal": 0.0, "rationale": "..."},
    "depreciation_rate": {"explicit": [...], "terminal": 0.0, "rationale": "..."},
    "cash_tax_rate":     {"explicit": [...], "terminal": 0.0, "rationale": "..."},
    "operating_assets":      {"receivables": {"explicit": [...], "terminal": 0.0,
                                              "rationale": "..."}},
    // ratios to the same year's sales; sales_to_net_ppe above is the exception
    "operating_liabilities": {"payables": {"explicit": [...], "terminal": 0.0,
                                           "rationale": "..."}}
  },
  "rates": {
    "wacc": 0.096,
    "wacc_derivation": "CAPM: 4.20 + 1.55 x 5.00 = 11.95 percent. ...",
    "nol_limitation": 0.80
  },
  "history": {"years": [2021, 2022, 2023, 2024, 2025], "ratios": {}}
}
```

Rules the engine enforces, each raising rather than guessing:

- every `explicit` array holds exactly five values
- `base.operating_assets` and `assumptions.operating_assets` name the same keys,
  and likewise for liabilities
- no key appears on both sides of working capital
- `rates.wacc` exceeds `assumptions.sales_growth.terminal`

`guidance`, `citations` and `rationale` are optional and the engine ignores them.
They are what makes the HTML an advisory document rather than a bare answer: the
numbers in `explicit` and `terminal` are suggestions, and these three fields are
what let someone choose differently.

The numbers in `explicit` and `terminal` can be carried in an `assumptions.csv`
instead and overlaid with `dcf_assumptions.apply_assumptions_csv`. That CSV is
the part that changes; everything else in the bundle is settled once. It must
name every row the bundle expects -- a missing row raises rather than silently
keeping the old value.

`history` is carried only so the artifacts can show historical columns beside
the forecast columns. The engine ignores it. Its `ratios` are shaped exactly as
`dcf_history.historical_ratios` returns them.

## What the engine returns

```python
{
  "schedule": [ one dict per year, 1..7 ],
  "ev_ops": float, "pv_explicit": float, "pv_terminal": float,
  "terminal_value": float, "pv_nol": float,
  "bridge": [ {"label": str, "amount": float} ],
  "equity_value": float, "value_per_share": float | None,
  "warnings": [ str ],
}
```

Warnings fire on: a carryforward surviving year 6, a carryforward not exhausted
within the horizon, non-positive terminal EBIT, negative implied capex in any
year, sales reaching zero, a year-5-to-terminal turnover gap above ten percent,
and a units mismatch between the statements and the share count.

## Where the arithmetic lives

Twice: in this module, and in the workbook's Excel formulas. Both HTML pages
render figures the engine already computed and hold no script, so they are not a
third implementation and cannot disagree with the engine.

The workbook's Check sheet holds the engine's base-case figures beside formulas
that resolve to FAIL and turn red when a cell disagrees. Excel evaluates them on
open, so drift announces itself to whoever opens the file.
