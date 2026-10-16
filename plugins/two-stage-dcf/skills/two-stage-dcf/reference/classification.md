# Classifying the balance sheet

Every reported line goes in exactly one bucket. The buckets are not a filing
convention; they are the question "does this line consume cash as the business
grows, or is it a claim on what the business produces?"

| Bucket | What it means | Where it shows up |
|---|---|---|
| `net_ppe` | the productive asset base | driven by the sales-to-PP&E turnover |
| `operating_asset` | grows with sales, consumes cash | a ratio to that year's sales, in NWC |
| `operating_liability` | grows with sales, supplies cash | a ratio to that year's sales, in NWC |
| `nonoperating_asset` | not needed to run the business | added in the bridge at book |
| `debt_claim` | a claim that must be paid before equity | subtracted in the bridge |
| `equity_claim` | someone else's slice of the equity | subtracted in the bridge |
| `excluded` | no cash-flow effect and no bridge effect | nowhere |

`excluded` is a bucket. Use it rather than leaving a line out of the table —
`check_footing` refuses an incomplete table precisely because a silently dropped
line is how a real liability goes missing from a valuation.

## The cases that are actually hard

Each of these has a default and a reason. The default is a starting point for
the conversation, not an answer. Say which one you took and why.

### Operating lease liabilities and right-of-use assets

Default: the liability is a `debt_claim` and the right-of-use asset is
`excluded`.

Since ASC 842 the lease liability is a disclosed, discounted obligation that
behaves like debt, and EBITDA is struck after the operating lease expense has
been removed to depreciation and interest — or not, depending on the company's
presentation. Check which. If EBITDA in your forecast is *after* rent expense,
the lease obligation is already paid for in the cash flows and adding the
liability to the bridge double-counts it; classify the liability `excluded`
instead. Getting this backwards is the single most common error in this table.

The right-of-use asset is excluded rather than operating because its growth is
mechanically tied to the liability, not to sales.

### Goodwill and acquired intangibles

Default: `excluded`.

The cash flows those acquisitions generate are already in revenue and EBITDA.
Adding the carrying amount to the bridge counts the same thing twice. Holding
them as an `operating_asset` growing with sales is worse — it makes the model
pay cash for goodwill every year.

Amortisation of acquired intangibles is a separate question: if it is inside the
depreciation line you are forecasting, the depreciation rate will drift as the
intangibles run off. Say so.

### Deferred tax assets and liabilities

Default: `excluded`.

The model computes cash taxes directly from EBIT and an NOL balance, so the
deferred accounts are describing the same timing differences a second time.
Where a deferred tax asset is substantially an NOL carryforward, do not put it
in the bridge — put the underlying carryforward in `base.nol` and let the engine
value the shield.

A company with a full valuation allowance is telling you it does not expect to
use its carryforward. Take that seriously before assuming a shield.

### Tax receivable agreements

Default: `debt_claim`.

An Up-C TRA is a contractual obligation to pay cash to pre-IPO holders, and the
cash goes out before common shareholders see anything. It is debt with an
unusual coupon. Note that its carrying amount is an estimate that moves with
expected future taxable income, so it is softer than a bond.

### Related-party receivables and payables

Default: classify them like their arm's-length equivalents — related-party
receivables as `operating_asset`, related-party payables as
`operating_liability`.

Look at whether they are trade balances or financing. A related-party payable
that is really a loan from the sponsor is a `debt_claim`. The statement rarely
says; the notes usually do.

### Noncontrolling interests and mezzanine

Default: `equity_claim`.

Enterprise value is the value of the whole enterprise, including the part of
consolidated subsidiaries someone else owns, because consolidated sales and
EBITDA include all of it. Book value is a poor proxy for what that slice is
worth, and it is the number you have. Say that it is a proxy.

Redeemable preferred in mezzanine is an `equity_claim` at its redemption value
where that is disclosed, not its carrying amount.

### Investments in and income from affiliates

Default: the investment is a `nonoperating_asset` at book.

Equity-method income is not in EBITDA, so the affiliate contributes nothing to
the forecast cash flows and its value has to enter through the bridge. If the
affiliate is material, book value is probably wrong and a separate valuation is
the honest answer.

### Cash

Default: `nonoperating_asset`.

The defensible refinement is to split out operating cash the business needs to
function and treat that as an `operating_asset`. Most companies do not disclose
enough to do it credibly. If you split it, say what you assumed.

### Assets held for sale, restructuring reserves, litigation accruals

Default: held-for-sale assets are `nonoperating_asset`; the reserves are
`debt_claim` if they are a settled obligation with a known amount, `excluded` if
they are an estimate of something that may not happen.

These do not scale with sales, so they must never be `operating_asset` or
`operating_liability` — putting them there makes the model buy more litigation
every year the company grows.

## Footing

```python
from dcf_history import check_footing
check_footing(classification, balance_lines, reported_total)
```

Raises on a line classified twice, a line classified that is not on the
statement, an unclassified line (naming it and what it is worth), or buckets
that do not add back to the reported total.
