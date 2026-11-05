"""The binomial tutor's tools: the private answer key (price_tree), trees
drawn for the student (show_tree), grading (check_answer), and the plots the
tutor can put on the board.  Results go to the model only; the student sees
the tree payloads that show_tree emits, with hidden values removed.

The engine adds the tools every tutor has (calculate, save_progress,
start_module, show_plot) and calls run() for the tools here.
"""

import json
import math

import binomial as bt
import plots
from errors import ToolError

TREE_PARAMS = {
    "S": {"type": "number", "description": "Stock price today."},
    "K": {"type": "number", "description": "Strike price."},
    "n": {"type": "integer", "minimum": 1, "maximum": 12, "description": "Number of periods."},
    "kind": {"type": "string",
             "description": "'European call', 'European put', 'American call', or 'American put'."},
    "r": {"type": "number", "description": "Risk-free rate per period, e.g. 0.02. Omit if rate is given."},
    "u": {"type": "number", "description": "Gross up factor, e.g. 1.1. Omit if sigma is given."},
    "d": {"type": "number", "description": "Gross down factor, e.g. 0.9. Defaults to 1/u."},
    "rate": {"type": "number",
             "description": "Annual continuously compounded rate (textbook input). Sets r = e^(rate*T/n) - 1. Needs T."},
    "sigma": {"type": "number",
              "description": "Annual volatility (textbook input). Sets u = e^(sigma*sqrt(T/n)), d = 1/u. Needs T."},
    "T": {"type": "number", "description": "Maturity in years, with rate or sigma."},
}

TOOLS = [
    {
        "name": "price_tree",
        "description": (
            "Private answer key. Prices a binomial tree and returns q, and for every node the "
            "stock price, option value, value of holding, value of exercising, delta and bond. "
            "The student never sees this. Use it before stating any number, and to prepare "
            "worked examples."),
        "input_schema": {"type": "object", "properties": TREE_PARAMS,
                         "required": ["S", "K", "n", "kind"]},
    },
    {
        "name": "show_tree",
        "description": (
            "Draw a binomial tree in the chat for the student, each node showing stock price "
            "and option value. hide controls what the student must fill in: 'none' shows every "
            "value (for a worked example or after the student has solved it); 'all' shows only "
            "stock prices; a node name such as 'u' or 'ud' hides that node and every earlier "
            "node that depends on it. Hidden values are never sent to the student. Returns a "
            "tree id for check_answer, and the full answer key for you."),
        "input_schema": {
            "type": "object",
            "properties": {
                **TREE_PARAMS,
                "hide": {"type": "string",
                         "description": "'none', 'all', or a node name such as 'u', 'd', 'ud'."},
                "caption": {"type": "string",
                            "description": "Optional short title, e.g. 'Exercise 3.3' or 'Worked example'. The kind and parameters are printed automatically; do not repeat them."},
            },
            "required": ["S", "K", "n", "kind", "hide"],
        },
    },
    {
        "name": "check_answer",
        "description": (
            "Grade a number the student gave for a tree you displayed with show_tree. Returns "
            "whether it is correct, the correct value (for you only), and the known mistakes "
            "the number matches, each with a question that exposes it without giving the answer."),
        "input_schema": {
            "type": "object",
            "properties": {
                "tree_id": {"type": "string", "description": "Id returned by show_tree."},
                "node": {"type": "string", "description": "Node the answer is for: '0' (today), 'u', 'd', 'uu', ..."},
                "quantity": {"type": "string", "enum": ["value", "delta", "bond", "q"],
                             "description": "What the student computed. Default value."},
                "answer": {"type": "number", "description": "The student's number."},
            },
            "required": ["tree_id", "node", "answer"],
        },
    },
]


def _solve(args):
    r, u, d = args.get("r"), args.get("u"), args.get("d")
    if args.get("rate") is not None or args.get("sigma") is not None:
        if args.get("T") is None:
            raise ToolError("rate and sigma need T (maturity in years).")
        conv = bt.from_textbook(args.get("rate"), args.get("sigma"), args["T"], args["n"])
        r = conv.get("r", r)
        u = conv.get("u", u)
        if "d" in conv and d is None:
            d = conv["d"]
    if r is None or u is None:
        raise ToolError("Give r and u (per period, gross), or rate, sigma and T.")
    d = 1 / u if d is None else d
    if not 1 <= args["n"] <= 12:
        raise ToolError("n must be between 1 and 12.")
    try:
        return bt.solve(args["S"], args["K"], r, u, d, args["n"], args["kind"])
    except ValueError as e:
        raise ToolError(str(e))


