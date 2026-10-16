"""Write the valuation page: one file, four tabs.

Line items is the classification. Forecasts is a section per driver on how to
choose it, with the quoted evidence. Baseline is the grid of suggested numbers
beside the history, every cell editable. DCF is the answer -- forecast, bridge,
sensitivity, driver ranking -- and revalues as the Baseline is edited.

Every figure is first rendered here from ``dcf_engine``, so the page shows the
engine's numbers before any script runs. The revaluing is done by ``page.js``, a
port of the engine; it is held to the engine by tests/test_page_js.py and by a
check the page runs on itself against the figures written into it.

The live-reload poller is injected only when ``live=True``, which is the watch
loop, never the artifact you send someone.

No network references of any kind -- it has to open in a lab container.
"""

import hashlib
import html
import json
import os
import re

from dcf_engine import (N_EXPLICIT, PERPETUITY_YEAR, TRANSITION_YEAR,
                        driver_ranking, run_model, sensitivity_axes,
                        sensitivity_grid)

HERE = os.path.dirname(os.path.abspath(__file__))
STYLES = os.path.join(HERE, "styles.css")
TEMPLATE = os.path.join(HERE, "page.html")
SCRIPT = os.path.join(HERE, "page.js")

#: Injected only in watch mode. It asks the server whether the file it is
#: looking at has changed, and reloads if so -- no arithmetic, and absent from
#: anything anyone receives.
LIVE_RELOAD = """<script>
(function () {
  var seen = null;
  function check() {
    return fetch(location.href, { method: "HEAD", cache: "no-store" })
      .then(function (r) {
        var stamp = r.headers.get("Last-Modified") || r.headers.get("ETag");
        if (!stamp) return;
        if (seen && stamp !== seen) location.reload();
        seen = stamp;
      })
      .catch(function () {});
  }
  // Seed immediately rather than on the first tick. Otherwise a rebuild that
  // lands between load and that tick is recorded as the baseline and the page
  // never reloads -- which is precisely what happens when you rebuild straight
  // after opening the page.
  check();
  setInterval(check, 1000);
})();
</script>"""

SCALAR_ROWS = [
    ("group", "Growth and margin"),
    ("sales_growth", "Sales growth", "pct"),
    ("ebitda_margin", "EBITDA margin", "pct"),
    ("group", "Property, plant and equipment"),
    ("sales_to_net_ppe", "Next-year sales / net PP&E", "mult"),
    ("depreciation_rate", "Depreciation / prior net PP&E", "pct"),
]

SCHEDULE_ROWS = [
    ("sales", "Sales", "num"),
    ("ebitda", "EBITDA", "num"),
    ("depreciation", "Depreciation", "num"),
    ("ebit", "EBIT", "num"),
    ("nol_open", "NOL carryforward, opening", "num"),
    ("nol_used", "NOL used", "num"),
    ("taxable_income", "Taxable income", "num"),
    ("tax", "Cash taxes", "num"),
    ("effective_tax_rate", "Effective tax rate", "pct"),
    ("net_ppe", "Net PP&E, closing", "num"),
    ("capex", "Capital expenditure", "num"),
    ("nwc", "Net working capital, closing", "num"),
    ("delta_nwc", "Investment in working capital", "num"),
    ("fcf", "Free cash flow", "num"),
    ("discount_factor", "Discount factor", "factor"),
    ("pv_fcf", "PV of free cash flow", "num"),
]


# --------------------------------------------------------------------------
# formatting
# --------------------------------------------------------------------------

def esc(text):
    return html.escape(str(text), quote=False)


def fmt(value, kind):
    if value is None:
        return "—"
    if kind == "pct":
        return f"{value * 100:,.1f}%"
    if kind == "mult":
        return f"{value:,.2f}×"
    if kind == "factor":
        return f"{value:,.4f}"
    if kind == "share":
        return f"{value:,.2f}"
    return f"{value:,.1f}" if abs(value) < 100 else f"{value:,.0f}"


def _labels(bundle):
    return {c["key"]: c["line"] for c in bundle.get("classification", [])
            if c.get("key")}


def _input_rows(bundle):
    """The assumption rows, in display order, as (key, label, kind, side)."""
    labels = _labels(bundle)
    rows = list(SCALAR_ROWS)
    rows.append(("group", "Operating assets, as a share of sales"))
    for key in bundle["assumptions"]["operating_assets"]:
        rows.append((key, labels.get(key, key), "pct", "operating_assets"))
    rows.append(("group", "Operating liabilities, as a share of sales"))
    for key in bundle["assumptions"]["operating_liabilities"]:
        rows.append((key, labels.get(key, key), "pct", "operating_liabilities"))
    rows.append(("group", "Taxes"))
    rows.append(("cash_tax_rate", "Cash tax rate on taxable income", "pct"))
    return rows


