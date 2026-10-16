"""The assumptions grid as a CSV, so the numbers can move without the rest.

A bundle holds two very different kinds of thing. The classification, the
year-0 balances, the history, the guidance and the citations are slow-moving --
settled once and rarely touched. The forecast numbers are the opposite: they are
the whole point of the exercise and they change every time someone disagrees.

So the numbers live in a CSV of their own. Edit it, rebuild, and the pages
follow. Everything else stays in ``bundle.json`` where it is not in the way.

    row,key,unit,Y1,Y2,Y3,Y4,Y5,Terminal
    sales_growth,,%,4.5,6.5,6.0,4.5,3.5,3.0
    sales_to_net_ppe,,x,5.25,5.60,5.90,6.15,6.30,6.30
    operating_assets,inventories,%,20.9,20.5,20.0,19.7,19.5,19.5
    wacc,,%,8.0

Rates in percent and turnovers as multiples, with the unit named on every row so
a reader never has to guess whether 8.0 means eight percent or eight times. A
single-valued row carries one number and stops; Excel renders that as a short
row, which is exactly what it is.

Lines beginning with ``#`` are ignored, so you can annotate freely. Note that
rewriting the file from a bundle does not carry your annotations across -- put
anything you want to keep in the bundle's ``guidance`` instead, where it reaches
the assumptions page.
"""

import csv

from dcf_engine import N_EXPLICIT, SCALAR_DRIVERS

SIDES = ("operating_assets", "operating_liabilities")

#: Single-valued rows, and where each one lives in the bundle.
SINGLES = {
    "wacc": (("rates", "wacc"), "%"),
    "nol_limitation": (("rates", "nol_limitation"), "%"),
    "opening_nol": (("base", "nol"), "n"),
    "diluted_shares": (("meta", "diluted_shares"), "n"),
}

UNITS = {
    "sales_growth": "%",
    "ebitda_margin": "%",
    "sales_to_net_ppe": "x",
    "depreciation_rate": "%",
    "cash_tax_rate": "%",
}

HEADER = ["row", "key", "unit"] + [f"Y{t}" for t in range(1, N_EXPLICIT + 1)] \
    + ["Terminal"]


def _to_number(text, unit, where):
    try:
        value = float(str(text).strip())
    except (TypeError, ValueError):
        raise ValueError(f"{where}: {text!r} is not a number") from None
    return value / 100.0 if unit == "%" else value


#: Significant figures written out. Six is what you would type; a ratio derived
#: from an actual balance carries more, and truncating it moves the answer in a
#: company whose enterprise value is near zero. Eight keeps typed numbers short
#: -- 4.5 stays 4.5 -- while making the loss immaterial.
SIGFIGS = 8


def _from_number(value, unit):
    if value is None:
        return ""
    shown = value * 100.0 if unit == "%" else value
    return f"{shown:.{SIGFIGS}g}"


def write_assumptions_csv(bundle, path, comments=True):
    """Write the current grid. Returns the path."""
    a = bundle["assumptions"]
    rows = []

    if comments:
        rows.append(["# every number here is editable; rebuild to see it land"])
        rows.append(["# unit: % is a percent, x is a multiple, n is a plain number"])
    rows.append(HEADER)

    for name in SCALAR_DRIVERS:
        unit = UNITS[name]
        spec = a[name]
        rows.append([name, "", unit]
                    + [_from_number(v, unit) for v in spec["explicit"]]
                    + [_from_number(spec["terminal"], unit)])

    for side in SIDES:
        for key, spec in a[side].items():
            rows.append([side, key, "%"]
                        + [_from_number(v, "%") for v in spec["explicit"]]
                        + [_from_number(spec["terminal"], "%")])

    if comments:
        rows.append([])
        rows.append(["# one value each"])
    for name, (where, unit) in SINGLES.items():
        section, field = where
        rows.append([name, "", unit,
                     _from_number(bundle[section].get(field), unit)])

    with open(path, "w", newline="", encoding="utf-8") as fh:
        # Unix line endings. csv.writer defaults to CRLF, which Excel is happy
        # with but sed, grep and git diffs are not -- and this is a file people
        # edit with ordinary text tools.
        csv.writer(fh, lineterminator="\n").writerows(rows)
    return path


def read_assumptions_csv(path):
    """Parse the grid into ``{"grid": {...}, "singles": {...}}``."""
    grid, singles = {}, {}

    with open(path, newline="", encoding="utf-8") as fh:
        for n, raw in enumerate(csv.reader(fh), start=1):
            if not raw or not raw[0].strip() or raw[0].lstrip().startswith("#"):
                continue
            if raw[0].strip() == "row":
                continue                        # the header
            if len(raw) < 4:
                raise ValueError(
                    f"{path} line {n}: a row needs at least "
                    f"'row,key,unit,value', got {raw!r}")

            name, key, unit = raw[0].strip(), raw[1].strip(), raw[2].strip()
            values = [c for c in raw[3:] if str(c).strip() != ""]
            where = f"{path} line {n} ({name}{'/' + key if key else ''})"

            if name in SINGLES:
                if len(values) != 1:
                    raise ValueError(f"{where}: expected one value, got {len(values)}")
                singles[name] = _to_number(values[0], unit, where)
                continue

            if len(values) != N_EXPLICIT + 1:
                raise ValueError(
                    f"{where}: expected {N_EXPLICIT} explicit years plus a "
                    f"terminal value, got {len(values)}")
            numbers = [_to_number(v, unit, where) for v in values]
            grid[(name, key)] = {"explicit": numbers[:N_EXPLICIT],
                                 "terminal": numbers[N_EXPLICIT]}
    return {"grid": grid, "singles": singles}


def apply_assumptions_csv(bundle, path):
    """Return ``bundle`` with its numbers replaced by the CSV's.

    Guidance, citations, rationales, the classification and the year-0 balances
    are untouched -- the CSV carries numbers and nothing else.

    Every row the bundle expects must be present. A missing row is an error
    rather than a silent fall-back to the old value, because a forecast that
    quietly kept a number you thought you had changed is worse than one that
    refuses to build.

    The CSV is authoritative for the numbers once it exists: applying it gives
    exactly what it says, to the precision it carries. Writing it out, applying
    it and writing it again is stable.
    """
    import copy

    parsed = read_assumptions_csv(path)
    grid, singles = parsed["grid"], parsed["singles"]
    out = copy.deepcopy(bundle)
    a = out["assumptions"]

    wanted = {(name, "") for name in SCALAR_DRIVERS}
    for side in SIDES:
        wanted |= {(side, key) for key in a[side]}

    missing = sorted(wanted - set(grid))
    if missing:
        raise ValueError(
            f"{path} is missing {len(missing)} row(s): "
            + ", ".join(f"{n}{'/' + k if k else ''}" for n, k in missing))
    unknown = sorted(set(grid) - wanted)
    if unknown:
        raise ValueError(
            f"{path} has {len(unknown)} row(s) the bundle does not know: "
            + ", ".join(f"{n}{'/' + k if k else ''}" for n, k in unknown))

    for (name, key), values in grid.items():
        spec = a[name] if not key else a[name][key]
        spec["explicit"] = values["explicit"]
        spec["terminal"] = values["terminal"]

    for name, value in singles.items():
        section, field = SINGLES[name][0]
        out[section][field] = value

    return out


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) != 3:
        raise SystemExit("usage: dcf_assumptions.py <bundle.json> <assumptions.csv>")
    with open(sys.argv[1], encoding="utf-8") as fh:
        print(write_assumptions_csv(json.load(fh), sys.argv[2]))
