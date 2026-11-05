#!/usr/bin/env python3
"""
Binomial trees for the binomial tutoring skill.

The pricing recursion and the plotly tree figure are taken from the "binomial
trees" notebook at

    https://learn-investments.rice-business.org

by Kerry Back and Kevin Crotty, Jones Graduate School of Business, Rice
University.  Extensions for tutoring use: the down factor d may differ from 1/u
(the notebook fixes d = 1/u), the replicating portfolio and early-exercise
nodes are reported alongside the values, a node can be blanked to make an
exercise, and a student's answer can be checked against the tree and matched
to the common mistakes without printing the correct number.

Pure Python: no numpy.  plotly is needed only for --plot.

Conventions
-----------
u and d are GROSS returns: u = 1.10 means +10%, d = 0.90 means -10%.
r is the risk-free rate PER PERIOD, so one dollar grows to 1 + r each period.
Trees are lists of lists: tree[t][i] is the node at date t reached by i DOWN
moves and t - i up moves.  So tree[t][0] is the top (all-up) node.
Nodes can be named by path ('0', 'u', 'd', 'uu', 'ud', 'dud', ...; only the
number of d's matters) or by 't,i'.

Usage
-----
    # the answer key: full tree and node table
    python binomial.py --S 100 --K 100 --r 0.02 --u 1.1 --d 0.9 --n 2 \
        --kind "European call"

    # an exercise: one node and its ancestors blanked, nothing hidden leaks
    python binomial.py ... --blank u

    # check a student's answer without printing the correct number
    python binomial.py ... --check 0=5.88
    python binomial.py ... --check u=0.75 --quantity delta

    # textbook inputs: annual continuously compounded rate, volatility,
    # maturity in years
    python binomial.py --S 100 --K 100 --rate 0.05 --sigma 0.3 --T 1 --n 4 \
        --kind "American put"

    # write the plotly stock and option trees to an HTML file
    python binomial.py ... --plot trees.html
"""

import argparse
import math

# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


def parse_kind(kind):
    """'American put', 'american-put', 'american_put', 'put' -> ('american', 'put').

    A bare 'call' or 'put' is European.
    """
    words = kind.lower().replace("-", " ").replace("_", " ").split()
    style = "european"
    right = None
    for w in words:
        if w in ("american", "amer", "am"):
            style = "american"
        elif w in ("european", "euro", "eu"):
            style = "european"
        elif w in ("call", "put"):
            right = w
    if right is None:
        raise ValueError(f"kind must name 'call' or 'put', got {kind!r}")
    return style, right


def kind_name(style, right):
    return f"{style.capitalize()} {right}"


def from_textbook(rate=None, sigma=None, T=None, n=None):
    """Per-period r and gross u, d from an annual continuously compounded rate,
    an annual volatility, and a maturity in years split into n periods."""
    dt = T / n
    out = {}
    if rate is not None:
        out["r"] = math.exp(rate * dt) - 1
    if sigma is not None:
        out["u"] = math.exp(sigma * math.sqrt(dt))
        out["d"] = 1 / out["u"]
    return out


def no_arbitrage_error(r, u, d):
    """None if d < 1+r < u, else an explanation of the arbitrage."""
    if d < 1 + r < u:
        return None
    if 1 + r >= u:
        trade = ("the bond earns at least as much as the stock in every state: "
                 "short the stock and lend the proceeds")
    else:
        trade = ("the stock earns at least as much as the bond in every state: "
                 "borrow and buy the stock")
    return (f"No-arbitrage fails: need d < 1+r < u, but d={d:.4f}, 1+r={1 + r:.4f}, "
            f"u={u:.4f}.  {trade.capitalize()}.  There is an arbitrage, so no "
            f"option price exists.")


# ---------------------------------------------------------------------------
# Trees
# ---------------------------------------------------------------------------


def stock_tree(S, u, d, n):
    return [[S * u ** (t - i) * d**i for i in range(t + 1)] for t in range(n + 1)]


def payoff(S, K, right):
    return max(S - K, 0.0) if right == "call" else max(K - S, 0.0)