def _spec(bundle, row):
    a = bundle["assumptions"]
    return a[row[3]][row[0]] if len(row) > 3 else a[row[0]]


def _history_series(bundle, row):
    ratios = ((bundle.get("history") or {}).get("ratios") or {})
    if len(row) > 3:
        return (ratios.get(row[3]) or {}).get(row[0]) or {}
    return ratios.get(row[0]) or {}


# --------------------------------------------------------------------------
# tables
# --------------------------------------------------------------------------

UNIT = {"pct": "%", "mult": "x"}


def _shown(value, unit):
    """What an input box shows: percent drivers in percent, turnovers as
    multiples, at display precision unless the number carries more."""
    x = value * 100.0 if unit == "%" else value
    exact = round(x, 4)
    if unit == "n":
        return f"{exact:g}"
    plain = f"{x:.{2 if unit == 'x' else 1}f}"
    return plain if float(plain) == exact else f"{exact:g}"


def _input(path, unit, label, value, col=None):
    col_attr = "" if col is None else f" data-col='{col}'"
    return (f"<input inputmode='decimal' data-path='{path}' data-unit='{unit}'"
            f"{col_attr} aria-label='{html.escape(label, quote=True)}'"
            f" value='{_shown(value, unit)}'>")


def _inputs_table(bundle):
    """The Baseline grid: history shaded, every forecast cell an input."""
    years = ((bundle.get("history") or {}).get("years") or [])[-5:]
    span = len(years) + N_EXPLICIT + 2
    heads = [f"Year {t}" for t in range(1, N_EXPLICIT + 1)] + ["Terminal"]

    out = ["<table><thead><tr><th>Assumption</th>"]
    out += [f"<th>{esc(y)}</th>" for y in years]
    out += [f"<th class='fc'>{h}</th>" for h in heads]
    out.append("</tr></thead><tbody>")

    for row in _input_rows(bundle):
        if row[0] == "group":
            out.append(f"<tr class='group'><td colspan='{span}'>{esc(row[1])}</td></tr>")
            continue
        key, label, kind = row[0], row[1], row[2]
        unit = UNIT[kind]
        path = "assumptions." + (f"{row[3]}.{key}" if len(row) > 3 else key)
        history, spec = _history_series(bundle, row), _spec(bundle, row)
        out.append(f"<tr><td>{esc(label)}</td>")
        for year in years:
            value = history.get(year, history.get(str(year)))
            out.append(f"<td class='hist'>{fmt(value, kind)}</td>")
        values = list(spec["explicit"]) + [spec["terminal"]]
        for c, value in enumerate(values):
            out.append(f"<td class='fc'>{_input(path, unit, f'{label}, {heads[c]}', value, c)}"
                       f"<span class='u'>{'%' if unit == '%' else '×'}</span></td>")
        out.append("</tr>")

    return "".join(out) + "</tbody></table>"


def _rates_block(bundle):
    """The single-valued inputs, editable, and terminal growth read off the grid."""
    rates, meta, base = bundle["rates"], bundle["meta"], bundle["base"]
    fields = [
        ("WACC", "rates.wacc", "%", rates["wacc"]),
        ("NOL limitation", "rates.nol_limitation", "%", rates.get("nol_limitation", 0.80)),
        ("opening NOL", "base.nol", "n", float(base.get("nol") or 0.0)),
        ("diluted shares", "meta.diluted_shares", "n", meta.get("diluted_shares") or 0.0),
    ]
    parts = [f"{label} {_input(path, unit, label, value)}"
             + ("<span class='u'>%</span>" if unit == "%" else "")
             for label, path, unit, value in fields]
    growth = fmt(bundle["assumptions"]["sales_growth"]["terminal"], "pct")
    parts.append(f"terminal growth <b id='tg'>{growth}</b> (the terminal sales growth)")
    return "<p class='rates'>" + " &nbsp;·&nbsp; ".join(parts) + "</p>"


def _schedule_table(result):
    out = ["<table><thead><tr><th>Forecast</th>"]
    for row in result["schedule"]:
        label = f"Year {row['year']}"
        if row["year"] == TRANSITION_YEAR:
            label += " · transition"
        elif row["year"] == PERPETUITY_YEAR:
            label += " · perpetuity"
        out.append(f"<th class='fc'>{esc(label)}</th>")
    out.append("</tr></thead><tbody>")

    for key, label, kind in SCHEDULE_ROWS:
        cls = " class='total'" if key == "fcf" else ""
        out.append(f"<tr{cls}><td>{esc(label)}</td>")
        for row in result["schedule"]:
            out.append(f"<td>{fmt(row[key], kind)}</td>")
        out.append("</tr>")
        if key == "fcf":
            out.append(_fcf_growth_row(result["schedule"]))
    return "".join(out) + "</tbody></table>"


