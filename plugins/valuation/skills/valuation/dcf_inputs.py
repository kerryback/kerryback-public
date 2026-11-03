"""Find the inputs, from a folder or from filenames.

The folder is either one ``dcf_fetch.py`` wrote or one the user staged by hand.
This reports what it found and what it did not, so the gaps are visible before
any number is computed rather than after.

Two ways in, and they do the same thing:

    inventory("~/data/jbss")                       a folder, searched
    inventory(financials="jbss.xlsx",              filenames, given
              filings=["10k/FY2026.htm"])

A folder is searched for the shapes these bundles actually arrive in --
``*financials*.xlsx`` beside ``10k/``, ``transcripts/`` and ``press_releases/``,
or loose statement CSVs. Nothing but the statements is required; with no text
the forecast rests on history alone, and the report says so.
"""

import glob
import os

STATEMENT_PATTERNS = [
    "*financials*10k*.xlsx", "*financials*.xlsx", "*financials*.xls",
    "financials.xlsx", "*.xlsx",
]

TEXT_FOLDERS = {
    "filings": ["10k", "10-k", "filings", "sec"],
    "transcripts": ["transcripts", "calls", "earnings_calls"],
    "press_releases": ["press_releases", "press", "releases"],
}

STATEMENT_CSVS = {
    "income": ["*income*annual*.csv", "*income*.csv"],
    "balance": ["*balance*annual*.csv", "*balance*.csv"],
    "cashflow": ["*cashflow*annual*.csv", "*cash_flow*.csv", "*cashflow*.csv"],
}


def _first(folder, patterns):
    for pattern in patterns:
        hits = sorted(glob.glob(os.path.join(folder, pattern)))
        hits = [h for h in hits if not os.path.basename(h).startswith("~$")]
        if hits:
            return hits[0]
    return None


def _folder(root, names):
    for name in names:
        path = os.path.join(root, name)
        if os.path.isdir(path):
            return path
    return None


def inventory(folder=None, financials=None, filings=None, transcripts=None,
              press_releases=None):
    """Return what was found, what is missing, and whether it is enough.

    ``{"financials": path|None, "statement_csvs": {...}, "filings": [...],
       "transcripts": [...], "press_releases": [...], "missing": [...],
       "sufficient": bool}``
    """
    found = {"financials": None, "statement_csvs": {}, "filings": [],
             "transcripts": [], "press_releases": [], "root": None}

    if folder:
        root = os.path.abspath(os.path.expanduser(folder))
        if not os.path.isdir(root):
            raise ValueError(f"{folder} is not a folder")
        found["root"] = root
        found["financials"] = _first(root, STATEMENT_PATTERNS)
        for key, patterns in STATEMENT_CSVS.items():
            hit = _first(root, patterns) or _first(os.path.join(root, "yahoo_csv"),
                                                   patterns)
            if hit:
                found["statement_csvs"][key] = hit
        for key, names in TEXT_FOLDERS.items():
            sub = _folder(root, names)
            if sub:
                found[key] = sorted(
                    os.path.join(sub, n) for n in os.listdir(sub)
                    if not n.startswith("."))

    if financials:
        found["financials"] = os.path.abspath(os.path.expanduser(financials))
    for key, given in (("filings", filings), ("transcripts", transcripts),
                       ("press_releases", press_releases)):
        if given:
            found[key] = [os.path.abspath(os.path.expanduser(p)) for p in given]

    missing = []
    if not found["financials"] and not found["statement_csvs"]:
        missing.append("financial statements")
    for key in ("filings", "transcripts", "press_releases"):
        if not found[key]:
            missing.append(key.replace("_", " "))

    found["missing"] = missing
    found["sufficient"] = bool(found["financials"] or found["statement_csvs"])
    return found


def describe(found):
    """A short report to show the user at phase 0."""
    lines = []
    if found.get("root"):
        lines.append(f"Looked in {found['root']}")
    if found["financials"]:
        lines.append(f"  statements    {os.path.basename(found['financials'])}")
    for key, path in found.get("statement_csvs", {}).items():
        lines.append(f"  {key + ' csv':<13} {os.path.basename(path)}")
    for key in ("filings", "transcripts", "press_releases"):
        n = len(found[key])
        if n:
            label = key.replace("_", " ")
            lines.append(f"  {label:<13} {n} file{'s' if n != 1 else ''}")
    if found["missing"]:
        lines.append("  not found:    " + ", ".join(found["missing"]))
    if not found["sufficient"]:
        lines.append("")
        lines.append("Without statements there is nothing to value. Fetch them "
                     "with dcf_fetch.py, point me at a folder holding a financials "
                     "workbook, or name the file.")
    elif "transcripts" in found["missing"] and "filings" in found["missing"]:
        lines.append("")
        lines.append("No text at all, so the forecast will rest on history alone. "
                     "The assumptions page will say so.")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        raise SystemExit("usage: dcf_inputs.py <folder>")
    print(describe(inventory(sys.argv[1])))
