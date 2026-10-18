#!/usr/bin/env python3
"""
Binomial trees for the binomial tutoring skill.

The pricing engine (europeanTree, americanTree) and the plotly tree figure are
taken from the "binomial trees" notebook at

    https://learn-investments.rice-business.org

by Kerry Back and Kevin Crotty, Jones Graduate School of Business, Rice
University.  Two extensions were made for tutoring use: the down factor d may
differ from 1/u (the notebook fixes d = 1/u), and the replicating portfolio and
early-exercise nodes are reported alongside the values.

Conventions
-----------
u and d are GROSS returns: u = 1.10 means +10%, d = 0.90 means -10%.
r is the risk-free rate PER PERIOD, so one dollar grows to 1 + r each period.
Trees are lists of lists: tree[t][i] is the node at date t reached by i DOWN
moves and t - i up moves.  So tree[t][0] is the top (all-up) node.

Usage
-----
    python binomial.py --S 100 --K 100 --r 0.02 --u 1.1 --d 0.9 --n 2 \
        --kind "European call"

    # blank out one node so the student has to fill it in
    python binomial.py ... --blank 1,0

    # write the plotly stock and option trees to an HTML file
    python binomial.py ... --plot trees.html
"""

import argparse

import numpy as np


# ---------------------------------------------------------------------------
# Pricing engine (Back & Crotty, learn-investments.rice-business.org)
# ---------------------------------------------------------------------------


def europeanTree(S, K, r, u, n, kind, d=None):
    # u and d are gross returns; d defaults to 1/u as in the original notebook
    def f(S):
        if kind == "call":
            return np.maximum(np.array(S) - K, 0)
        else:
            return np.maximum(K - np.array(S), 0)

    d = 1 / u if d is None else d
    p = (1 + r - d) / (u - d)
    disc = 1 / (1 + r)
    ST = [S * u ** (n - i) * d**i for i in range(n + 1)]
    x = f(ST)
    lst = [x]
    while len(x) > 1:
        x = disc * (p * x[:-1] + (1 - p) * x[1:])
        lst.insert(0, x)
    return [list(x) for x in lst], p


def americanTree(S, K, r, u, n, kind, d=None):
    # u and d are gross returns; d defaults to 1/u as in the original notebook
    def f(S):
        if kind == "call":
            return np.maximum(np.array(S) - K, 0)
        else:
            return np.maximum(K - np.array(S), 0)

    d = 1 / u if d is None else d
    p = (1 + r - d) / (u - d)
    disc = 1 / (1 + r)
    ST = [S * u ** (n - i) * d**i for i in range(n + 1)]
    x = f(ST)
    lst = [x]
    while len(x) > 1:
        x0 = disc * (p * x[:-1] + (1 - p) * x[1:])
        t = len(x0) - 1
        St = [S * u ** (t - i) * d**i for i in range(t + 1)]
        x = np.maximum(x0, f(St))
        lst.insert(0, x)
    return [list(x) for x in lst], p


# ---------------------------------------------------------------------------
# Tree figure (Back & Crotty, learn-investments.rice-business.org)
# ---------------------------------------------------------------------------


def tree_figure(tree, color="blue", ytitle="Underlying Price", reverse=False):
    """Plotly figure of a recombining tree."""
    import plotly.graph_objects as go

    spliced = []
    for a, b in zip(tree[1:], tree[:-1]):
        x = []
        for i in range(len(a)):
            x.append(a[i])
            try:
                x.append(b[i])
            except IndexError:
                pass
        spliced.append(x)

    fig = go.Figure()
    string = "$%{y:,.2f}<extra></extra>"
    for i in range(len(tree) - 1):
        x = [1, 0, 1]
        for _ in range(i):
            x.append(0)
            x.append(1)
        x = np.array(x) + i
        trace = go.Scatter(
            x=x,
            y=spliced[i],
            mode="lines+markers",
            hovertemplate=string,
            marker=dict(size=12, color=color),
            line=dict(color=color),
            showlegend=False,
        )
        fig.add_trace(trace)

    fig.update_layout(
        xaxis=dict(tickmode="linear", tick0=0, dtick=1, title="Time"),
        yaxis=dict(
            tickprefix="$",
            tickformat=",.2f",
            title=ytitle,
            autorange="reversed" if reverse else None,
        ),
        template="plotly_white",
    )
    return fig


# ---------------------------------------------------------------------------
# Tutoring helpers
# ---------------------------------------------------------------------------


def stock_tree(S, u, d, n):
    return [[S * u ** (t - i) * d**i for i in range(t + 1)] for t in range(n + 1)]


def payoff(S, K, right):
    return max(S - K, 0) if right == "call" else max(K - S, 0)


def node_label(t, i):
    """Path label: 'uud' style, with '0' for the root."""
    if t == 0:
        return "0"
    return "u" * (t - i) + "d" * i


def replication(stree, vtree, t, i, r):
    """Shares (delta) and dollars in the bond that replicate holding the option
    one more period.  At an early-exercise node this replicates the value of
    holding, not the exercise value, since no portfolio pays the exercise value
    in both successor states.
    """
    su, sd = stree[t + 1][i], stree[t + 1][i + 1]
    vu, vd = vtree[t + 1][i], vtree[t + 1][i + 1]
    delta = (vu - vd) / (su - sd)
    bond = (vd - delta * sd) / (1 + r)
    return delta, bond


def hidden_nodes(blank, n):
    """The blanked node plus every earlier node whose value depends on it.

    Blanking one interior node and leaving its ancestors visible would give the
    answer away, so the student is asked to rebuild that whole part of the tree.
    """
    if blank is None:
        return set()
    t, i = blank
    hidden = {(t, i)}
    for s in range(t):
        for j in range(s + 1):
            if j <= i <= j + (t - s):
                hidden.add((s, j))
    return hidden