def _fcf_growth_row(rows):
    """Year-on-year growth in free cash flow, read off the line above.

    Greyed because it is shown rather than used: nothing downstream reads it.
    It earns its place by making the terminal year visible -- the dip into year
    6 is the balance sheet stepping up to support growth for ever, and the
    constant g from year 6 on is what says the perpetuity has already begun.
    """
    cells = ["<td>&mdash;</td>"]
    for prev, cur in zip(rows, rows[1:]):
        prior = prev["fcf"]
        cells.append(f"<td>{fmt(cur['fcf'] / prior - 1.0, 'pct')}</td>"
                     if prior > 0 else "<td>&mdash;</td>")
    return ("<tr class='derived'><td>Free cash flow growth</td>"
            + "".join(cells) + "</tr>")


def _bridge_table(bundle, result):
    shares = bundle["meta"].get("diluted_shares")
    out = ["<table><tbody>"]

    def line(label, value, kind="num", total=False):
        cls = " class='total'" if total else ""
        out.append(f"<tr{cls}><td>{esc(label)}</td>"
                   f"<td>{fmt(value, kind)}</td></tr>")

    line("PV of free cash flow, years 1 to 6", result["pv_explicit"])
    line("Terminal value at the end of year 6", result["terminal_value"])
    line("PV of the terminal value", result["pv_terminal"])
    for i, item in enumerate(result["bridge"]):
        line(item["label"], item["amount"], total=(i == 0))
    line("Equity value", result["equity_value"], total=True)
    line("Diluted shares", shares)
    line("Value per share", result["value_per_share"], "share", total=True)
    return "".join(out) + "</tbody></table>"


def _sensitivity_table(bundle):
    waccs, growths = sensitivity_axes(bundle)
    grid = sensitivity_grid(bundle, waccs, growths)
    base_wacc = bundle["rates"]["wacc"]
    base_growth = bundle["assumptions"]["sales_growth"]["terminal"]

    out = ["<table><thead><tr><th>WACC \\ terminal growth</th>"]
    out += [f"<th>{fmt(g, 'pct')}</th>" for g in growths]
    out.append("</tr></thead><tbody>")
    for i, wacc in enumerate(waccs):
        out.append(f"<tr><td>{fmt(wacc, 'pct')}</td>")
        for j, growth in enumerate(growths):
            here = (abs(wacc - base_wacc) < 1e-12
                    and abs(growth - base_growth) < 1e-12)
            cls = "sens here" if here else "sens"
            out.append(f"<td class='{cls}'>{fmt(grid[i][j], 'share')}</td>")
        out.append("</tr>")
    return "".join(out) + "</tbody></table>"


def _classification_table(bundle):
    rows = bundle.get("classification") or []
    if not rows:
        return "<p class='note'>No classification was recorded.</p>"
    out = ["<table><thead><tr><th>Reported line</th><th>Bucket</th>"
           "<th>Why</th></tr></thead><tbody>"]
    for c in rows:
        out.append(f"<tr><td>{esc(c['line'])}</td>"
                   f"<td class='wrap'>{esc(c['bucket'])}</td>"
                   f"<td class='wrap'>{esc(c.get('note') or '')}</td></tr>")
    return "".join(out) + "</tbody></table>"


def _history_strip(bundle, row, ranked=None):
    """The driver's own history, the suggested path, and what it is worth."""
    history = _history_series(bundle, row)
    years = ((bundle.get("history") or {}).get("years") or [])[-6:]
    kind = row[2]
    seen = [(y, history.get(y, history.get(str(y)))) for y in years]
    seen = [(y, v) for y, v in seen if v is not None]

    parts = []
    if seen:
        parts.append("History " + ", ".join(
            f"{y} <b>{fmt(v, kind)}</b>" for y, v in seen))
    spec = _spec(bundle, row)
    parts.append("Suggested " + ", ".join(
        f"<b>{fmt(v, kind)}</b>" for v in spec["explicit"])
        + f", then <b>{fmt(spec['terminal'], kind)}</b> forever")
    entry = (ranked or {}).get((row[0], row[3] if len(row) > 3 else None))
    if entry and entry["span_share"] is not None:
        parts.append(f"Moving it {entry['shift']} each way moves the value "
                     f"<b>{entry['span_share'] * 100:,.1f}%</b>")
    return "<p class='strip'>" + " &nbsp;·&nbsp; ".join(parts) + "</p>"


