"""Covariance from historical returns, and the risk parity portfolio.

The risk parity (equal risk contribution) portfolio is the long-only portfolio in
which every asset supplies the same share of portfolio variance. It uses the
covariance matrix and nothing else -- no expected returns.

Solved by cyclical coordinate descent on the log-barrier form
(Griveau-Billion, Richard and Roncalli 2013):

    minimise  (1/2) w' S w  -  (1/n) sum_i log w_i     over w > 0,

then rescale to sum to one. The log term keeps every weight strictly positive, so
the long-only constraint never has to be imposed; the objective is strictly
convex, so the solution is unique. Needs numpy and pandas -- no solver library.

Usage
-----
    python3 risk_parity.py returns.csv
    python3 risk_parity.py prices.csv --prices
    python3 risk_parity.py cov.csv --cov
    python3 risk_parity.py returns.csv --periods-per-year 52 --out-dir ./out

The returns file has dates in the first column and one column per asset. The
--cov form takes a square matrix with matching row and column labels, already
annualised, which is what --out-dir writes.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

PERIODS = {"D": 252, "B": 252, "W": 52, "M": 12, "Q": 4, "A": 1, "Y": 1}


def periods_per_year(index: pd.DatetimeIndex) -> int:
    """Guess observations per year from the median gap between dates."""
    if len(index) < 3:
        raise ValueError("need at least three dates to infer the frequency")
    days = np.median(np.diff(index.values).astype("timedelta64[D]").astype(float))
    for limit, n in ((3, 252), (10, 52), (45, 12), (135, 4), (400, 1)):
        if days <= limit:
            return n
    raise ValueError(f"cannot infer a frequency from a median gap of {days:.0f} days")


def load_table(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def to_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.sort_index().pct_change().dropna(how="all")


def covariance_matrix(returns: pd.DataFrame, per_year: int) -> pd.DataFrame:
    """Annualised sample covariance matrix of the return columns."""
    clean = returns.dropna()
    if len(clean) <= returns.shape[1]:
        raise ValueError(
            f"{len(clean)} complete observations for {returns.shape[1]} assets: "
            "the sample covariance matrix would be singular"
        )
    return clean.cov() * per_year


def risk_parity_weights(cov, tol: float = 1e-12, max_iter: int = 10_000) -> np.ndarray:
    """Long-only weights giving every asset an equal share of portfolio variance."""
    S = np.asarray(cov, dtype=float)
    n = S.shape[0]
    if S.shape[0] != S.shape[1]:
        raise ValueError("the covariance matrix must be square")
    if not np.allclose(S, S.T, atol=1e-10):
        raise ValueError("the covariance matrix must be symmetric")
    var = np.diag(S)
    if (var <= 0).any():
        raise ValueError("every asset needs a positive variance")

    x = 1.0 / np.sqrt(var)          # start from inverse volatility
    x /= x.sum()
    for _ in range(max_iter):
        prev = x.copy()
        for i in range(n):
            # solve S_ii x_i^2 + (sum_{j != i} S_ij x_j) x_i - 1/n = 0 for x_i > 0
            b = S[i] @ x - S[i, i] * x[i]
            x[i] = (-b + np.sqrt(b * b + 4.0 * S[i, i] / n)) / (2.0 * S[i, i])
        if np.max(np.abs(x - prev)) < tol * max(1.0, np.max(x)):
            break
    else:
        raise RuntimeError(f"did not converge in {max_iter} sweeps")
    return x / x.sum()


def risk_shares(cov, weights) -> np.ndarray:
    """Each asset's share of portfolio variance: w_i * Cov(asset i, portfolio) / variance."""
    S, w = np.asarray(cov, dtype=float), np.asarray(weights, dtype=float)
    total = w @ S @ w
    if total <= 0:
        raise ValueError("portfolio variance is not positive")
    return w * (S @ w) / total


def inverse_vol_weights(cov) -> np.ndarray:
    w = 1.0 / np.sqrt(np.diag(np.asarray(cov, dtype=float)))
    return w / w.sum()


def report(cov: pd.DataFrame) -> pd.DataFrame:
    w = risk_parity_weights(cov)
    return pd.DataFrame(
        {
            "weight": w,
            "risk share": risk_shares(cov, w),
            "volatility": np.sqrt(np.diag(cov.values)),
            "inverse vol weight": inverse_vol_weights(cov),
        },
        index=cov.index,
    )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("path", help="CSV of returns, prices, or a covariance matrix")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--prices", action="store_true", help="input holds prices, not returns")
    src.add_argument("--cov", action="store_true", help="input is already a covariance matrix")
    p.add_argument("--periods-per-year", type=int, default=None,
                   help="observations per year (default: inferred from the dates)")
    p.add_argument("--out-dir", default=None, help="write covariance.csv and weights.csv here")
    a = p.parse_args(argv)

    table = load_table(a.path)

    if a.cov:
        cov = table
        cov.index = [str(i).strip() for i in cov.index]
        if list(cov.index) != list(cov.columns):
            raise SystemExit("a covariance matrix needs matching row and column labels")
    else:
        table.index = pd.to_datetime(table.index)
        table = table.sort_index().apply(pd.to_numeric, errors="coerce")
        returns = to_returns(table) if a.prices else table
        per_year = a.periods_per_year or periods_per_year(returns.index)
        cov = covariance_matrix(returns, per_year)
        print(f"{len(returns.dropna())} observations, {per_year} per year, "
              f"{returns.index[0].date()} to {returns.index[-1].date()}")

    out = report(cov)
    vol = float(np.sqrt(out["weight"].values @ cov.values @ out["weight"].values))

    show = out.copy()
    for c in ("weight", "risk share", "volatility", "inverse vol weight"):
        show[c] = (100 * show[c]).map("{:.2f}%".format)
    print()
    print(show.to_string())
    print(f"\nportfolio volatility {100 * vol:.2f}%    "
          f"risk shares equal to within {100 * out['risk share'].std():.2e} points")

    if a.out_dir:
        import os
        os.makedirs(a.out_dir, exist_ok=True)
        cov.to_csv(os.path.join(a.out_dir, "covariance.csv"), index_label="asset")
        out.to_csv(os.path.join(a.out_dir, "weights.csv"), index_label="asset")
        print(f"wrote covariance.csv and weights.csv to {a.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
