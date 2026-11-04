"""Build the statements workbook from the XBRL statement pages of a run of 10-Ks.

Every 10-K on EDGAR carries its face statements as rendered XBRL pages (the
``R`` files listed in ``FilingSummary.xml``). Each page has the company's own
line labels, the XBRL concept behind each line, and two or three fiscal years.
Five 10-Ks therefore cover six or seven years, with every year but the oldest
reported more than once.

Each year is taken from the most recent 10-K that reports it, so the figures are
the latest restated ones -- right for valuation, wrong for backtesting a signal.
Lines are matched across filings by concept, not by label, because labels drift
and concepts mostly do not; where a concept changed and the label did not, the
two rows are merged back together.

The workbook has three sheets -- Income Statement, Balance Sheet, Cash Flow
Statement -- in $ thousands, with the source filing for each year in row 6 and
check rows at the foot that should be zero. ``dcf_load`` reads it as is.

Two repairs are made and both are marked in the cell they touch: a sign flipped
where one row's sign convention changed between filings and flipping it is the
only way the section foots, and a supplemental cash-flow line filled from an
older 10-K when the newer one stopped presenting it.
"""

import difflib
import re
from collections import Counter
from datetime import datetime

from bs4 import BeautifulSoup

UNIT = 1000.0               # parse_report returns $ millions; the workbook is in $ thousands
TOL = 6e-4                  # $ millions: half a thousand dollars
TYPES = (("Income Statement", "IS"), ("Balance Sheet", "BS"), ("Cash Flow Statement", "CF"))


# --------------------------------------------------------------------------
# one statement page
# --------------------------------------------------------------------------

def _num(text):
    text = text.replace("$", "").replace(",", "").strip()
    if not text:
        return None
    neg = text.startswith("(")
    try:
        value = float(text.strip("()"))
    except ValueError:
        return None
    return -value if neg else value