def solve(S, K, r, u, d, n, kind):
    """Price on a recombining tree by backward induction.

    Returns a dict with the stock tree, value tree, hold tree (value of keeping
    the option one more period; None at expiry), q, and the set of
    early-exercise nodes (t, i).
    """
    style, right = parse_kind(kind) if isinstance(kind, str) else kind
    err = no_arbitrage_error(r, u, d)
    if err:
        raise ValueError(err)
    q = (1 + r - d) / (u - d)
    R = 1 + r
    st = stock_tree(S, u, d, n)
    value = [None] * (n + 1)
    hold = [None] * (n + 1)
    value[n] = [payoff(s, K, right) for s in st[n]]
    hold[n] = [None] * (n + 1)
    exercise = set()
    for t in range(n - 1, -1, -1):
        h = [(q * value[t + 1][i] + (1 - q) * value[t + 1][i + 1]) / R for i in range(t + 1)]
        v = list(h)
        if style == "american":
            for i in range(t + 1):
                ex = payoff(st[t][i], K, right)
                if ex > h[i] + 1e-12:
                    v[i] = ex
                    exercise.add((t, i))
        hold[t], value[t] = h, v
    return {
        "S": S, "K": K, "r": r, "u": u, "d": d, "n": n,
        "style": style, "right": right, "kind": kind_name(style, right),
        "q": q, "stock": st, "value": value, "hold": hold, "exercise": exercise,
    }


def replication(sol, t, i):
    """Shares (delta) and dollars in the bond that replicate holding the option
    one more period.  At an early-exercise node this replicates the value of
    holding, not the exercise value, since no portfolio pays the exercise value
    in both successor states.
    """
    st, v = sol["stock"], sol["value"]
    su, sd = st[t + 1][i], st[t + 1][i + 1]
    vu, vd = v[t + 1][i], v[t + 1][i + 1]
    delta = (vu - vd) / (su - sd)
    bond = (vd - delta * sd) / (1 + sol["r"])
    return delta, bond


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def node_label(t, i):
    """Path label: 'uud' style, with '0' for the root."""
    if t == 0:
        return "0"
    return "u" * (t - i) + "d" * i


def parse_node(spec, n=None):
    """'0', 'u', 'ud', 'du', or 't,i' -> (t, i)."""
    spec = str(spec).strip().lower()
    if "," in spec:
        t, i = (int(x) for x in spec.split(","))
    elif spec in ("0", "root", ""):
        t, i = 0, 0
    elif set(spec) <= {"u", "d"}:
        t, i = len(spec), spec.count("d")
    else:
        raise ValueError(f"cannot read node {spec!r}; use a path like 'ud' or 't,i'")
    if not 0 <= i <= t or (n is not None and t > n):
        raise ValueError(f"node {spec!r} is not in a {n}-period tree")
    return t, i


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


# ---------------------------------------------------------------------------
# Checking answers
# ---------------------------------------------------------------------------

# Each mistake: what the student did, and a question that exposes it without
# giving the number.
MISTAKES = {
    "no_discount": ("Took the risk-neutral expectation but did not discount it.",
                    "That is the expected payoff next period. Is that what you would pay today?"),
    "no_discount_multi": ("Took the risk-neutral expectation of the final payoffs and did not discount at all.",
                          "That is an expected payoff at expiration. How many periods away is that?"),
    "discount_once": ("Discounted the expected final payoff by one period instead of all of them.",
                      "How many periods does that payoff have to be discounted?"),
    "real_prob_half": ("Used a probability of 0.5 instead of q.",
                       "Where did the 0.5 come from?"),
    "flipped_q": ("Attached q to the down state and 1-q to the up state.",
                  "Which state does your q attach to?"),
    "average_payoffs": ("Averaged the two payoffs with no probabilities and no discounting.",
                        "Walk me through how you weighted the two states."),
    "up_only": ("Discounted the up-state value and ignored the down state.",
                "What is the option worth if the stock goes down?"),
    "gave_delta": ("Gave the hedge ratio instead of the value.",
                   "That is the number of shares. What does the whole portfolio cost?"),
    "delta_times_S": ("Priced the shares and forgot the bond position.",
                      "Did you pay for all of that yourself, or is there borrowing or lending too?"),
    "other_right": ("Priced the other kind of option (call instead of put, or put instead of call).",
                    "What does this option pay at expiration in each state?"),
    "ignored_early_exercise": ("Valued it as a European option: never compared holding with exercising.",
                               "At each node, what would you get if you exercised right there?"),
    "forgot_exercise_here": ("Rolled the tree back correctly but did not check exercise at this node.",
                             "What would you get if you exercised at this node instead of holding?"),
    "exercised_too_soon": ("Took the exercise value although holding is worth more.",
                           "Compare exercising here with holding one more period. Which is bigger?"),
    "delta_inverted": ("Divided the stock spread by the option spread instead of the other way round.",
                       "Delta is shares per option. Which spread goes on top?"),
    "delta_sign": ("Has the sign of the hedge ratio backward.",
                   "When the stock goes up, does this option gain or lose value?"),
    "bond_no_discount": ("Found what the bond must pay next period but did not discount it.",
                         "That is what the bond pays next period. What does it cost today?"),
    "bond_sign": ("Has the sign of the bond position backward (borrowing versus lending).",
                  "Are you borrowing or lending in this portfolio?"),
    "q_flipped": ("Gave 1-q, the risk-neutral probability of a down move.",
                  "Is that the probability of the up move or the down move?"),
    "q_half": ("Used 0.5.",
               "Where did the 0.5 come from? What must q satisfy?"),
    "q_net_rate": ("Used r instead of 1+r in the formula.",
                   "The stock moves are gross returns. Is your interest rate gross too?"),
}