def _key(sol):
    """The full answer key as text, for the model."""
    lines = [f"{sol['kind']}: S={sol['S']:g} K={sol['K']:g} r={sol['r']:.6g}/period "
             f"u={sol['u']:.6g} d={sol['d']:.6g} n={sol['n']}",
             f"q = {sol['q']:.6f}",
             "node  S  value  hold  exercise  delta  bond"]
    for t in range(sol["n"] + 1):
        for i in range(t + 1):
            S, V = sol["stock"][t][i], sol["value"][t][i]
            ex = bt.payoff(S, sol["K"], sol["right"])
            star = " *early exercise" if (t, i) in sol["exercise"] else ""
            if t < sol["n"]:
                delta, bond = bt.replication(sol, t, i)
                lines.append(f"{bt.node_label(t, i)}  {S:.4f}  {V:.4f}  {sol['hold'][t][i]:.4f}  "
                             f"{ex:.4f}  {delta:.4f}  {bond:.4f}{star}")
            else:
                lines.append(f"{bt.node_label(t, i)}  {S:.4f}  {V:.4f}  --  {ex:.4f}  --  --")
    return "\n".join(lines)


def tree_payload(sol, hide, tree_id, caption=None):
    """What the browser gets.  Hidden values are None, not masked client-side."""
    n = sol["n"]
    if hide in (None, "", "none"):
        hidden = set()
    elif hide == "all":
        hidden = {(t, i) for t in range(n + 1) for i in range(t + 1)}
    else:
        hidden = bt.hidden_nodes(bt.parse_node(hide, n), n)
    nodes = []
    for t in range(n + 1):
        for i in range(t + 1):
            h = (t, i) in hidden
            nodes.append({
                "t": t, "i": i, "label": bt.node_label(t, i),
                "S": round(sol["stock"][t][i], 2),
                "V": None if h else round(sol["value"][t][i], 2),
                "exercise": (t, i) in sol["exercise"] and not h,
            })
    return {"id": tree_id, "n": n, "kind": sol["kind"], "caption": caption or "",
            "params": {"S": sol["S"], "K": sol["K"], "r": round(sol["r"], 6),
                       "u": round(sol["u"], 6), "d": round(sol["d"], 6)},
            "nodes": nodes}


def run(name, args, state):
    """Execute one of this tutor's tools.

    state is the session dict: state['trees'] maps tree id -> solve() inputs,
    state['progress'] is the student record.  Returns (result_text, tree_payload
    or None).  Raises ToolError for bad input.
    """
    if name == "price_tree":
        return _key(_solve(args)), None

    if name == "show_tree":
        sol = _solve(args)
        hide = args.get("hide", "none")
        tree_id = f"T{len(state['trees']) + 1}"
        try:
            payload = tree_payload(sol, hide, tree_id, args.get("caption"))
        except ValueError as e:
            raise ToolError(str(e))
        inputs = {k: args[k] for k in TREE_PARAMS if args.get(k) is not None}
        state["trees"][tree_id] = inputs
        shown = sum(1 for nd in payload["nodes"] if nd["V"] is not None)
        return (f"Displayed tree {tree_id} to the student ({shown} of {len(payload['nodes'])} "
                f"option values visible; hide={hide!r}). The student cannot see the key below.\n\n"
                + _key(sol)), payload

    if name == "check_answer":
        inputs = state["trees"].get(args["tree_id"])
        if inputs is None:
            raise ToolError(f"No tree {args['tree_id']!r}. Ids so far: {sorted(state['trees'])}.")
        sol = _solve(inputs)
        quantity = args.get("quantity") or "value"
        try:
            res = bt.check(sol, args["node"], float(args["answer"]), quantity)
        except ValueError as e:
            raise ToolError(str(e))
        out = {
            "correct": res["correct"],
            "correct_value_for_you_only": round(res["correct_value"], 4),
            "matches": [{"mistake": m, "what_they_did": bt.MISTAKES[m][0],
                         "question_to_ask": bt.MISTAKES[m][1]} for m in res["matches"]],
        }
        if not res["correct"] and not res["matches"]:
            out["advice"] = "Matches no known mistake. Ask the student to walk you through the steps."
        if len(res["matches"]) > 1:
            out["advice"] = "Matches more than one mistake. Ask which, rather than assuming."
        return json.dumps(out, indent=1), None

    raise ToolError(f"Unknown tool {name!r}.")


