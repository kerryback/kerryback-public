"""Fetch a company's statements, 10-Ks, press releases and call transcripts.

    python dcf_fetch.py JBSS ~/data/jbss --contact "Jane Doe jane@school.edu"

writes the folder ``dcf_inputs`` reads:

    <folder>/
      <ticker>_financials_10k.xlsx    three statements from the 10-Ks' XBRL pages
      10k/                            the 10-K documents themselves
      press_releases/                 earnings releases, 8-K Exhibit 99 (.htm and .txt)
      transcripts/                    earnings call transcripts (.txt)

Sources, all free:

- SEC EDGAR for everything but the calls. EDGAR requires a User-Agent naming a
  person and an email address, so pass ``--contact`` or set
  ``SEC_USER_AGENT``. Requests are paced well under EDGAR's ten a second.
- The Motley Fool's transcript archive for the calls, found through the
  company's quote page and the monthly sitemaps. Coverage is uneven: some
  quarters are missing, more often for small companies and for 2023-2025. The
  text is copyrighted; it is fine to read for coursework and not to
  redistribute. A transcript a company filed with an 8-K is picked up from
  EDGAR as well.

Fiscal quarters are computed from EDGAR's fiscal-year-end date and the filing
or call date, the same way for releases and calls, so a release and its call
carry the same FY/Q label. The fiscal year is named for the calendar year it
ends in.

Re-running is cheap: files already present are not fetched again.
"""

import os
import re
import time
from datetime import date, datetime, timedelta

PAUSE_SEC = 0.15
PAUSE_FOOL = 0.6
TIMEOUT = 30
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126 Safari/537.36")
QUARTER_WORDS = {"first": 1, "second": 2, "third": 3, "fourth": 4}


# --------------------------------------------------------------------------
# fiscal calendar
# --------------------------------------------------------------------------

def fiscal_quarter(when, fye_month):
    """``(fiscal_year, quarter)`` of the latest quarter that ended before ``when``.

    A quarter counts as ended five days after its month closes, which is
    earlier than any company files or holds its call. Fiscal years are named
    for the calendar year they end in, so a June year end makes September the
    first quarter of the next fiscal year.
    """
    if isinstance(when, str):
        when = date.fromisoformat(when[:10])
    ends = {(fye_month - 1 + 3 * k) % 12 + 1 for k in range(4)}
    y, m = when.year, when.month
    while True:
        last = (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1))
        if m in ends and last <= when - timedelta(days=5):
            break
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    fy = y if m <= fye_month else y + 1
    q = ((m - fye_month - 1) % 12) // 3 + 1
    return fy, q


# --------------------------------------------------------------------------
# EDGAR
# --------------------------------------------------------------------------

class Edgar:
    def __init__(self, contact=None):
        import requests

        agent = contact or os.environ.get("SEC_USER_AGENT")
        if not agent or "@" not in agent:
            raise SystemExit(
                "EDGAR asks every client to identify itself. Pass --contact "
                "\"Your Name you@example.com\" or set SEC_USER_AGENT.")
        self.http = requests.Session()
        self.http.headers.update({"User-Agent": agent})

    def get(self, url, binary=False):
        r = self.http.get(url, timeout=TIMEOUT)
        time.sleep(PAUSE_SEC)
        r.raise_for_status()
        return r.content if binary else r.text

    def company(self, ticker):
        tickers = self.http.get("https://www.sec.gov/files/company_tickers.json", timeout=TIMEOUT).json()
        hit = next((r for r in tickers.values() if r["ticker"].upper() == ticker.upper()), None)
        if hit is None:
            raise SystemExit(f"{ticker} is not in EDGAR's ticker list.")
        cik = int(hit["cik_str"])
        sub = self.http.get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", timeout=TIMEOUT).json()
        import pandas as pd

        filings = pd.DataFrame(sub["filings"]["recent"])
        return {"ticker": ticker.upper(), "cik": cik, "name": sub.get("name") or hit["title"],
                "fiscal_year_end": sub.get("fiscalYearEnd") or "1231", "filings": filings}

    def base(self, co, accession):
        return f"https://www.sec.gov/Archives/edgar/data/{co['cik']}/{accession.replace('-', '')}/"