def candidates(sol, t, i, quantity="value"):
    """Correct value and the value each known mistake produces at node (t, i).

    Returns a list of (name, value); name 'correct' comes first.  Mistakes that
    do not apply at this node (or coincide with the correct number) are left out.
    """
    n, r, q = sol["n"], sol["r"], sol["q"]
    R = 1 + r
    st, v, h = sol["stock"], sol["value"], sol["hold"]
    out = []
    if quantity == "q":
        out = [("correct", q), ("q_flipped", 1 - q), ("q_half", 0.5),
               ("q_net_rate", (r - sol["d"]) / (sol["u"] - sol["d"]))]
    elif t == n:
        out = [("correct", v[t][i])]
        if quantity == "value":
            other = "put" if sol["right"] == "call" else "call"
            out.append(("other_right", payoff(st[t][i], sol["K"], other)))
    elif quantity == "delta":
        delta, _ = replication(sol, t, i)
        vu, vd = v[t + 1][i], v[t + 1][i + 1]
        su, sd = st[t + 1][i], st[t + 1][i + 1]
        out = [("correct", delta), ("delta_sign", -delta)]
        if vu != vd:
            out.append(("delta_inverted", (su - sd) / (vu - vd)))
    elif quantity == "bond":
        delta, bond = replication(sol, t, i)
        out = [("correct", bond), ("bond_no_discount", bond * R), ("bond_sign", -bond)]
    elif quantity == "value":
        vu, vd = v[t + 1][i], v[t + 1][i + 1]
        delta, bond = replication(sol, t, i)
        out = [
            ("correct", v[t][i]),
            ("no_discount", q * vu + (1 - q) * vd),
            ("real_prob_half", 0.5 * (vu + vd) / R),
            ("flipped_q", ((1 - q) * vu + q * vd) / R),
            ("average_payoffs", 0.5 * (vu + vd)),
            ("up_only", vu / R),
            ("gave_delta", delta),
            ("delta_times_S", delta * st[t][i]),
        ]
        m = n - t
        if m > 1:
            # expectation of the final payoffs from this node, European style
            exp_T = sum(math.comb(m, k) * q ** (m - k) * (1 - q) ** k * v_T
                        for k, v_T in enumerate(_terminal_from(sol, t, i)))
            out += [("no_discount_multi", exp_T), ("discount_once", exp_T / R)]
        other = "put" if sol["right"] == "call" else "call"
        out.append(("other_right",
                     solve(st[t][i], sol["K"], r, sol["u"], sol["d"], m,
                           (sol["style"], other))["value"][0][0]))
        if sol["style"] == "american":
            euro = solve(st[t][i], sol["K"], r, sol["u"], sol["d"], m,
                         ("european", sol["right"]))["value"][0][0]
            out.append(("ignored_early_exercise", euro))
            ex = payoff(st[t][i], sol["K"], sol["right"])
            if (t, i) in sol["exercise"]:
                out.append(("forgot_exercise_here", h[t][i]))
            elif ex > 0:
                out.append(("exercised_too_soon", ex))
    else:
        raise ValueError("quantity must be value, delta, bond, or q")
    correct = out[0][1]
    return [out[0]] + [(k, x) for k, x in out[1:] if abs(x - correct) > 1e-9]