def parse_report(html):
    """One rendered XBRL statement page into ``(title, years, rows)``.

    Values come back in $ millions, shares in millions, per-share amounts as
    stated. A page that names no unit is in whole dollars.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="report")
    trs = table.find_all("tr")
    title = trs[0].th.get_text(" ", strip=True)

    scale = 1e-3 if "$ in Thousands" in title else 1.0 if "$ in Millions" in title else 1e-6
    shares = 1e-3 if "shares in Thousands" in title else 1.0 if "shares in Millions" in title else 1e-6

    years = []
    for tr in trs[:3]:
        heads = [th.get_text(" ", strip=True) for th in tr.find_all("th", class_="th")]
        heads = [h for h in heads if re.match(r"[A-Z][a-z]{2}\. \d", h)]
        if heads:
            years = [int(re.search(r"\d{4}", h)[0]) for h in heads]

    rows = []
    for tr in trs:
        td = tr.find_all("td")
        if not td or "pl" not in (td[0].get("class") or []):
            continue
        a = td[0].find("a")
        m = re.search(r"defref_([A-Za-z0-9-]+)_(\w+)", a["onclick"]) if a and a.get("onclick") else None
        concept = f"{m[1]}:{m[2]}" if m else td[0].get_text(strip=True)
        vals = {}
        for year, cell in zip(years, td[1:]):
            raw = cell.get_text(" ", strip=True)
            v = _num(raw.split(" ")[-1] if raw.startswith("$") else raw)
            if v is not None:
                vals[year] = v
        pershare = "PerShare" in concept
        is_shares = "Shares" in concept and not pershare and "Value" not in concept
        factor = 1.0 if pershare else shares if is_shares else scale
        rows.append(dict(
            concept=concept, label=td[0].get_text(" ", strip=True),
            abstract=concept.endswith("Abstract") or not vals,
            total=(tr.get("class") or [""])[0] in ("reu", "rou"),
            vals={y: v * factor for y, v in vals.items()},
            pershare=pershare, shares=is_shares))
    return title, years, rows


# --------------------------------------------------------------------------
# across filings
# --------------------------------------------------------------------------

def _keyed(rows):
    seen, out = Counter(), []
    for r in rows:
        seen[r["concept"]] += 1
        out.append(((r["concept"], seen[r["concept"]]), r))
    return out


def merge(pages):
    """``pages`` is ``[(filing_key, html), ...]``, newest filing first.

    Returns ``(years, source_by_year, [(key, row), ...])`` with rows in
    presentation order. A row a newer filing dropped keeps its place next to
    its old neighbour.
    """
    keys = [k for k, _ in pages]
    parsed = {k: _keyed(parse_report(html)[2]) for k, html in pages}
    src = {}
    for k in keys:
        for _, r in parsed[k]:
            for y in r["vals"]:
                src.setdefault(y, k)

    order, rows = [], {}
    for fk in keys:
        prev, seq = None, parsed[fk]
        for n, (k, r) in enumerate(seq):
            if k not in rows:
                rows[k] = dict(label=r["label"], abstract=r["abstract"], total=r["total"],
                               pershare=r["pershare"], shares=r["shares"], vals={}, alt={})
                if prev in order:
                    pos = order.index(prev) + 1
                else:
                    nxt = next((kk for kk, _ in seq[n + 1:] if kk in order), None)
                    pos = order.index(nxt) if nxt else len(order)
                order.insert(pos, k)
            for y, v in r["vals"].items():
                if src[y] == fk:
                    rows[k]["vals"][y] = v
            prev = k

    # A line the source filing does not present at all: remember the value from
    # the next-newest filing that has it. Whether to use it is decided later.
    present = {fk: {k for k, _ in parsed[fk]} for fk in keys}
    for fk in keys:
        for k, r in parsed[fk]:
            for y, v in r["vals"].items():
                if y not in rows[k]["vals"] and k not in present[src[y]] and y not in rows[k]["alt"]:
                    rows[k]["alt"][y] = (v, fk)
    return sorted(src), src, [(k, rows[k]) for k in order]


def clean(label):
    label = re.sub(r"\s*\[(Member|Abstract|Line Items)\]", "", label)
    label = re.sub(r"\s*\([^()]*\$\s?[\d,.]+[^()]*\)", "", label)
    label = re.sub(r",?\s*(including|excluding|less allowances?|net of allowances?)[^;]*?\$[\d,.]+.*$",
                   "", label, flags=re.I)
    label = re.sub(r"\s*of \$[\d,.]+( and \$[\d,.]+)?( at| as of)?[^,;]*$", "", label)
    label = re.sub(r";\s*[\d,]+ shares( of Common Stock)?( as of| at)?.*$", "", label)
    return label.strip(" ,;-")


def _norm(s):
    return re.sub(r"[^a-z0-9 ]", "", clean(s).lower().replace("—", "-"))


def _sgn(x):
    return (x > 0) - (x < 0)


def statement_rows(pages, typ):
    """Merged, repaired rows for one statement type."""
    years, src, rows = merge(pages)
    rows = [[k, dict(r)] for k, r in rows]
    tail_at = next((i for i, (k, _) in enumerate(rows) if k[0].endswith("Axis")), len(rows))
    main, tail = rows[:tail_at], rows[tail_at:]
    main = [x for x in main if not (
        x[1]["abstract"] and not x[1]["vals"] and (
            "[Abstract]" in x[1]["label"]
            or re.match(r"(consolidated statements? of|reconciliation of net)", x[1]["label"], re.I)))]

    # Rows split by a concept change: same section, near-identical label, disjoint years.
    changed = True
    while changed:
        changed = False
        sec, s = [], 0
        for _, r in main:
            s += bool(r["abstract"])
            sec.append(s)
        for i in range(len(main)):
            for j in range(i + 1, len(main)):
                a, b = main[i][1], main[j][1]
                if a["abstract"] or b["abstract"] or sec[i] != sec[j] or not a["vals"] or not b["vals"]:
                    continue
                if set(a["vals"]) & set(b["vals"]):
                    continue
                if difflib.SequenceMatcher(None, _norm(a["label"]), _norm(b["label"])).ratio() < 0.8:
                    continue
                newer, older = (i, j) if max(a["vals"]) > max(b["vals"]) else (j, i)
                nv = main[newer][1]
                nv["vals"] = {**main[older][1]["vals"], **nv["vals"]}
                nv["alt"] = {y: t for y, t in {**main[older][1].get("alt", {}), **nv.get("alt", {})}.items()
                             if y not in nv["vals"]}
                nv["total"] = a["total"] or b["total"]
                del main[older]
                changed = True
                break
            if changed:
                break

    # Sign repair: a section misses its reported subtotal, flipping exactly one
    # row fixes it, and the flip makes that row agree with its own sign elsewhere.
    since_abs, since_tot = [], []
    for _, r in main:
        if r["abstract"]:
            since_abs = []
            continue
        if not r["total"]:
            since_abs.append(r)
            since_tot.append(r)
            continue
        for y in r["vals"]:
            for seg in (since_abs, since_tot):
                items = [x for x in seg if y in x["vals"] and not x["pershare"]
                         and not x["shares"] and not x.get("dim")]
                if len(items) < 2:
                    continue
                diff = sum(x["vals"][y] for x in items) - r["vals"][y]
                if abs(diff) < TOL:
                    break
                fix = [x for x in items if abs(diff - 2 * x["vals"][y]) < TOL]
                if len(fix) != 1:
                    continue
                x = fix[0]
                others = [_sgn(v) for yy, v in x["vals"].items() if yy != y and v]
                if others and sum(others) * -_sgn(x["vals"][y]) > 0 and all(o == others[0] for o in others):
                    x["vals"][y] = -x["vals"][y]
                    x.setdefault("flipped", set()).add(y)
                    break
        since_abs, since_tot = [], []

    main = [x for n, x in enumerate(main) if not (
        n and x[1]["abstract"] and main[n - 1][1]["abstract"] and x[1]["label"] == main[n - 1][1]["label"])]

    # Supplemental cash-flow lines below ending cash that the source 10-K no
    # longer presents are filled from an older one; nothing else is.
    start = len(main)
    if typ == "CF":
        ends = [i for i, (k, r) in enumerate(main)
                if k[0].split(":")[-1].startswith(("CashCashEquivalents", "CashAndCashEquivalents"))
                and "PeriodIncreaseDecrease" not in k[0] and not r["abstract"]]
        start = max(ends) + 1 if ends else len(main)
    for n, (_, r) in enumerate(main):
        cand, r["alt"] = r.get("alt", {}), {}
        if n >= start:
            for y, (v, fk) in cand.items():
                if y not in r["vals"]:
                    r["vals"][y] = v
                    r["alt"][y] = fk

    # Segment and other dimensional rows go under the line they break down.
    member = parent = None
    for k, r in tail:
        if k[0].endswith("Axis"):
            member = clean(r["label"])
            continue
        if r["abstract"]:
            parent = k[0]
            continue
        if not r["vals"]:
            continue
        same = [i for i, (kk, rr) in enumerate(main) if kk[0] == k[0] and not rr.get("dim")]
        if same:
            i = same[0]
            r.update(label=member, dim=True, memo=True)
        else:
            par = [i for i, (kk, rr) in enumerate(main) if kk[0] == parent and rr["abstract"]]
            i = par[0] if par else len(main) - 1
            r.update(label=f"{clean(r['label'])} — {member}", dim=True)
        while i + 1 < len(main) and main[i + 1][1].get("dim"):
            i += 1
        main.insert(i + 1, [(k[0], ("dim", member, k[1])), r])

    out = []
    for k, r in main:
        if not r["abstract"] and not r["vals"]:
            continue
        r["label"] = clean(r["label"])
        out.append((k, r))
    return years, src, out


# --------------------------------------------------------------------------
# the workbook
# --------------------------------------------------------------------------

def _fye_text(fiscal_year_end):
    """EDGAR's ``MMDD`` as words. 52-53 week years land near, not on, it."""
    if not fiscal_year_end or len(fiscal_year_end) != 4:
        return "the company's fiscal year end"
    d = datetime(2000, int(fiscal_year_end[:2]), int(fiscal_year_end[2:]))
    return f"on or about {d:%B} {d.day}"


