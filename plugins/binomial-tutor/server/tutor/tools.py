"""Tools the tutor model calls: the tutor's own tools (from its topic.py) and
the ones every tutor has.  Results go to the model only; the student sees the
payloads the tools emit (trees, plots, module intros).

Every tutor has calculate (safe arithmetic), save_progress (the student
record), start_module (plays a module's fixed intro) and, if its topic.py
declares PLOTS, show_plot.
"""

import ast
import inspect
import math
import operator

import intros
from errors import ToolError
from tutor_config import topic

N_MODULES = max(intros.MODULES)

_COMMON = [
    {
        "name": "save_progress",
        "description": (
            "Replace the student's record, which carries over to their next session. Call when a "
            "module ends, when the student stops, and when a mistake repeats."),
        "input_schema": {
            "type": "object",
            "properties": {
                "modules_done": {"type": "array", "items": {"type": "integer", "minimum": 1, "maximum": N_MODULES}},
                "now_in": {"type": "string", "description": "Module and exercise, e.g. '3, stopped after exercise 3.1'."},
                "mistakes_seen": {"type": "array", "items": {"type": "string"}},
                "objectives_met": {"type": "array", "items": {"type": "string"},
                                   "description": "Ids of learning objectives the student has met, e.g. ['1.1', '1.2']."},
                "notes": {"type": "string", "description": "Anything else worth knowing next time. One or two lines."},
            },
            "required": ["modules_done", "now_in", "mistakes_seen"],
        },
    },
    {
        "name": "start_module",
        "description": (
            "Begin a module. The app shows and speaks the module's fixed intro (what the "
            "student will learn and why it is useful) and its learning objectives. Call this "
            "whenever you start teaching a module, and never give a module overview yourself. "
            "After it returns, start teaching the module."),
        "input_schema": {
            "type": "object",
            "properties": {"module": {"type": "integer", "minimum": 1, "maximum": N_MODULES}},
            "required": ["module"],
        },
    },
    {
        "name": "calculate",
        "description": (
            "Arithmetic. Never compute a number yourself: use the topic's tools for anything "
            "they cover and this tool for everything else, e.g. '0.6*110 + 0.4*90', "
            "'(0.6*10 + 0.4*0)/1.02', 'max(110 - 100, 0)', '0.0126*sqrt(252)'. "
            "Supports + - * / ^ ** and parentheses, and max, min, abs, exp, log, sqrt, round. "
            "The student never sees the result."),
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
    },
]

_PLOTS = getattr(topic, "PLOTS", None)
_SHOW_PLOT = [{
    "name": "show_plot",
    "description": (
        "Draw a plot on the board. The app computes every number in it. "
        + " ".join(f"{name!r}: {what}" for name, what in (_PLOTS or {}).items())
        + " Never plot the exact problem the student is working on: the plot "
        "shows values the student may be asked to find."),
    "input_schema": {
        "type": "object",
        "properties": {
            "plot": {"type": "string", "enum": list(_PLOTS or [])},
            **getattr(topic, "PLOT_PARAMS", {}),
            "caption": {"type": "string", "description": "One line shown above the plot."},
        },
        "required": ["plot"],
    },
}] if _PLOTS else []

# The tutor's tools first, then save_progress, start_module, show_plot, calculate.
TOOLS = topic.TOOLS + _COMMON[:2] + _SHOW_PLOT + _COMMON[2:]
_TOPIC_TOOLS = {t["name"] for t in topic.TOOLS}

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos}
_FUNCS = {"max": max, "min": min, "abs": abs, "exp": math.exp, "log": math.log,
          "sqrt": math.sqrt, "round": round}


def calculate(expression):
    """Evaluate arithmetic safely: numbers, operators and a few functions only."""
    expr = expression.replace("^", "**").replace("×", "*").replace("−", "-").replace("÷", "/")

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            a, b = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Pow) and abs(b) > 100:
                raise ToolError("Exponent too large.")
            return _OPS[type(node.op)](a, b)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in _FUNCS and not node.keywords):
            return _FUNCS[node.func.id](*[ev(a) for a in node.args])
        raise ToolError(f"Not arithmetic: {ast.unparse(node) if hasattr(ast, 'unparse') else node!r}")

    if len(expr) > 500:
        raise ToolError("Expression too long.")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        raise ToolError(f"Could not read {expression!r} as arithmetic.")
    try:
        value = ev(tree)
    except ZeroDivisionError:
        raise ToolError("Division by zero.")
    except (ValueError, OverflowError) as e:
        raise ToolError(str(e))
    return f"{expression} = {value:.10g}"


def run_tool(name, args, state):
    """Execute one tool call.

    state is the session dict: state['trees'] holds what the tutor's tools keep
    between calls (such as the trees shown so far), state['progress'] is the
    student record.  Returns (result_text, payload or None).  Raises ToolError
    for bad input.
    """
    if name in _TOPIC_TOOLS:
        return topic.run(name, args, state)

    if name == "save_progress":
        state["progress"] = {k: args.get(k) for k in
                             ("modules_done", "now_in", "mistakes_seen", "objectives_met", "notes")}
        return "Saved.", None

    if name == "start_module":
        n = int(args["module"])
        if n not in intros.MODULES:
            raise ToolError(f"No module {n}. Modules: {sorted(intros.MODULES)}.")
        return intros.note(n), {"intro": n}

    if name == "calculate":
        return calculate(str(args["expression"])), None

    if name == "show_plot" and _PLOTS:
        if args.get("plot") not in _PLOTS:
            raise ToolError(f"Unknown plot {args.get('plot')!r}. Plots: {sorted(_PLOTS)}.")
        # A tutor whose make_plot takes the session state too (for data the student fetched) gets it.
        if len(inspect.signature(topic.make_plot).parameters) > 1:
            return topic.make_plot(args, state)
        return topic.make_plot(args)

    raise ToolError(f"Unknown tool {name!r}.")