def _terminal_from(sol, t, i):
    """Option payoffs at expiry reachable from (t, i), top to bottom."""
    n = sol["n"]
    return [sol["value"][n][i + k] for k in range(n - t + 1)]


def close(a, b):
    """Within rounding: a student who rounds to cents should still match."""
    return abs(a - b) <= max(0.0051, 0.0025 * abs(b))


def check(sol, node, answer, quantity="value"):
    """Grade a student's number.

    Returns {'correct': bool, 'correct_value': float, 'matches': [mistake names]}.
    A number can match more than one mistake (3.92 in the running one-period
    example is both the flipped-q call and the correct put), so matches is a
    list and the tutor should ask rather than assume.
    """
    t, i = parse_node(node, sol["n"]) if not isinstance(node, tuple) else node
    cands = candidates(sol, t, i, quantity)
    correct_value = cands[0][1]
    matches = [name for name, x in cands[1:] if close(answer, x)]
    return {"correct": close(answer, correct_value), "correct_value": correct_value,
            "matches": matches}


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------


def ascii_tree(sol, hidden=None):
    """Column-per-date layout; each cell is 'S / V', '*' marks early exercise."""
    stree, vtree, exercise = sol["stock"], sol["value"], sol["exercise"]
    n = len(stree) - 1
    hidden = hidden or set()
    rows = [["" for _ in range(n + 1)] for _ in range(2 * n + 1)]
    for t in range(n + 1):
        for i in range(t + 1):
            row = 2 * i + (n - t)
            vtxt = "       ?" if (t, i) in hidden else f"{vtree[t][i]:8.2f}"
            # never mark a hidden node: the star would give away the answer
            mark = "*" if (t, i) in exercise and (t, i) not in hidden else " "
            rows[row][t] = f"{stree[t][i]:8.2f} /{vtxt}{mark}"
    header = "".join(f"{'t=' + str(t):^19}" for t in range(n + 1))
    lines = [header, "-" * len(header)]
    for row in rows:
        lines.append("".join(f"{cell:^19}" for cell in row).rstrip())
    return "\n".join(lines)