def build_workbook(company, filings, pages_by_type, out_path):
    """Write the three-sheet workbook. Returns ``(out_path, problems)``.

    ``company`` is ``{"ticker", "name", "fiscal_year_end"}``. ``filings`` is a
    list of dicts with ``key, form, fy, filed, url, stmts``. ``pages_by_type``
    maps ``"IS"/"BS"/"CF"`` to ``[(filing_key, html), ...]``, newest first.
    ``problems`` lists every check row that does not come to zero.
    """
    from openpyxl import Workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter as col

    tk, name = company["ticker"], company["name"]
    fil = {f["key"]: f for f in filings}
    font, thin = "Arial", Side(style="thin")
    grey = dict(name=font, size=9, italic=True, color="595959")
    wb = Workbook()
    wb.remove(wb.active)
    info = {}

    for title, typ in TYPES:
        if not pages_by_type.get(typ):
            continue
        years, src, rows = statement_rows(pages_by_type[typ], typ)
        ws = wb.create_sheet(title)
        ws["A1"] = f"{name} ({tk}) — {fil[src[max(years)]]['stmts'][typ]}"
        ws["A1"].font = Font(name=font, size=14)
        ws["A2"] = (f"Fiscal years ending {_fye_text(company.get('fiscal_year_end'))}. $ thousands except "
                    "per-share data; share counts in thousands. Each year is taken from the most recent "
                    "10-K that reports it (latest restated figures).")
        ws["A3"] = ("Source: SEC EDGAR, XBRL financial statements (R files) of the company's Form 10-K "
                    "filings; the source filing for each year is shown in row 6.")
        ws["A4"] = ("Shaded cells: the line is not presented in that year's source 10-K, so the value "
                    "comes from an earlier 10-K (see the cell comment).")
        for c in ("A2", "A3", "A4"):
            ws[c].font = Font(**grey)
        ws["A5"] = "Line item"
        ws["A6"] = "Source 10-K (fiscal year / filed)"
        ws["A6"].font = Font(**grey)
        for j, y in enumerate(years, start=2):
            f = fil[src[y]]
            ws.cell(5, j, f"FY{y}").alignment = Alignment(horizontal="right")
            s = ws.cell(6, j, f"FY{f['fy']} / {f['filed']}")
            s.font = Font(name=font, size=8, italic=True, color="595959")
            s.alignment = Alignment(horizontal="right")
            s.hyperlink = f["url"]
        for j in range(1, len(years) + 2):
            c = ws.cell(5, j)
            c.font = Font(name=font, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="1F3864")

        i, rowof = 7, {}
        for k, r in rows:
            lab = ws.cell(i, 1, r["label"])
            if r["abstract"]:
                lab.font = Font(name=font, italic=True)
                i += 1
                continue
            memo = r.get("memo")
            lab.font = Font(name=font, italic=bool(memo))
            lab.alignment = Alignment(indent=0 if r["total"] else (3 if memo else 1))
            if not r.get("dim"):
                rowof.setdefault(k, i)
            for j, y in enumerate(years, start=2):
                c = ws.cell(i, j)
                if y in r["vals"]:
                    v = r["vals"][y]
                    c.value = v if r["pershare"] else round(v * UNIT, 3)
                    if y in r.get("flipped", ()):
                        c.comment = Comment(
                            f"Sign reversed from the XBRL value in the FY{fil[src[y]]['fy']} 10-K so that the "
                            "rows sum to the reported subtotal, matching the sign convention of later filings.",
                            "two-stage-dcf")
                    if y in r.get("alt", {}):
                        g = fil[r["alt"][y]]
                        c.comment = Comment(
                            f"Not presented in the FY{fil[src[y]]['fy']} 10-K; value from the FY{g['fy']} "
                            f"{g['form']} filed {g['filed']}. {g['url']}", "two-stage-dcf")
                        c.fill = PatternFill("solid", fgColor="F2F2F2")
                c.number_format = '$0.00;($0.00);"-"' if r["pershare"] else '#,##0;(#,##0);"-"'
                c.font = Font(name=font, color="0000FF", italic=bool(memo))
                if r["total"]:
                    c.border = Border(top=thin)
            if r["total"]:
                lab.border = Border(top=thin)
            i += 1
        ws.column_dimensions["A"].width = 66
        for j in range(2, len(years) + 2):
            ws.column_dimensions[col(j)].width = 13
        ws.freeze_panes = "B7"
        info[typ] = dict(ws=ws, rowof=rowof, years=years, next=i)

    problems = _add_checks(info, Font, Alignment, col, font)
    wb.save(out_path)
    return out_path, problems


