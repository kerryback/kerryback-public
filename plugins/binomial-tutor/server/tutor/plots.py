"""Plots the tutor can put on the board, as Plotly figures (data and layout).

The tutor names a plot and its inputs; every number in the figure comes from
the pricing engine here, never from the model.

payoff                  an option's payoff at expiry against the stock price (Module 1)
american_vs_european    American and European put values today against the stock
                        price, with the exercise value, showing where early
                        exercise starts (Module 4)
return_distribution     the log return over T on a calibrated n-period tree,
                        against its normal limit (Module 3)
"""

import math

import binomial as bt

NAVY, RED, GRAY = "#1b2f6e", "#a12b2b", "#7c7e7f"


def _grid(lo, hi, n):
    return [lo + (hi - lo) * k / (n - 1) for k in range(n)]


def _r4(xs):
    return [round(x, 4) for x in xs]


def payoff(kind, K, position="long"):
    """Payoff at expiry of a long or short European-style call or put."""
    right = bt.parse_kind(kind)[1]
    sign = -1 if position == "short" else 1
    xs = _grid(0, 2 * K, 81)
    ys = [sign * bt.payoff(S, K, right) for S in xs]
    name = f"{position.capitalize()} {right}, strike {K:g}"
    return {
        "data": [{"x": _r4(xs), "y": _r4(ys), "mode": "lines", "name": name,
                  "line": {"color": NAVY, "width": 3}}],
        "layout": {"title": {"text": f"Payoff at expiry: {name.lower()}"},
                   "xaxis": {"title": {"text": "Stock price at expiry"}},
                   "yaxis": {"title": {"text": "Payoff"}, "zeroline": True},
                   "shapes": [{"type": "line", "x0": K, "x1": K, "yref": "paper", "y0": 0, "y1": 1,
                               "line": {"color": GRAY, "dash": "dot", "width": 1.5}}],
                   "annotations": [{"x": K, "yref": "paper", "y": 1, "text": f"K = {K:g}",
                                    "showarrow": False, "yanchor": "bottom"}],
                   "showlegend": False},
    }


def american_vs_european(K, r, u, d, n):
    """Put values today for a range of stock prices, on an n-period tree with
    per-period r, u and d, against the value of exercising now."""
    xs = _grid(0.5 * K, 1.5 * K, 41)
    amer = [bt.solve(S, K, r, u, d, n, "American put")["value"][0][0] for S in xs]
    euro = [bt.solve(S, K, r, u, d, n, "European put")["value"][0][0] for S in xs]
    exer = [max(K - S, 0.0) for S in xs]
    # The largest stock price at which exercising now is best (American = exercise value).
    early = [S for S, a, e in zip(xs, amer, exer) if e > 0 and abs(a - e) < 1e-9]
    layout = {"title": {"text": f"Put values today, {n}-period tree"},
              "xaxis": {"title": {"text": "Stock price today"}},
              "yaxis": {"title": {"text": "Value"}},
              "legend": {"orientation": "h", "y": -0.32},
              "margin": {"l": 56, "r": 16, "t": 44, "b": 96}, "height": 380}
    if early:
        s_star = max(early)
        layout["shapes"] = [{"type": "rect", "x0": xs[0], "x1": s_star, "yref": "paper", "y0": 0, "y1": 1,
                             "fillcolor": RED, "opacity": 0.08, "line": {"width": 0}}]
        layout["annotations"] = [{"x": (xs[0] + s_star) / 2, "yref": "paper", "y": 1,
                                  "text": "exercise early", "showarrow": False, "yanchor": "bottom"}]
    return {
        "data": [
            {"x": _r4(xs), "y": _r4(amer), "mode": "lines", "name": "American put",
             "line": {"color": RED, "width": 3}},
            {"x": _r4(xs), "y": _r4(euro), "mode": "lines", "name": "European put",
             "line": {"color": NAVY, "width": 3}},
            {"x": _r4(xs), "y": _r4(exer), "mode": "lines", "name": "Exercise now (K − S)",
             "line": {"color": GRAY, "width": 2, "dash": "dash"}},
        ],
        "layout": layout,
    }


def return_distribution(sigma, rate, T, n):
    """Risk-neutral distribution of log(S_T/S) on an n-period Cox-Ross-Rubinstein
    tree, as a density (bars of width 2*sigma*sqrt(dt)), against the normal
    limit with mean (rate - sigma^2/2)T and variance sigma^2 T."""
    dt = T / n
    step = sigma * math.sqrt(dt)
    u, d = math.exp(step), math.exp(-step)
    q = (math.exp(rate * dt) - d) / (u - d)
    xs = [(2 * k - n) * step for k in range(n + 1)]
    ps = [math.comb(n, k) * q ** k * (1 - q) ** (n - k) for k in range(n + 1)]
    mean, sd = (rate - sigma ** 2 / 2) * T, sigma * math.sqrt(T)
    lo, hi = mean - 4 * sd, mean + 4 * sd
    keep = [i for i, x in enumerate(xs) if lo - step <= x <= hi + step]
    grid = _grid(lo, hi, 161)
    curve = [math.exp(-((x - mean) / sd) ** 2 / 2) / (sd * math.sqrt(2 * math.pi)) for x in grid]
    return {
        "data": [
            {"type": "bar", "x": _r4([xs[i] for i in keep]), "y": _r4([ps[i] / (2 * step) for i in keep]),
             "width": round(2 * step * 0.9, 4), "name": f"{n}-period tree",
             "marker": {"color": NAVY, "opacity": 0.55}},
            {"x": _r4(grid), "y": _r4(curve), "mode": "lines", "name": "Normal limit",
             "line": {"color": RED, "width": 3}},
        ],
        "layout": {"title": {"text": f"Log return over {T:g} year{'' if T == 1 else 's'}: {n} periods vs. the normal"},
                   "xaxis": {"title": {"text": "Continuously compounded return log(S_T / S)"},
                             "range": [round(lo, 4), round(hi, 4)]},
                   "yaxis": {"title": {"text": "Probability density"}},
                   "bargap": 0,
                   "legend": {"orientation": "h", "y": -0.32},
                   "margin": {"l": 56, "r": 16, "t": 44, "b": 96}, "height": 380},
    }