# Plots for show_plot: name -> what it shows and what it needs.  The engine
# builds the show_plot tool from PLOTS and PLOT_PARAMS and calls make_plot.
PLOTS = {
    "payoff": ("an option's payoff at expiry against the stock price at expiry "
               "(needs kind and K; position 'long' or 'short'), for Module 1."),
    "american_vs_european": ("American and European put values today against the "
                             "stock price, with the exercise value K - S, shading where early exercise is "
                             "best (needs K and n, and r and u, d per period, or rate, sigma and T), for "
                             "Module 4."),
    "return_distribution": ("the risk-neutral distribution of the log return over T "
                            "on an n-period Cox-Ross-Rubinstein tree, as bars, against its normal limit "
                            "(needs sigma, rate, T and n, with n up to 200), for Module 3."),
}

PLOT_PARAMS = {
    "kind": {"type": "string", "description": "For payoff: 'call' or 'put'."},
    "position": {"type": "string", "enum": ["long", "short"]},
    "K": TREE_PARAMS["K"],
    "n": {"type": "integer", "minimum": 1, "maximum": 200,
          "description": "Number of periods (at most 12, or 200 for return_distribution)."},
    "r": TREE_PARAMS["r"],
    "u": TREE_PARAMS["u"], "d": TREE_PARAMS["d"], "rate": TREE_PARAMS["rate"],
    "sigma": TREE_PARAMS["sigma"], "T": TREE_PARAMS["T"],
}


def make_plot(args):
    """Draw one of PLOTS.  Returns (result_text, {'plot': figure})."""
    if args["plot"] == "return_distribution":
        need = [k for k in ("sigma", "rate", "T", "n") if args.get(k) is None]
        if need:
            raise ToolError("return_distribution needs " + ", ".join(need) + ".")
        sigma, rate, T, n = float(args["sigma"]), float(args["rate"]), float(args["T"]), int(args["n"])
        if sigma <= 0 or T <= 0 or not 1 <= n <= 200:
            raise ToolError("Need sigma > 0, T > 0 and n from 1 to 200.")
        if not math.exp(-sigma * math.sqrt(T / n)) < math.exp(rate * T / n) < math.exp(sigma * math.sqrt(T / n)):
            raise ToolError("With these inputs q is not between 0 and 1: use more periods or a larger sigma.")
        fig = plots.return_distribution(sigma, rate, T, n)
        what = (f"the distribution of the log return over {T:g} years on a {n}-period tree "
                f"(sigma={sigma:g}, rate={rate:g}) against the normal with mean "
                f"{(rate - sigma ** 2 / 2) * T:.6g} and standard deviation {sigma * math.sqrt(T):.6g}")
        if args.get("caption"):
            fig["caption"] = args["caption"]
        return f"Plotted {what} on the board for the student.", {"plot": fig}
    if args.get("K") is None:
        raise ToolError(f"{args['plot']} needs K.")
    K = float(args["K"])
    if K <= 0:
        raise ToolError("K must be positive.")
    if args["plot"] == "payoff":
        try:
            fig = plots.payoff(args.get("kind") or "call", K, args.get("position") or "long")
        except ValueError as e:
            raise ToolError(str(e))
        what = f"the payoff at expiry of a {args.get('position') or 'long'} {args.get('kind') or 'call'} with strike {K:g}"
    elif args["plot"] == "american_vs_european":
        if "n" not in args:
            raise ToolError("american_vs_european needs n.")
        sol = _solve({**args, "S": K, "kind": "American put"})   # checks the inputs and converts rate/sigma/T
        fig = plots.american_vs_european(K, sol["r"], sol["u"], sol["d"], int(args["n"]))
        what = (f"American and European put values today against the stock price "
                f"(K={K:g}, n={sol['n']}, r={sol['r']:.6g}, u={sol['u']:.6g}, d={sol['d']:.6g})")
    else:
        raise ToolError(f"Unknown plot {args['plot']!r}.")
    if args.get("caption"):
        fig["caption"] = args["caption"]
    return f"Plotted {what} on the board for the student.", {"plot": fig}