def _citations(spec):
    out = []
    for c in spec.get("citations") or []:
        who = ", ".join(x for x in (c.get("speaker"), c.get("source")) if x)
        out.append(f"<blockquote>&ldquo;{esc(c['quote'])}&rdquo;"
                   + (f"<cite>{esc(who)}</cite>" if who else "")
                   + "</blockquote>")
    return "".join(out)


def _ranking(bundle):
    """Driver spans, keyed by (name, key). Computed once per page."""
    return {(r["name"], r["key"]): r for r in driver_ranking(bundle)}


def _ranking_table(bundle, ranked):
    """Which arguments are worth having, measured rather than asserted.

    Spans are shown as a share of value, never as a level, so the page can say
    what matters without telling you the answer.
    """
    rows = sorted(ranked.values(), key=lambda r: r["span_share"] or 0, reverse=True)
    if not rows:
        return "<p class='note'>No driver could be varied without breaking the "\
               "model, so there is nothing to rank.</p>"
    widest = rows[0]["span_share"] or 1.0

    out = ["<table><thead><tr><th>Driver</th><th>Moved</th>"
           "<th>Moves the value by</th><th></th></tr></thead><tbody>"]
    for row in rows:
        share = row["span_share"] or 0.0
        width = max(2, round(100 * share / widest))
        out.append(
            f"<tr><td>{esc(row['driver'])}</td>"
            f"<td>{esc(row['shift'])}</td>"
            f"<td>{share * 100:,.1f}%</td>"
            f"<td class='bar'><span style='width:{width}%'></span></td></tr>")
    return "".join(out) + "</tbody></table>"


def _guidance(bundle, ranked=None):
    """The advisory document: how to choose each driver, not a defence of one."""
    out = []
    for row in _input_rows(bundle):
        if row[0] == "group":
            continue
        spec = _spec(bundle, row)
        body = spec.get("guidance") or spec.get("rationale")
        if not body:
            continue
        out.append(f"<section class='guide'><h3>{esc(row[1])}</h3>")
        out.append(_history_strip(bundle, row, ranked))
        out.append(f"<p class='how'>{esc(body)}</p>")
        out.append(_citations(spec))
        if spec.get("guidance") and spec.get("rationale"):
            out.append(f"<p class='how'><i>Why the suggestion sits where it "
                       f"does.</i> {esc(spec['rationale'])}</p>")
        out.append("</section>")
    return "".join(out) or (
        "<p class='note'>No guidance was recorded with these assumptions. The "
        "numbers above are then bare suggestions with nothing behind them, which "
        "is not enough to choose from.</p>")


def _warnings(result):
    return "".join(f"<li>{esc(w)}</li>" for w in result["warnings"])


def _history_notes(bundle):
    notes = (bundle.get("history") or {}).get("notes") or []
    if not notes:
        return ""
    return "<h2>What the history showed</h2>" + "".join(
        f"<p class='note body'>{esc(n)}</p>" for n in notes)


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def _styles():
    with open(STYLES, encoding="utf-8") as fh:
        return fh.read()


def _header_bits(bundle):
    meta = bundle["meta"]
    company = meta.get("company", "Company")
    if meta.get("ticker"):
        company += f" ({meta['ticker']})"
    subtitle = (
        f"Fiscal {meta.get('fiscal_year_0', '')}"
        + (f" ended {meta['fiscal_year_end']}" if meta.get("fiscal_year_end") else "")
        + f" is year 0. All figures in "
        f"{meta.get('units', 'the units of the statements')}."
    )
    return company, subtitle


def _render(template_path, tokens):
    """Fill the template's tokens in one pass, so nothing substituted in --
    a quote, a company name, the script -- is ever itself scanned for tokens."""
    with open(template_path, encoding="utf-8") as fh:
        page = fh.read()
    missing = sorted(set(re.findall(r"__([A-Z_]+)__", page)) - {t.strip("_") for t in tokens})
    if missing:
        raise RuntimeError(f"template tokens left unfilled: {missing}")
    return re.sub(r"__([A-Z_]+)__", lambda m: tokens[f"__{m.group(1)}__"], page)


def _write(page, out_path):
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(page)
    return out_path