def _statement_reports(summary_xml):
    """Pick the face statements out of FilingSummary.xml: ``{"IS"|"BS"|"CF": (file, name)}``.

    Prefers a plain income statement; falls back to a combined statement of
    comprehensive income when that is the only one the company files.
    """
    import xml.etree.ElementTree as ET

    root = ET.fromstring(summary_xml)
    got, comprehensive = {}, None
    for rep in root.iter("Report"):
        if (rep.findtext("MenuCategory") or "") != "Statements":
            continue
        short, html = rep.findtext("ShortName") or "", rep.findtext("HtmlFileName")
        sn = short.lower()
        if not html or "parenthetical" in sn:
            continue
        if "balance sheet" in sn or "financial position" in sn:
            typ = "BS"
        elif "cash flow" in sn:
            typ = "CF"
        elif ("operations" in sn or "income" in sn or "earnings" in sn) and "equity" not in sn:
            if "comprehensive" in sn:
                comprehensive = comprehensive or (html, short)
                continue
            typ = "IS"
        else:
            continue
        got.setdefault(typ, (html, short))
    if "IS" not in got and comprehensive:
        got["IS"] = comprehensive
    return got


def fetch_10ks(edgar, co, folder, n=5, log=print):
    """The last ``n`` 10-Ks (and any amendments since the oldest), plus their statement pages.

    Returns ``(filings, pages_by_type)`` for ``dcf_statements.build_workbook``.
    """
    f = co["filings"]
    tenk = f[f.form.isin(["10-K", "10-K/A"])]
    oldest = tenk[tenk.form == "10-K"].head(n).filingDate.min()
    tenk = tenk[tenk.filingDate >= oldest]
    doc_dir = os.path.join(folder, "10k")
    cache = os.path.join(folder, ".edgar")
    os.makedirs(doc_dir, exist_ok=True)
    os.makedirs(cache, exist_ok=True)

    filings, pages = [], {"IS": [], "BS": [], "CF": []}
    for _, r in tenk.iterrows():             # EDGAR lists newest first
        base = edgar.base(co, r.accessionNumber)
        form = r.form.replace("/", "")
        fy = r.reportDate[:4]
        doc = os.path.join(doc_dir, f"{co['ticker']}_{form}_FY{fy}_filed{r.filingDate}.htm")
        if not os.path.exists(doc):
            open(doc, "wb").write(edgar.get(base + r.primaryDocument, binary=True))
        key = f"{r.filingDate}_{form}"
        reports = _statement_reports(edgar.get(base + "FilingSummary.xml", binary=True))
        for typ, (html_name, _) in reports.items():
            path = os.path.join(cache, f"{key}_{typ}.htm")
            if not os.path.exists(path):
                open(path, "wb").write(edgar.get(base + html_name, binary=True))
            pages[typ].append((key, open(path, encoding="utf-8", errors="replace").read()))
        filings.append(dict(key=key, form=r.form, fy=fy, filed=r.filingDate, url=base + r.primaryDocument,
                            stmts={t: v[1] for t, v in reports.items()}))
        log(f"  10-K   {r.form:7s} FY{fy} filed {r.filingDate}  statements: {', '.join(sorted(reports))}")
    return filings, pages


def _text(html):
    from bs4 import BeautifulSoup

    raw = BeautifulSoup(html, "html.parser").get_text("\n")
    return "\n".join(line.strip() for line in raw.split("\n") if line.strip())


def _looks_like_transcript(text):
    head = text[:3000].lower()
    return "transcript" in head[:1500] or (
        "operator" in text[:20000].lower() and "question-and-answer" in text.lower())


