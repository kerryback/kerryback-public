"""Historical driver ratios, computed from a script rather than read off a page.

Two jobs.

``check_footing`` guards the classification gate. Every reported balance-sheet
line has to land in exactly one bucket, and the buckets have to add back to the
reported total. A line that is on the statement and not in the table is an
error, not an omission -- that is precisely how a real liability goes missing
from a valuation.

``historical_ratios`` computes each driver the same way the forecast does, so
that history and forecast are comparable columns of one table. Working-capital
items are divided by their own year's sales. Net PP&E is the exception: it is
reported as a turnover on the *following* year's sales, because capacity is
built ahead of the sales it supports, so the final year carries no PP&E
turnover.

It also reports realised capex from the PP&E roll-forward, so the depreciation
rate and the capex the model implies can be checked against what the company
actually spent.
"""

BALANCE_BUCKETS = {
    "net_ppe", "operating_asset", "operating_liability",
    "nonoperating_asset", "debt_claim", "equity_claim", "excluded",
}


def check_footing(classification, balance_lines, reported_total, tolerance=0.01):
    """Raise unless every reported line is classified exactly once.

    ``balance_lines`` maps line label to the year-0 value. ``reported_total`` is
    the statement's own total for the same set of lines.
    """
    classified = [c["line"] for c in classification]

    duplicates = sorted({line for line in classified
                         if classified.count(line) > 1})
    if duplicates:
        raise ValueError(
            f"these lines are classified more than once: {duplicates}")

    bad = sorted({c["line"] for c in classification if c["line"] not in balance_lines})
    if bad:
        raise ValueError(
            f"classified but not on the statement: {bad}. Either the label is "
            f"misspelled or the line belongs to a different statement.")

    unclassified = sorted(set(balance_lines) - set(classified))
    if unclassified:
        missing = sum(balance_lines[line] for line in unclassified)
        raise ValueError(
            f"{len(unclassified)} reported line(s) are not classified, worth "
            f"{missing:,.1f} in total: {unclassified}. Every line gets a bucket "
            f"-- 'excluded' is a bucket. Leaving one out drops it silently.")

    total = sum(balance_lines[line] for line in classified)
    if abs(total - reported_total) > tolerance:
        raise ValueError(
            f"classified lines sum to {total:,.2f} but the statement reports "
            f"{reported_total:,.2f}, a difference of {total - reported_total:,.2f}")


def _series(lines, label):
    return lines.get(label, {})


def historical_ratios(financials, classification, sales_line,
                      ebitda_line=None, depreciation_line=None,
                      tax_line=None, pretax_line=None):
    """Every driver, year by year, plus the notes a forecaster needs to see."""
    years = list(financials["years"])
    lines = financials["lines"]
    sales = _series(lines, sales_line)
    if not sales:
        raise ValueError(f"sales line '{sales_line}' is not in the statements")

    ebitda = _series(lines, ebitda_line) if ebitda_line else {}
    depreciation = _series(lines, depreciation_line) if depreciation_line else {}
    taxes = _series(lines, tax_line) if tax_line else {}
    pretax = _series(lines, pretax_line) if pretax_line else {}

    by_bucket = {}
    for entry in classification:
        by_bucket.setdefault(entry["bucket"], []).append(entry)

    ppe_label = next((e["line"] for e in by_bucket.get("net_ppe", [])), None)
    net_ppe = _series(lines, ppe_label) if ppe_label else {}

    def next_sales(year):
        i = years.index(year)
        return sales.get(years[i + 1]) if i + 1 < len(years) else None

    def against_own_sales(series):
        out = {}
        for year in years:
            own, value = sales.get(year), series.get(year)
            if own and value is not None:
                out[year] = value / own
        return out

    ratios = {
        "sales_growth": {},
        "ebitda_margin": {},
        "sales_to_net_ppe": {},
        "depreciation_rate": {},
        "cash_tax_rate": {},
        "realized_capex": {},
        "operating_assets": {},
        "operating_liabilities": {},
    }

    for i, year in enumerate(years):
        if i and sales.get(years[i - 1]):
            ratios["sales_growth"][year] = sales[year] / sales[years[i - 1]] - 1
        if sales.get(year) and ebitda.get(year) is not None:
            ratios["ebitda_margin"][year] = ebitda[year] / sales[year]
        if net_ppe.get(year):
            nxt = next_sales(year)
            if nxt:
                ratios["sales_to_net_ppe"][year] = nxt / net_ppe[year]
        if i and net_ppe.get(years[i - 1]) and depreciation.get(year) is not None:
            prior = net_ppe[years[i - 1]]
            ratios["depreciation_rate"][year] = depreciation[year] / prior
            if net_ppe.get(year) is not None:
                # NPPE(t) = NPPE(t-1) + capex - depreciation
                ratios["realized_capex"][year] = (
                    net_ppe[year] - prior + depreciation[year])
        if pretax.get(year) and taxes.get(year) is not None:
            ratios["cash_tax_rate"][year] = taxes[year] / pretax[year]

    for entry in by_bucket.get("operating_asset", []):
        key = entry.get("key", entry["line"])
        ratios["operating_assets"][key] = against_own_sales(
            _series(lines, entry["line"]))
    for entry in by_bucket.get("operating_liability", []):
        key = entry.get("key", entry["line"])
        ratios["operating_liabilities"][key] = against_own_sales(
            _series(lines, entry["line"]))

    notes = []
    loss_years = [y for y, m in ratios["ebitda_margin"].items() if m <= 0]
    if loss_years:
        notes.append(
            f"EBITDA was not positive in {', '.join(str(y) for y in sorted(loss_years))}. "
            f"A margin from a loss year is not a starting point for a forecast; "
            f"anchor on the profitable years or on what the company says about "
            f"recovery.")
    uncovered = [year for year in years
                 if ebitda.get(year) is not None
                 and depreciation.get(year) is not None
                 and ebitda[year] - depreciation[year] <= 0]
    if uncovered:
        notes.append(
            f"EBITDA did not cover depreciation in "
            f"{', '.join(str(y) for y in sorted(uncovered))}, so EBIT was not "
            f"positive even though EBITDA was. That is the case the NOL "
            f"carryforward exists for: check the tax footnote for the balance "
            f"and for a valuation allowance before assuming any shield.")
    if len(ratios["sales_growth"]) < 2:
        notes.append(
            "Fewer than two growth observations. There is not enough history "
            "here to anchor a growth forecast.")
    if ratios["realized_capex"] and ratios["depreciation_rate"]:
        avg_capex = sum(ratios["realized_capex"].values()) / len(ratios["realized_capex"])
        if avg_capex < 0:
            notes.append(
                "Average realised capex is negative over the historical window, "
                "which usually means asset sales or a restated PP&E line rather "
                "than genuine disinvestment. Check before forecasting.")
    if not net_ppe:
        notes.append(
            "No line is classified as net_ppe, so the sales-to-PP&E turnover and "
            "the depreciation rate have no historical anchor.")

    return {"years": years, "ratios": ratios, "notes": notes}