def _page_data(bundle, result):
    """What page.js needs: the numbers, and the engine's answer to check against."""
    a = bundle["assumptions"]

    def numbers(spec):
        return {"explicit": list(spec["explicit"]), "terminal": spec["terminal"]}

    assumptions = {name: numbers(a[name]) for name in
                   ("sales_growth", "ebitda_margin", "sales_to_net_ppe",
                    "depreciation_rate", "cash_tax_rate")}
    for side in ("operating_assets", "operating_liabilities"):
        assumptions[side] = {k: numbers(v) for k, v in a[side].items()}

    model = {
        "base": bundle["base"],
        "assumptions": assumptions,
        "rates": {"wacc": bundle["rates"]["wacc"],
                  "nol_limitation": bundle["rates"].get("nol_limitation", 0.80)},
        "meta": {"diluted_shares": bundle["meta"].get("diluted_shares"),
                 "units": bundle["meta"].get("units", "")},
    }
    digest = hashlib.sha1(json.dumps(model, sort_keys=True).encode()).hexdigest()[:12]
    slug = (bundle["meta"].get("ticker") or "company").lower()
    return {
        "bundle": model,
        "store": f"dcf-{slug}-{digest}",
        "check": {"ev_ops": result["ev_ops"], "equity_value": result["equity_value"],
                  "value_per_share": result["value_per_share"],
                  "fcf": [r["fcf"] for r in result["schedule"]]},
    }


def _json_for_script(data):
    # Inside <script>, "</" would end the element early.
    return json.dumps(data).replace("</", "<\\/")


def build_page(bundle, out_path, live=False):
    """The one page: Line items, Forecasts, Baseline and DCF tabs."""
    result = run_model(bundle)
    ranked = _ranking(bundle)
    company, subtitle = _header_bits(bundle)
    meta = bundle["meta"]
    with open(SCRIPT, encoding="utf-8") as fh:
        script = fh.read()
    page = _render(TEMPLATE, {
        "__STYLES__": _styles(),
        "__TITLE__": esc(f"{meta.get('ticker') or meta.get('company', 'Company')} Valuation"),
        "__COMPANY__": esc(company),
        "__SUBTITLE__": esc(subtitle),
        "__CLASSIFICATION__": _classification_table(bundle),
        "__GUIDANCE__": _guidance(bundle, ranked),
        "__HISTORY_NOTES__": _history_notes(bundle),
        "__BASELINE__": _inputs_table(bundle),
        "__RATES__": _rates_block(bundle),
        "__WARNINGS__": _warnings(result),
        "__EV__": fmt(result["ev_ops"], "num"),
        "__EQUITY__": fmt(result["equity_value"], "num"),
        "__PER_SHARE__": fmt(result["value_per_share"], "share"),
        "__SCHEDULE__": _schedule_table(result),
        "__BRIDGE__": _bridge_table(bundle, result),
        "__SENSITIVITY__": _sensitivity_table(bundle),
        "__RANKING__": _ranking_table(bundle, ranked),
        "__WACC_NOTE__": esc(bundle["rates"].get("wacc_derivation")
                             or "No derivation was recorded for the discount rate."),
        "__DATA__": _json_for_script(_page_data(bundle, result)),
        "__SCRIPT__": script,
        "__LIVE__": LIVE_RELOAD if live else "",
    })
    return _write(page, out_path)


def build_pages(bundle, out_dir, slug=None, live=False):
    """Write ``<slug>.html`` into ``out_dir`` and return its path."""
    os.makedirs(out_dir, exist_ok=True)
    slug = slug or (bundle["meta"].get("ticker") or "company").lower()
    return build_page(bundle, os.path.join(out_dir, f"{slug}.html"), live=live)


if __name__ == "__main__":
    import argparse
    import json

    from dcf_assumptions import apply_assumptions_csv

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bundle")
    ap.add_argument("out_dir")
    ap.add_argument("--csv", help="assumptions CSV to overlay onto the bundle")
    ap.add_argument("--slug", help="file-name stem; defaults to the ticker")
    ap.add_argument("--live", action="store_true",
                    help="inject the reload poller (watch loop only, never a "
                         "page you send someone)")
    ap.add_argument("--open", dest="open_page", action="store_true",
                    help="open the page when it is written")
    ap.add_argument("--port", type=int, default=8791,
                    help="serve.py's port, so --open uses the URL that "
                         "live-reloads rather than a file:// path")
    args = ap.parse_args()

    with open(args.bundle, encoding="utf-8") as fh:
        bundle = json.load(fh)
    if args.csv:
        bundle = apply_assumptions_csv(bundle, args.csv)

    written = build_pages(bundle, args.out_dir, slug=args.slug, live=args.live)
    print(written)

    if args.open_page:
        from dcf_open import open_page
        open_page(written, port=args.port)
