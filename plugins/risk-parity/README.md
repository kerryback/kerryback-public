# risk-parity

The risk parity portfolio — long-only weights in which every asset supplies the
same share of portfolio variance — and the covariance matrix it is built from.

It needs the covariance matrix and nothing else. No expected returns, which are
the input that estimates worst.

## Install

```
/plugin marketplace add kerryback/kerryback-public
/plugin install risk-parity@kerryback-public
```

Then ask for a risk parity portfolio, equal risk contribution weights, a risk
budget, or a covariance matrix estimated from a return history.

## Requirements

Python with numpy and pandas. The solver is in the script, so there is no solver
library to install.

## Use it directly

```
python3 risk_parity.py returns.csv
python3 risk_parity.py prices.csv --prices
python3 risk_parity.py covariance.csv --cov --out-dir ./out
```

Dates in the first column, one column per asset. The observation frequency is
inferred from the spacing of the dates; `--periods-per-year` overrides it.

Output is one row per asset — weight, share of portfolio variance, own
volatility, inverse-volatility weight — then the portfolio volatility. Every
risk share should equal 1/n; that is the check that the answer is risk parity.

## Method

Cyclical coordinate descent on

    minimise  (1/2) w' S w  -  (1/n) sum of log w_i     over w > 0,

rescaled to sum to one. The log term keeps every weight strictly positive, so
the long-only constraint is never imposed, and the objective is strictly convex,
so the solution is unique. Each coordinate update is the positive root of a
quadratic.

## What it does not claim

Risk parity is not the maximum-Sharpe portfolio and does not lie on the
mean-variance frontier except by coincidence. It is what you hold when you
decline to forecast returns.

Inverse-volatility weighting, reported for comparison, coincides with risk parity
only when every pair of assets has the same correlation — and always, exactly,
when there are just two assets.