def ascii_tree(stree, vtree, exercise=None, hidden=None):
    """Column-per-date layout; each cell is 'S / V', '*' marks early exercise."""
    n = len(stree) - 1
    hidden = hidden or set()
    rows = [["" for _ in range(n + 1)] for _ in range(2 * n + 1)]
    for t in range(n + 1):
        for i in range(t + 1):
            row = 2 * i + (n - t)
            v = vtree[t][i]
            if (t, i) in hidden:
                vtxt = "       ?"
            else:
                vtxt = f"{v:8.2f}"
            # never mark a hidden node: the star would give away the answer
            mark = "*" if exercise and (t, i) in exercise and (t, i) not in hidden else " "
            rows[row][t] = f"{stree[t][i]:8.2f} /{vtxt}{mark}"
    header = "".join(f"{'t=' + str(t):^19}" for t in range(n + 1))
    lines = [header, "-" * len(header)]
    for row in rows:
        lines.append("".join(f"{cell:^19}" for cell in row).rstrip())
    return "\n".join(lines)


def solve(S, K, r, u, d, n, kind):
    """Return stock tree, value tree, q, and the set of early-exercise nodes."""
    style, right = kind.split()
    style, right = style.lower(), right.lower()
    if style == "european":
        vtree, q = europeanTree(S, K, r, u, n, right, d=d)
        exercise = set()
    else:
        vtree, q = americanTree(S, K, r, u, n, right, d=d)
        exercise = set()
        stree_ = stock_tree(S, u, d, n)
        for t in range(n):
            for i in range(t + 1):
                hold = (q * vtree[t + 1][i] + (1 - q) * vtree[t + 1][i + 1]) / (1 + r)
                if payoff(stree_[t][i], K, right) > hold + 1e-12:
                    exercise.add((t, i))
    return stock_tree(S, u, d, n), vtree, q, exercise


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("--S", type=float, default=100.0, help="initial stock price")
    p.add_argument("--K", type=float, default=100.0, help="strike price")
    p.add_argument("--r", type=float, default=0.02, help="risk-free rate per period")
    p.add_argument("--u", type=float, default=1.1, help="gross up factor, e.g. 1.10")
    p.add_argument("--d", type=float, default=None, help="gross down factor (default 1/u)")
    p.add_argument("--n", type=int, default=2, help="number of periods")
    p.add_argument(
        "--kind",
        default="European call",
        help="'European call', 'European put', 'American call', 'American put'",
    )
    p.add_argument("--blank", default=None, help="hide one option value, e.g. --blank 1,0")
    p.add_argument("--plot", default=None, help="write the plotly trees to this HTML file")
    p.add_argument("--brief", action="store_true", help="price and tree only, no node table")
    a = p.parse_args()

    d = 1 / a.u if a.d is None else a.d
    if not (d < 1 + a.r < a.u):
        raise SystemExit(
            f"No-arbitrage fails: need d < 1+r < u, but d={d:.4f}, 1+r={1 + a.r:.4f}, "
            f"u={a.u:.4f}.  With these numbers the stock dominates the bond (or is "
            f"dominated by it), so there is an arbitrage and no option price exists."
        )

    stree, vtree, q, exercise = solve(a.S, a.K, a.r, a.u, d, a.n, a.kind)
    blank = tuple(int(x) for x in a.blank.split(",")) if a.blank else None
    hidden = hidden_nodes(blank, a.n)
    right = a.kind.split()[1].lower()

    print(f"{a.kind}:  S={a.S:g}  K={a.K:g}  r={a.r:.4g}/period  u={a.u:g}  d={d:.6g}  n={a.n}")
    print(f"Risk-neutral probability of an up move:  q = (1+r-d)/(u-d) = {q:.6f}")
    if hidden:
        print(f"Value at date 0:  hidden ({len(hidden)} node(s) blanked for the student)")
    else:
        print(f"Value at date 0:  {vtree[0][0]:.4f}")
    print()
    print("Each cell is  stock price / option value"
          + ("   (* = early exercise)" if exercise else ""))
    print()
    print(ascii_tree(stree, vtree, exercise, hidden))

    if a.plot:
        f1 = tree_figure(stree, color="blue", ytitle="Underlying Price")
        f2 = tree_figure(vtree, color="green", ytitle=a.kind + " Value",
                         reverse=(right == "put"))
        with open(a.plot, "w") as fh:
            fh.write(f1.to_html(full_html=True, include_plotlyjs="cdn"))
            fh.write(f2.to_html(full_html=False, include_plotlyjs=False))
        print(f"\nWrote {a.plot}")

    if a.brief:
        return

    print()
    print(f"{'t':>2} {'node':<8} {'S':>9} {'value':>9} {'hold':>9} {'exercise':>9} "
          f"{'delta':>8} {'bond':>10}")
    for t in range(a.n + 1):
        for i in range(t + 1):
            S_ti, V_ti = stree[t][i], vtree[t][i]
            ex = payoff(S_ti, a.K, right)
            if t < a.n:
                hold = (q * vtree[t + 1][i] + (1 - q) * vtree[t + 1][i + 1]) / (1 + a.r)
                delta, bond = replication(stree, vtree, t, i, a.r)
                print(f"{t:>2} {node_label(t, i):<8} {S_ti:9.2f} {V_ti:9.4f} {hold:9.4f} "
                      f"{ex:9.4f} {delta:8.4f} {bond:10.4f}")
            else:
                print(f"{t:>2} {node_label(t, i):<8} {S_ti:9.2f} {V_ti:9.4f} {'--':>9} "
                      f"{ex:9.4f} {'--':>8} {'--':>10}")


if __name__ == "__main__":
    main()