def fetch_press_releases(edgar, co, folder, since, log=print):
    """Earnings releases: Exhibit 99 of every 8-K with item 2.02 since ``since``.

    A transcript filed as an exhibit goes to ``transcripts/`` instead. Investor
    presentations and other exhibits are skipped.
    """
    f = co["filings"]
    k8 = f[f.form.isin(["8-K", "8-K/A"]) & (f.filingDate >= since)]
    out = os.path.join(folder, "press_releases")
    calls = os.path.join(folder, "transcripts")
    os.makedirs(out, exist_ok=True)
    os.makedirs(calls, exist_ok=True)
    fye_month = int(co["fiscal_year_end"][:2])
    from bs4 import BeautifulSoup

    n = 0
    for _, r in k8.iterrows():
        is_earnings = "2.02" in str(r["items"])
        base = edgar.base(co, r.accessionNumber)
        index = edgar.get(base + f"{r.accessionNumber}-index.htm")
        exhibits = []
        for tr in BeautifulSoup(index, "html.parser").select("table.tableFile tr"):
            td = tr.find_all("td")
            kind = td[3].get_text(strip=True).upper() if len(td) >= 4 else ""
            if kind.startswith("EX-99") and td[2].a:
                exhibits.append((kind, td[2].a["href"].split("/")[-1]))
        if not exhibits:
            continue
        fy, q = fiscal_quarter(r.filingDate, fye_month)
        for kind, doc in exhibits:
            html = edgar.get(base + doc, binary=True)
            text = _text(html)
            transcript = _looks_like_transcript(text)
            # The release is Exhibit 99.1 (or a lone 99). Later 99s are slides,
            # supplements or a transcript; only the transcript is kept.
            release = is_earnings and kind in ("EX-99.1", "EX-99") and "presentation" not in text[:600].lower()
            if transcript:
                stem = os.path.join(calls, f"{co['ticker']}_FY{fy}Q{q}_earnings_call_filed8K_{r.filingDate}")
            elif not release:
                continue
            else:
                stem = os.path.join(out, f"{co['ticker']}_FY{fy}Q{q}_press_release_filed{r.filingDate}")
            if os.path.exists(stem + ".txt"):
                stem += "_" + re.sub(r"\W", "", doc.rsplit(".", 1)[0])[-6:]
                if os.path.exists(stem + ".txt"):
                    continue
            open(stem + ".htm", "wb").write(html)
            open(stem + ".txt", "w", encoding="utf-8").write(
                f"Source: SEC EDGAR 8-K {r.accessionNumber} (items {r['items']}), {base + doc}\n\n{text}")
            n += 1
            log(f"  8-K    filed {r.filingDate}  -> {os.path.basename(stem)}")
    return n


# --------------------------------------------------------------------------
# Motley Fool transcripts
# --------------------------------------------------------------------------

FOOL = "https://www.fool.com"
LINK_RE = re.compile(r"/earnings/call-transcripts/(\d{4})/(\d{2})/(\d{2})/([a-z0-9.\-]+?)(?:\.aspx|/)")
DATE_RE = re.compile(
    r"(?:[A-Z][a-z]+day\s*,\s*)?([A-Z][a-z]{2,8})\.?\s+(\d{1,2})\s*,\s*(\d{4})", re.I)
FISCAL_RE = re.compile(
    r"(first|second|third|fourth)[ -]quarter(?: of)?(?: fiscal)?(?: year)? (20\d\d)"
    r"|fiscal (?:year )?(20\d\d) (first|second|third|fourth)[ -]quarter", re.I)


def _fool_session():
    import requests

    s = requests.Session()
    s.headers.update({"User-Agent": BROWSER_UA})
    return s


def _slug_has(slug, ticker):
    return ticker.lower() in slug.lower().split("-")


def transcript_links(ticker, years, session=None, log=print):
    """Transcript paths for ``ticker``: the quote page, then the monthly sitemaps."""
    s = session or _fool_session()
    found = {}
    for exchange in ("nasdaq", "nyse", "nysemkt", "otc"):
        r = s.get(f"{FOOL}/quote/{exchange}/{ticker.lower()}/", timeout=TIMEOUT)
        time.sleep(PAUSE_FOOL)
        if r.status_code == 200:
            for m in LINK_RE.finditer(r.text):
                if _slug_has(m.group(4), ticker):
                    found.setdefault(m.group(0), m.groups())
            break
    today = date.today()
    for y in range(today.year - years, today.year + 1):
        for mo in range(1, 13):
            if (y, mo) > (today.year, today.month):
                break
            r = s.get(f"{FOOL}/sitemap/{y}/{mo:02d}", timeout=TIMEOUT)
            time.sleep(PAUSE_FOOL / 2)
            if r.status_code != 200:
                continue
            for m in LINK_RE.finditer(r.text):
                if _slug_has(m.group(4), ticker):
                    found.setdefault(m.group(0), m.groups())
    log(f"  calls  {len(found)} Motley Fool transcript links")
    return sorted(found)


def _call_date(text):
    """The date the call was held, from the transcript's own header, or None."""
    m = DATE_RE.search(text[:1500])
    if m:
        for fmt in ("%b %d %Y", "%B %d %Y"):
            try:
                word = m.group(1)[:3] if fmt.startswith("%b") else m.group(1)
                return datetime.strptime(f"{word} {m.group(2)} {m.group(3)}", fmt).date()
            except ValueError:
                continue
    return None


