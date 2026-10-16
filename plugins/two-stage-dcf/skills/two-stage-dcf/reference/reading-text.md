# Reading the filings against the drivers

The point is not to summarise the company. It is to find, for each driver, what
management has said that bears on it — and what they have said that contradicts
the number you were about to use.

Cite every piece of evidence to its file and where in it. A forecast the user
cannot audit back to a sentence in a filing is a forecast they cannot defend.

## Where to look

| Source | What it is good for |
|---|---|
| 10-K Item 7, MD&A | the company's own account of why last year moved |
| 10-K Item 1A, risk factors | the downside case, written by people with lawyers |
| 10-K Item 1, business | capacity, segments, customer concentration |
| Tax footnote | the NOL balance, the valuation allowance, the cash rate |
| Commitments footnote | contracted capex, leases, purchase obligations |
| Earnings call transcripts | guidance, and what analysts keep asking about |
| Press releases | announcements that post-date the last 10-K |

## Driver by driver

### Sales growth

Look for: explicit revenue guidance; backlog or contracted revenue and how much
of next year it covers; capacity additions and when they come online; pricing
commentary; customer concentration and any contract expiring; end-market
commentary tied to something observable, such as a rig count or a build rate.

Guidance covers one year. Years 2 through 5 are yours to argue, and the argument
is usually a fade from the guided year toward something defensible. Terminal
growth is a perpetual nominal rate — above nominal GDP and the company
eventually becomes the economy.

### EBITDA margin

Look for: cost programmes and their claimed run-rate savings; whether last
year's margin was hit by something management calls non-recurring, and whether
the same thing was non-recurring the year before; operating leverage claims;
input cost exposure; mix shift between higher- and lower-margin segments.

Check what the company's EBITDA excludes. Many exclude stock compensation, which
is a real cost; if yours does, either add it back or say that you did not.

### Sales-to-net-PP&E turnover

Look for: announced capex and what it is meant to buy; utilisation, and whether
the company says it has spare capacity; asset retirements and impairments;
acquisitions that come with assets.

A company running at low utilisation can grow sales without growing PP&E, so the
turnover rises. One at full utilisation cannot, and the turnover is roughly
fixed until it builds.

### Depreciation rate

Look for: stated useful lives and any change to them; the split between
maintenance and growth capex; amortisation of acquired intangibles inside the
depreciation line and when it runs off.

Cross-check against `realized_capex` from the roll-forward. If the implied
depreciation rate and the company's actual capex tell different stories about
the asset base, find out why before forecasting.

### Operating assets and liabilities

These are ratios to the same year's sales, unlike net PP&E above.

Look for: days sales outstanding and days payable, and any commentary on them;
customer payment terms changing; inventory build ahead of a ramp or a wind-down;
factoring or supply-chain finance programmes, which move payables in ways that
reverse.

### Cash tax rate

Look for: the NOL carryforward balance and its expiry; whether there is a
valuation allowance, which is management telling you they do not expect to use
it; the cash taxes actually paid, per the cash flow statement, against the
provision; foreign rate differentials.

The driver is a marginal rate on taxable income, not an effective rate. The
engine derives the effective rate once the carryforward is applied.

### The discount rate

Look for: the cost of debt implied by recent issuances or the disclosed weighted
average rate; the capital structure management says it is targeting, which is
rarely today's.

## Two habits worth keeping

Read the risk factors after you have drafted the assumptions, not before. They
are written to be comprehensive rather than probable, and reading them first
anchors everything downward. Read them as a checklist against a forecast you
have already written.

When the text contradicts the history, say so and pick — do not average. "Five
years of history says 18 percent, management guided to 24, I used 21" is a
number nobody can defend. Decide whose account of the future you believe.
