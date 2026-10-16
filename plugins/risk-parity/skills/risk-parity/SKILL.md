---
name: risk-parity
description: >-
  Compute the risk parity (equal risk contribution) portfolio, and the covariance
  matrix it needs, from a file of historical returns or prices. Use whenever the
  user asks for risk parity, equal risk contribution, ERC, risk budgeting, or
  "weights where every asset contributes the same risk"; whenever they ask what
  each holding contributes to portfolio risk or variance; and whenever they want
  a covariance matrix estimated from a return history. Also use for inverse
  volatility weights, and to check whether a set of weights actually equalises
  risk contributions. Triggers on "build a risk parity portfolio", "equal risk
  contribution weights", "risk budget these assets", "what share of the risk does
  each position carry", "estimate the covariance matrix from these returns".
---

# Risk Parity

The risk parity portfolio is the long-only portfolio in which every asset
supplies the same share of portfolio variance. It needs the covariance matrix and
nothing else — no expected returns, which are the input nobody can estimate well.

`risk_parity.py`, in this skill's directory, does both halves: the covariance
matrix from a return history, and the weights from the covariance matrix.

## Run it

```
python3 <skill-dir>/risk_parity.py returns.csv
python3 <skill-dir>/risk_parity.py prices.csv --prices
python3 <skill-dir>/risk_parity.py covariance.csv --cov
```

Add `--out-dir DIR` to write `covariance.csv` and `weights.csv`. Add
`--periods-per-year N` to override the frequency, which is otherwise inferred
from the spacing of the dates (252, 52, 12, 4 or 1).

It needs numpy and pandas. Nothing else — the solver is in the script.

## The input file

Returns or prices: dates in the first column, one column per asset, a header row
of asset names.

```
date,NoDur,Durbl,Manuf
2016-09-16,-0.0071,0.0042,-0.0018
2016-09-23,0.0123,0.0208,0.0155
```

A covariance matrix (`--cov`): a square table whose row labels match its column
labels, already annualised. This is what `--out-dir` writes, so a matrix
produced once can be fed back in.

## What comes back

One row per asset: its weight, its share of portfolio variance, its own
volatility, and for comparison the inverse-volatility weight. Then the portfolio
volatility, and how nearly equal the risk shares came out.

Read the risk share column first. Every entry should be 1/n. If it is not, the
solve did not converge and the weights are not risk parity.

## How it solves

Cyclical coordinate descent on the log-barrier form:

    minimise  (1/2) w' S w  -  (1/n) sum of log w_i     over w > 0

then rescale to sum to one. The log term holds every weight strictly positive, so
long-only never has to be imposed as a constraint, and the objective is strictly
convex, so the answer is unique. Each coordinate update is the positive root of a
quadratic, so there is no line search and no solver dependency.

Other methods reach the same weights — least squares on the deviations between
risk contributions, Newton on the first-order conditions, or a general solver on
the constrained problem. They differ in speed and in what they guarantee, not in
the answer.

## Things worth saying to the user

- Inverse volatility (`1/sigma_i`, also reported) equals risk parity only when
  every pair of assets has the same correlation. With exactly two assets it is
  always exactly right, whatever the correlation.
- Risk parity is not on the mean-variance frontier except by coincidence. It is
  a rule for when you decline to forecast returns, not a claim to be optimal.
- The covariance matrix is estimated, and a longer window buys precision at the
  cost of relevance. Say which window was used.
- Weights change only when the covariance matrix changes, so turnover is low
  compared with rules that use expected returns.

## Extending it

Import the pieces rather than rewriting them:

```python
from risk_parity import covariance_matrix, risk_parity_weights, risk_shares

cov = covariance_matrix(returns, 52)       # annualised
w = risk_parity_weights(cov)
shares = risk_shares(cov, w)               # each should be 1/n
```

For a backtest, call `risk_parity_weights` on each estimation window and hold the
weights until the next rebalance.