def fetch_transcripts(co, folder, years=6, log=print):
    """Save each Motley Fool transcript as ``<T>_FY<y>Q<q>_earnings_call_<date>.txt``."""
    from bs4 import BeautifulSoup

    out = os.path.join(folder, "transcripts")
    os.makedirs(out, exist_ok=True)
    s = _fool_session()
    fye_month = int(co["fiscal_year_end"][:2])
    have = {re.sub(r"_earnings_call.*", "", n) for n in os.listdir(out)}
    n = 0
    for path in transcript_links(co["ticker"], years, s, log):
        y, mo, d = (int(x) for x in LINK_RE.search(path).groups()[:3])
        r = s.get(FOOL + path, timeout=TIMEOUT)
        time.sleep(PAUSE_FOOL)
        if r.status_code != 200:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        body = soup.select_one(".article-body") or soup.select_one("section.usmf-new")
        if body is None:
            continue
        for x in body.select("script,style,figure,aside"):
            x.decompose()
        text = "\n".join(line.strip() for line in body.get_text("\n").split("\n") if line.strip())
        if len(text) < 2000:
            continue
        held = _call_date(text)
        when = held or date(y, mo, d)
        fy, q = fiscal_quarter(when, fye_month)
        # With no date in the text, the publication date is all there is, and
        # the archive sometimes publishes a call months late. Then what the
        # call says about itself is the better label.
        label = FISCAL_RE.search(re.sub(r"\s+", " ", text[:6000]))
        if held is None and label:
            q = QUARTER_WORDS[(label.group(1) or label.group(4)).lower()]
            fy = int(label.group(2) or label.group(3))
        stem = f"{co['ticker']}_FY{fy}Q{q}"
        if stem in have:
            continue
        have.add(stem)
        name = f"{stem}_earnings_call_{when.isoformat()}.txt"
        open(os.path.join(out, name), "w", encoding="utf-8").write(
            f"{co['ticker']} earnings call transcript\nSource: The Motley Fool, {FOOL + path}\n\n{text}")
        n += 1
        log(f"  call   {when}  -> {name}")
    return n


# --------------------------------------------------------------------------
# all of it
# --------------------------------------------------------------------------

def fetch(ticker, folder, contact=None, years=5, skip=(), log=print):
    """Fetch everything for ``ticker`` into ``folder``. Returns a summary dict."""
    from dcf_statements import build_workbook

    folder = os.path.abspath(os.path.expanduser(folder))
    os.makedirs(folder, exist_ok=True)
    edgar = Edgar(contact)
    co = edgar.company(ticker)
    log(f"{co['name']} ({co['ticker']}), CIK {co['cik']}, fiscal year end {co['fiscal_year_end']}")
    summary = {"company": co["name"], "ticker": co["ticker"], "folder": folder}

    filings, pages = fetch_10ks(edgar, co, folder, n=years, log=log)
    if not filings:
        raise SystemExit(f"EDGAR lists no 10-K for {ticker}.")
    workbook = os.path.join(folder, f"{co['ticker'].lower()}_financials_10k.xlsx")
    _, problems = build_workbook(co, filings, pages, workbook)
    summary.update(workbook=workbook, problems=problems)
    log(f"  wrote  {os.path.basename(workbook)}" + ("" if not problems else f"  ({len(problems)} checks fail)"))

    # The oldest 10-K reports three years of income, so releases go back as far.
    since = (date.fromisoformat(min(f["filed"] for f in filings)) - timedelta(days=3 * 365)).isoformat()
    if "press" not in skip:
        summary["press_releases"] = fetch_press_releases(edgar, co, folder, since, log=log)
    if "transcripts" not in skip:
        summary["transcripts"] = fetch_transcripts(co, folder, years=years + 1, log=log)
    return summary


if __name__ == "__main__":
    import argparse

    from dcf_inputs import describe, inventory

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("ticker")
    ap.add_argument("folder")
    ap.add_argument("--contact", help='"Name email" for EDGAR\'s User-Agent (or set SEC_USER_AGENT)')
    ap.add_argument("--years", type=int, default=5, help="how many 10-Ks to read (default 5)")
    ap.add_argument("--skip", action="append", default=[], choices=["press", "transcripts"],
                    help="leave out press releases or transcripts")
    args = ap.parse_args()

    result = fetch(args.ticker, args.folder, contact=args.contact, years=args.years, skip=args.skip)
    for p in result.get("problems") or []:
        print("  CHECK  " + p)
    print()
    print(describe(inventory(result["folder"])))