def _add_checks(info, Font, Alignment, col, font):
    """Footing checks as live formulas, also evaluated here so a failure is reported."""

    def find(typ, *pats):
        if typ not in info:
            return None
        for (concept, occ), row in info[typ]["rowof"].items():
            name = concept.split(":")[-1]
            if occ == 1 and any(name == p or (p.endswith("*") and name.startswith(p[:-1])) for p in pats):
                return row
        return None

    def value(typ, ref):
        return info[typ]["ws"][ref].value or 0

    checks = {"IS": [], "BS": [], "CF": []}
    rev = find("IS", "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet")
    cogs = find("IS", "CostOfGoodsAndServicesSold", "CostOfRevenue", "CostOfGoodsSold")
    gp = find("IS", "GrossProfit")
    pre = find("IS", "IncomeLossFromContinuingOperationsBefore*")
    tax = find("IS", "IncomeTaxExpenseBenefit")
    ni = find("IS", "ProfitLoss") or find("IS", "NetIncomeLoss")
    if rev and cogs and gp:
        checks["IS"].append(("Revenue − cost of sales − gross profit", f"{{c}}{rev}-{{c}}{cogs}-{{c}}{gp}"))
    if pre and tax and ni:
        last = col(len(info["IS"]["years"]) + 1)
        sign = "-" if abs(value("IS", f"{last}{pre}") - value("IS", f"{last}{tax}")
                          - value("IS", f"{last}{ni}")) < 1 else "+"
        checks["IS"].append((f"Pretax income {sign} income tax − net income",
                             f"{{c}}{pre}{sign}{{c}}{tax}-{{c}}{ni}"))
    a, le = find("BS", "Assets"), find("BS", "LiabilitiesAndStockholdersEquity")
    if a and le:
        checks["BS"].append(("Total assets − total liabilities and equity", f"{{c}}{a}-{{c}}{le}"))
    if "CF" in info:
        op = find("CF", "NetCashProvidedByUsedInOperatingActivities*")
        inv = find("CF", "NetCashProvidedByUsedInInvestingActivities*")
        fin = find("CF", "NetCashProvidedByUsedInFinancingActivities*")
        fx = find("CF", "EffectOfExchangeRate*")
        rowof = info["CF"]["rowof"]
        chg = next((r for (c, _), r in rowof.items() if "PeriodIncreaseDecrease" in c
                    and c.split(":")[-1].startswith("Cash")), None)
        cash = sorted(r for (c, _), r in rowof.items()
                      if c.split(":")[-1].startswith(("CashCashEquivalents", "CashAndCashEquivalents"))
                      and "PeriodIncreaseDecrease" not in c)
        if op and inv and fin and chg:
            checks["CF"].append(("Operating + investing + financing" + (" + FX" if fx else "")
                                 + " − net change in cash",
                                 f"{{c}}{op}+{{c}}{inv}+{{c}}{fin}" + (f"+{{c}}{fx}" if fx else "")
                                 + f"-{{c}}{chg}"))
        if len(cash) >= 2 and chg:
            checks["CF"].append(("Beginning cash + net change − ending cash",
                                 f"{{c}}{cash[0]}+{{c}}{chg}-{{c}}{cash[-1]}"))

    names = {"IS": "Income Statement", "BS": "Balance Sheet", "CF": "Cash Flow Statement"}
    problems = []
    for typ, items in checks.items():
        if not items:
            continue
        ws, years, i = info[typ]["ws"], info[typ]["years"], info[typ]["next"] + 1
        ws.cell(i, 1, "Checks (should be zero)").font = Font(name=font, italic=True)
        i += 1
        for label, template in items:
            ws.cell(i, 1, label).font = Font(name=font, size=9)
            ws.cell(i, 1).alignment = Alignment(indent=1)
            for j, y in enumerate(years, start=2):
                c = col(j)
                expr = template.format(c=c)
                cell = ws.cell(i, j, "=" + expr)
                cell.number_format = '#,##0;(#,##0);"-"'
                cell.font = Font(name=font, size=9)
                result = eval(re.sub(r"[A-Z]+\d+", lambda m: repr(value(typ, m.group(0))), expr))
                if abs(result) >= 1:
                    problems.append(f"{names[typ]} FY{y}: {label} is {result:,.0f}")
            i += 1
    return problems