def tree_figure(tree, color="blue", ytitle="Underlying Price", reverse=False):
    """Plotly figure of a recombining tree (Back & Crotty)."""
    import plotly.graph_objects as go

    spliced = []
    for a, b in zip(tree[1:], tree[:-1]):
        x = []
        for i in range(len(a)):
            x.append(a[i])
            if i < len(b):
                x.append(b[i])
        spliced.append(x)

    fig = go.Figure()
    string = "$%{y:,.2f}<extra></extra>"
    for i in range(len(tree) - 1):
        x = [1, 0, 1] + [0, 1] * i
        x = [xx + i for xx in x]
        fig.add_trace(go.Scatter(
            x=x, y=spliced[i], mode="lines+markers", hovertemplate=string,
            marker=dict(size=12, color=color), line=dict(color=color),
            showlegend=False,
        ))
    fig.update_layout(
        xaxis=dict(tickmode="linear", tick0=0, dtick=1, title="Time"),
        yaxis=dict(tickprefix="$", tickformat=",.2f", title=ytitle,
                   autorange="reversed" if reverse else None),
        template="plotly_white",
    )
    return fig


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def main():
    p = argparse.ArgumentParser(description="Binomial option trees for tutoring.")
    p.add_argument("--S", type=float, default=100.0, help="initial stock price")
    p.add_argument("--K", type=float, default=100.0, help="strike price")
    p.add_argument("--r", type=float, default=None, help="risk-free rate per period (default 0.02)")
    p.add_argument("--u", type=float, default=None, help="gross up factor, e.g. 1.10 (default 1.1)")
    p.add_argument("--d", type=float, default=None, help="gross down factor (default 1/u)")
    p.add_argument("--n", type=int, default=2, help="number of periods")
    p.add_argument("--rate", type=float, default=None,
                   help="annual continuously compounded rate; sets r = e^(rate*T/n) - 1")
    p.add_argument("--sigma", type=float, default=None,
                   help="annual volatility; sets u = e^(sigma*sqrt(T/n)), d = 1/u")
    p.add_argument("--T", type=float, default=None, help="maturity in years (with --rate/--sigma)")
    p.add_argument("--kind", default="European call",
                   help="e.g. 'European call', 'american-put', 'put' (bare = European)")
    p.add_argument("--blank", default=None,
                   help="hide a node and its ancestors, e.g. --blank u or --blank 1,0")
    p.add_argument("--check", default=None,
                   help="NODE=ANSWER: grade a student's number without printing the answer")
    p.add_argument("--quantity", default="value", choices=["value", "delta", "bond", "q"],
                   help="what --check is grading (default value)")
    p.add_argument("--plot", default=None, help="write the plotly trees to this HTML file")
    p.add_argument("--brief", action="store_true", help="price and tree only, no node table")
    a = p.parse_args()

    r, u, d = a.r, a.u, a.d
    if a.rate is not None or a.sigma is not None:
        if a.T is None:
            p.error("--rate and --sigma need --T (maturity in years)")
        conv = from_textbook(a.rate, a.sigma, a.T, a.n)
        r = conv.get("r", r)
        u = conv.get("u", u)
        d = conv.get("d", d) if a.d is None else a.d
    r = 0.02 if r is None else r
    u = 1.1 if u is None else u
    d = 1 / u if d is None else d

    try:
        sol = solve(a.S, a.K, r, u, d, a.n, a.kind)
    except ValueError as e:
        raise SystemExit(str(e))

    if a.check:
        node, _, ans = a.check.partition("=")
        try:
            res = check(sol, node, float(ans), a.quantity)
        except ValueError as e:
            raise SystemExit(f"--check needs NODE=ANSWER with a node in the tree: {e}")
        print(f"{a.quantity} at node {node or '0'}: {float(ans):g} is "
              + ("CORRECT" if res["correct"] else "NOT correct"))
        for m in res["matches"]:
            did, ask = MISTAKES[m]
            print(f"  matches mistake '{m}': {did}\n    ask: {ask}")
        if not res["correct"] and not res["matches"]:
            print("  matches no known mistake: ask the student to walk through the steps")
        return

    try:
        blank = parse_node(a.blank, a.n) if a.blank else None
    except ValueError as e:
        raise SystemExit(str(e))
    hidden = hidden_nodes(blank, a.n)

    print(f"{sol['kind']}:  S={a.S:g}  K={a.K:g}  r={r:.6g}/period  u={u:.6g}  d={d:.6g}  n={a.n}")
    if hidden:
        # q is a step the student has to produce, so it is hidden with the nodes
        print(f"Exercise: {len(hidden)} option value(s) hidden, marked ?")
    else:
        print(f"Risk-neutral probability of an up move:  q = (1+r-d)/(u-d) = {sol['q']:.6f}")
        print(f"Value at date 0:  {sol['value'][0][0]:.4f}")
    print()
    print("Each cell is  stock price / option value"
          + ("   (* = early exercise)" if sol["exercise"] and not hidden else ""))
    print()
    print(ascii_tree(sol, hidden))

    if a.plot:
        f1 = tree_figure(sol["stock"], color="blue", ytitle="Underlying Price")
        f2 = tree_figure(sol["value"], color="green", ytitle=sol["kind"] + " Value",
                         reverse=(sol["right"] == "put"))
        with open(a.plot, "w") as fh:
            fh.write(f1.to_html(full_html=True, include_plotlyjs="cdn"))
            fh.write(f2.to_html(full_html=False, include_plotlyjs=False))
        print(f"\nWrote {a.plot}")

    # An exercise never prints the node table: hold, delta and bond at a
    # hidden node would give its value away.
    if a.brief or hidden:
        return

    print()
    print(f"{'t':>2} {'node':<8} {'S':>9} {'value':>9} {'hold':>9} {'exercise':>9} "
          f"{'delta':>8} {'bond':>10}")
    for t in range(a.n + 1):
        for i in range(t + 1):
            S_ti, V_ti = sol["stock"][t][i], sol["value"][t][i]
            ex = payoff(S_ti, a.K, sol["right"])
            if t < a.n:
                delta, bond = replication(sol, t, i)
                print(f"{t:>2} {node_label(t, i):<8} {S_ti:9.2f} {V_ti:9.4f} "
                      f"{sol['hold'][t][i]:9.4f} {ex:9.4f} {delta:8.4f} {bond:10.4f}")
            else:
                print(f"{t:>2} {node_label(t, i):<8} {S_ti:9.2f} {V_ti:9.4f} {'--':>9} "
                      f"{ex:9.4f} {'--':>8} {'--':>10}")


if __name__ == "__main__":
    main()
