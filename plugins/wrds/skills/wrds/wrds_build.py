"""WRDS building blocks — connect, pull, merge, and construct standard variables.

This is a LIBRARY OF SECTIONS, not an application. Nothing runs on import and
there is no config file, no global state, and no hidden ordering: every function
takes what it needs and returns a DataFrame. That is what makes it extractable.

HOW TO USE THIS FILE
--------------------
Do NOT import this module into a project. Copy the sections you need into the
project's own build script so that script is standalone and re-runnable years
later without this plugin on the path. Each section below is delimited by a
banner and lists its dependencies; a project that only needs a monthly CRSP
panel with market cap lifts sections 1, 2, and 3 and stops there.

    §1  Connection                     (always)
    §2  CRSP monthly security file     needs §1
    §3  Market cap, incl. permco       needs §2
    §4  Compustat annual fundamentals  needs §1
    §5  CRSP-Compustat link            needs §1
    §6  Merge accounting onto months   needs §2 §4 §5
    §7  Firm age                       needs §2 or §4
    §8  Orchestrator (worked example)  needs all

THE CHOICES THAT ARE NOT COMMON PRACTICE
-----------------------------------------
Almost everything here is standard and needs no defense. A handful of
constructions are not, and on those three reference implementations disagree:

    CONVENTIONS['french']      as documented in the Fama-French data library
    CONVENTIONS['drechsler']   the WRDS reference script — what most published
                               replications actually ran
    CONVENTIONS['openap']      Open Source Asset Pricing (Chen-Zimmermann)

DIVERGENCES below lists every dimension on which the three are NOT unanimous.
The rule: if a dimension is in DIVERGENCES and the build touches it, ASK the
person building the sample — never pick silently — and record the answer in the
paper, because results move with it. Anything not in DIVERGENCES is settled.
§4 and §6 are where it bites. describe_conventions() prints the choices.

CRSP VINTAGE
------------
v2 / CIZ only (crsp.msf_v2, which carries its screen columns inline —
see §2 on why joining stksecurityinfohist for them is harmful). The legacy v1 tables
are not supported here on purpose: v2's mthret is a proper float and is already
delisting-adjusted, which removes the single largest source of silent error in
older code — the missing-dlret imputation, where public implementations variously
used -0.30, -0.35/-0.55, or nothing at all.

Units are stated on every variable that has them. Money is US dollars;
market cap is returned in $ MILLIONS.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

# =============================================================================
# CONVENTIONS — the French / OpenAP switch
# =============================================================================
# preferred_order   how to value preferred stock when subtracting it from equity.
#                   French: "depending on availability, we use the redemption,
#                   liquidation, or par value (in that order)". OpenAP takes par
#                   value first. Both are populated for many firm-years and they
#                   are different numbers, so book equity genuinely differs.
#
# alignment         'calendar' is French: the fiscal year ending in calendar
#                   t-1 is used from July of year t through June of t+1, with
#                   DECEMBER t-1 market cap in the book-to-market denominator
#                   (while the size sort uses JUNE t cap).
#                   'monthly' is OpenAP: a fixed reporting lag of `lag_months`
#                   applied to datadate, giving a monthly characteristic panel,
#                   with market cap lagged to datadate in the denominator.
#
# Deferred taxes are txditc, dropped to 0 when missing, under BOTH — French says
# "plus balance sheet deferred taxes and investment tax credit (if available)"
# and OpenAP does the same. A txdb+itcb reconstruction is common in other code
# and recovers firm-years where txditc is unpopulated, but it is neither French
# nor OpenAP, so it is not offered here.
#
# lag_months        a SECOND, independent choice, and only meaningful under
#                   'monthly' alignment. 6 months is the conservative default;
#                   4 months is Hou-Xue-Zhang (2015), which gets the signal into
#                   the panel two months sooner and so trades look-ahead risk
#                   against staleness. Both are standard; neither is safe to
#                   pick silently. Under 'calendar' alignment the June/December
#                   structure supplies the lag and this does not apply.

LAG_CHOICES = {
    4: "Hou-Xue-Zhang (2015) — signal available 2 months sooner, tighter timing",
    6: "conservative — the fiscal year is comfortably public by then",
}

CONVENTIONS = {
    "french": {
        "label": "Ken French, as documented in the Fama-French data library",
        "preferred_order": ("pstkrv", "pstkl", "pstk"),
        "se_cascade": True,      # seq -> ceq + pstk -> at - lt
        "negative_be": "keep",   # flagged via be_positive, not dropped
        "alignment": "calendar",
        "lag_months": None,      # n/a: the June/December calendar supplies it
    },
    "drechsler": {
        "label": "Drechsler's WRDS reference script — what most published "
                 "replications actually ran",
        "preferred_order": ("pstkrv", "pstkl", "pstk"),
        "se_cascade": False,     # seq only; firm-years without seq drop out
        "negative_be": "drop",   # be = NaN where be <= 0
        "alignment": "calendar",
        "lag_months": None,
    },
    "openap": {
        "label": "Open Source Asset Pricing (Chen-Zimmermann)",
        "preferred_order": ("pstk", "pstkrv", "pstkl"),
        "se_cascade": True,
        "negative_be": "keep",
        "alignment": "monthly",
        "lag_months": 6,
    },
}

# Where the three do NOT agree. Each entry is the dimension, then what each
# convention does. The rule: if a dimension appears here and the build touches
# it, ASK — do not pick. Dimensions on which all three agree (market equity as
# |prc| * shrout, aggregation across permco, deferred taxes as txditc with 0 for
# missing, the Compustat format filters) are settled and need no discussion.
DIVERGENCES = {
    "preferred stock valuation": {
        "french": "redemption -> liquidation -> par (pstkrv, pstkl, pstk)",
        "drechsler": "redemption -> liquidation -> par  [same as french]",
        "openap": "par -> redemption -> liquidation (pstk, pstkrv, pstkl). "
                  "Differs from french on 6.4% of firm-years; where it "
                  "differs the median gap in book equity is 5.8% and the "
                  "90th percentile is 129%.",
    },
    "shareholders' equity": {
        "french": "seq -> ceq + pstk -> at - lt",
        "drechsler": "seq only — no fallback. Costs nothing in modern data "
                     "(the cascade recovered 0 firm-years in 2012-2018) but "
                     "3,474 in 1965-1975. Matters only for long samples.",
        "openap": "seq -> ceq + preferred -> at - lt  [~same as french]",
    },
    "negative book equity": {
        "french": "kept, flagged (be_positive)",
        "drechsler": "dropped — be set missing where be <= 0. 11.4% of "
                     "firm-years with computable book equity (2012-2018). "
                     "This is the whole of the french/drechsler gap in "
                     "modern data.",
        "openap": "kept, flagged",
    },
    "CRSP universe screens": {
        "french": "not specified at this level of detail",
        "drechsler": "conditionaltype 'RW' only, plus usincflg='Y' "
                     "(US-incorporated) — the tighter universe",
        "openap": "shrcd 10/11 + exchcd 1-3 on v1, i.e. 'RW' only, with no "
                  "US-incorporation filter",
    },
    "accounting-to-month alignment": {
        "french": "calendar: FY t-1 from July of t, December t-1 cap in B/M",
        "drechsler": "calendar  [same as french]",
        "openap": "monthly: fixed reporting lag on datadate, cap lagged to it",
    },
}


def describe_conventions() -> str:
    """The choices to put to the user before building a sample.

    Lists only the dimensions on which french / drechsler / openap disagree,
    plus the reporting lag. Anything not listed here is settled practice.
    """
    lines = [
        "Three reference conventions: french, drechsler, openap.",
        "",
        "  french     " + CONVENTIONS["french"]["label"],
        "  drechsler  " + CONVENTIONS["drechsler"]["label"],
        "  openap     " + CONVENTIONS["openap"]["label"],
        "",
        "They are NOT unanimous on the following. Choose explicitly:",
        "",
    ]
    for dim, by_conv in DIVERGENCES.items():
        lines.append(f"  {dim}")
        for conv in ("french", "drechsler", "openap"):
            lines.append(f"      {conv:<10} {by_conv[conv]}")
        lines.append("")
    lines += [
        "Reporting lag — openap alignment only; french and drechsler supply",
        "their own lag through the June/December calendar:",
        "",
        f"      4 months   {LAG_CHOICES[4]}",
        f"      6 months   {LAG_CHOICES[6]}",
        "",
        "Everything else — market equity as |prc| * shrout, aggregation across",
        "permco, deferred taxes as txditc with 0 for missing, the Compustat",
        "format filters — is settled and needs no decision.",
    ]
    return "\n".join(lines)


# =============================================================================
# §1  CONNECTION
# =============================================================================
# Password comes from ~/.pgpass. The username does NOT — the wrds library never
# reads it from there, so it must be passed explicitly or an unattended run
# blocks forever on a prompt. Never hardcode it: resolve at runtime so the same
# script works for a coauthor, a replicator, and a referee.


def wrds_username() -> str:
    """Resolve the WRDS username, first hit wins. Mirrors wrds_username.py."""
    u = os.environ.get("WRDS_USER")
    if u and u.strip():
        return u.strip()

    wrds_file = Path.home() / ".wrds"
    if wrds_file.exists():
        for line in wrds_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.upper().startswith("WRDS_USER"):
                return line.split("=", 1)[1].strip()
            return line  # a bare username line

    pgpass = Path.home() / ".pgpass"
    if pgpass.exists():
        for line in pgpass.read_text(encoding="utf-8").splitlines():
            parts = line.split(":")
            if len(parts) >= 5 and "wrds" in parts[0].lower():
                return parts[3]

    raise SystemExit(
        "WRDS username not found. Set $WRDS_USER, create ~/.wrds with your WRDS "
        "id, or ensure ~/.pgpass has a wrds line (host:port:db:USERNAME:password)."
    )


def connect():
    """Open a WRDS connection non-interactively."""
    import wrds

    return wrds.Connection(wrds_username=wrds_username())


# =============================================================================
# §2  CRSP MONTHLY SECURITY FILE (v2 / CIZ)
# =============================================================================
# crsp.msf_v2. mthret is already delisting-adjusted — do NOT merge
# crsp.msedelist on top of it, that double counts. Delisting months are visible
# via mthretflg ('DE') and mthdelflg.
#
# ---------------------------------------------------------------------------
# DO NOT JOIN stksecurityinfohist FOR THE SCREENS
# ---------------------------------------------------------------------------
# msf_v2 carries the screen columns INLINE — sharetype, securitytype,
# securitysubtype, issuertype, primaryexch, conditionaltype, tradingstatusflg,
# usincflg, siccd and ticker are all columns on msf_v2 itself. Screen on those.
#
# The tempting alternative — joining crsp.stksecurityinfohist over its validity
# window, secinfostartdt <= mthcaldt <= secinfoenddt — introduces a survivorship
# bug. That window closes on the DELISTING DATE while the return row is dated
# MONTH END, so for a stock that stops trading mid-month the join returns NULL
# for every screen column in the one month whose return IS the delisting return,
# and screening then drops it.
#
# Measured on 2000-2001 against the 2,004 delistings in crsp.msedelist:
#
#                                          delistings kept   of which for-cause
#   msf_v2 inline columns (what is used)         1,815              710
#   left join + forward-fill the identifiers     1,588              549
#   inner join on the window, then screen          222               49
#
# Concretely, permno 10039 delisted 2001-06-26. Its stksecurityinfohist record
# runs to 2001-06-26 and the next covers only 2001-06-27, while the msf_v2
# return row is dated 2001-06-29 — outside both. Read inline, that same row
# reports NS/EQTY/COM/CORP/Q/RW/A and mthret = -0.923077 flagged 'DE'.
#
# So the join is not merely unnecessary, it is harmful. Join
# stksecurityinfohist only if you specifically want its historical industry
# code, and then as a LEFT join that no screen depends on.


def crsp_monthly(
    conn,
    start_date: str = "1925-12-31",
    end_date: str = "2099-12-31",
    us_incorporated_only: bool = False,
    include_at_issuance: bool = False,
) -> pd.DataFrame:
    """Monthly CRSP common stocks from crsp.msf_v2.

    Returns permno, permco, date (month start), mthcaldt (the trading date),
    ret (delisting-adjusted), retx, prc, shrout (thousands of shares),
    mktcap_raw ($ thousands), primaryexch, siccd, ticker, mthretflg, mthdelflg.

    Defaults follow the reference scripts: conditionaltype 'RW' alone, i.e.
    the legacy exchcd in (1,2,3), excluding stocks at issuance. Both Drechsler's
    CIZ script and OpenAP's v1 screen do this. Set `include_at_issuance=True` to
    add 'NW', reproducing exchcd in (1,2,3,31,32,33).

    `us_incorporated_only` adds usincflg='Y'. Drechsler sets it; OpenAP's v1
    shrcd/exchcd screen has no equivalent and does not. It is a sample decision
    rather than part of the definition of common stock, so it is off by default
    — but it IS a divergence, so ask rather than assuming.
    """
    conditional = "'RW', 'NW'" if include_at_issuance else "'RW'"
    usinc = "\n           AND usincflg = 'Y'" if us_incorporated_only else ""
    query = f"""
        SELECT permno, permco,
               date_trunc('month', mthcaldt)::date AS date,
               mthcaldt,
               mthret  AS ret,
               mthretx AS retx,
               mthprc  AS prc,
               shrout,
               mthcap  AS mktcap_raw,
               mthretflg, mthdelflg,
               primaryexch, siccd, ticker
          FROM crsp.msf_v2
         WHERE mthcaldt BETWEEN '{start_date}' AND '{end_date}'
           AND sharetype = 'NS'
           AND securitytype = 'EQTY'
           AND securitysubtype = 'COM'
           AND issuertype IN ('ACOR', 'CORP')
           AND primaryexch IN ('N', 'A', 'Q')
           AND conditionaltype IN ({conditional})
           AND tradingstatusflg = 'A'{usinc}
    """
    df = conn.raw_sql(query, date_cols=["date", "mthcaldt"])
    df[["permno", "permco"]] = df[["permno", "permco"]].astype("Int64")
    for c in ("ret", "retx", "prc", "shrout", "mktcap_raw"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.sort_values(["permno", "date"], ignore_index=True)


# =============================================================================

# §3  MARKET CAP — AGGREGATED ACROSS SHARE CLASSES
# =============================================================================
# CRSP market cap is per PERMNO, which is one share CLASS. A dual-class firm
# (Alphabet GOOGL+GOOG, Berkshire BRK.A+BRK.B, Fox, News Corp) has several
# permnos under one PERMCO, and the CRSP-Compustat link maps a gvkey to a single
# permno. Take that permno's cap as the firm's and you understate the company,
# often by roughly half — silently corrupting size, book-to-market, enterprise
# value, value weights, and NYSE breakpoints.
#
# Verified June 2023: Alphabet (permco 45483) is $703.9bn on permno 14542 and
# $710.3bn on 90319 — $1,414bn together. Berkshire (permco 540) is $303.4bn +
# $441.9bn = $745.4bn.
#
# Keep every permno row, attach the permco total, and FLAG the representative
# rather than dropping rows. Collapsing to the max-cap permno (as some public
# code does, via an inner merge on the cap value) duplicates rows when two
# classes tie and drops permcos whose caps are all missing.


def add_market_cap(crsp: pd.DataFrame, cap_col: str | None = "mktcap_raw") -> pd.DataFrame:
    """Add per-security and per-firm market cap, both in $ MILLIONS.

    Adds:
      mktcap_permno   this share class's cap
      mktcap          the FIRM's cap: sum over all permnos in the permco-month
      is_primary_cap  True on the largest-cap permno in the permco-month

    `cap_col` names a cap column already in the frame (v2's `mktcap_raw`, in $
    thousands). If None, cap is computed as |prc| * shrout, also $ thousands
    since shrout is in thousands of shares.
    """
    df = crsp.copy()
    if cap_col and cap_col in df.columns:
        cap_thousands = df[cap_col]
    else:
        cap_thousands = df["prc"].abs() * df["shrout"]

    df["mktcap_permno"] = cap_thousands / 1_000.0
    # A cap of exactly zero means no price or no shares, not a bankrupt firm.
    df.loc[df["mktcap_permno"] == 0, "mktcap_permno"] = np.nan

    grp = df.groupby(["permco", "date"], dropna=False)["mktcap_permno"]
    df["mktcap"] = grp.transform("sum", min_count=1)
    df["is_primary_cap"] = df["mktcap_permno"].eq(grp.transform("max")) & df[
        "mktcap_permno"
    ].notna()
    return df


def lag_market_cap(crsp: pd.DataFrame, months: int = 1) -> pd.DataFrame:
    """Add `mktcap_lag`, the firm's cap `months` earlier.

    Joined on an explicit shifted date rather than groupby().shift(), so a gap
    in the panel produces a missing lag instead of silently reaching further
    back. Shifting a ragged panel by position is the standard way this breaks.
    """
    df = crsp.copy()
    key = df[["permno", "date", "mktcap"]].dropna(subset=["date"]).copy()
    key["date"] = key["date"] + pd.DateOffset(months=months)
    key = key.rename(columns={"mktcap": "mktcap_lag"})
    return df.merge(key, on=["permno", "date"], how="left")


# =============================================================================
# §4  COMPUSTAT ANNUAL FUNDAMENTALS  —  CONVENTION-DEPENDENT
# =============================================================================
# indfmt='INDL', datafmt='STD', consol='C', popsrc='D' select consolidated,
# standardized, industrial-format domestic statements. curcd='USD' keeps out
# CAD-reporting Canadian filers, whose book values would otherwise be mixed with
# CRSP's USD market equity.
#
# Book equity is where French and OpenAP part company. Both compute
#     BE = shareholders' equity + deferred taxes - preferred stock
# with shareholders' equity falling back seq -> ceq + preferred -> at - lt, and
# deferred taxes = txditc, 0 when missing. They differ in how preferred stock is
# valued:
#     french  redemption -> liquidation -> par   (pstkrv, pstkl, pstk)
#     openap  par -> redemption -> liquidation   (pstk, pstkrv, pstkl)
# Many firm-years populate more than one, and they are different numbers, so the
# resulting book equity — and every sort built on it — differs.


def compustat_annual(
    conn,
    start_date: str = "1950-01-01",
    end_date: str = "2099-12-31",
    convention: str = "french",
    usd_only: bool = True,
) -> pd.DataFrame:
    """Annual Compustat fundamentals plus book equity and operating profitability.

    One row per gvkey-datadate. `convention` is 'french' or 'openap'.
    """
    currency = "AND f.curcd = 'USD'" if usd_only else ""
    query = f"""
        SELECT f.gvkey, f.datadate, f.fyear, f.curcd,
               c.cik, c.sic, c.naics,
               f.at, f.lt, f.seq, f.ceq, f.txditc, f.txdb, f.itcb,
               f.pstkrv, f.pstkl, f.pstk,
               f.sale, f.revt, f.cogs, f.xsga, f.xint, f.dp, f.xrd,
               f.ib, f.ni, f.oancf, f.capx, f.dvt,
               f.act, f.lct, f.che, f.invt, f.rect, f.ppent, f.ppegt,
               f.dlc, f.dltt, f.csho, f.ajex, f.prcc_f
          FROM comp.funda AS f
          LEFT JOIN comp.company AS c
            ON f.gvkey = c.gvkey
         WHERE f.indfmt = 'INDL'
           AND f.datafmt = 'STD'
           AND f.popsrc  = 'D'
           AND f.consol  = 'C'
           {currency}
           AND f.datadate BETWEEN '{start_date}' AND '{end_date}'
    """
    fa = conn.raw_sql(query, date_cols=["datadate"])
    fa = fa.sort_values(["gvkey", "datadate"]).drop_duplicates(
        subset=["gvkey", "datadate"], keep="last"
    )

    # Zero total assets or zero shares outstanding is missing data, not a fact.
    for c in ("at", "csho", "ceq"):
        fa.loc[fa[c] == 0, c] = np.nan

    fa = add_book_equity(fa, convention=convention)
    fa["sic2"] = fa["sic"].astype(str).str[:2]
    return fa.reset_index(drop=True)


def add_book_equity(fa: pd.DataFrame, convention: str = "french") -> pd.DataFrame:
    """Book equity and operating profitability. Three-way; see DIVERGENCES.

    Adds `be`, `be_positive`, `op`, and `preferred` (the valuation actually
    used, kept so the convention is auditable after the fact).

    Deferred taxes are txditc with 0 for missing under all three, so that term
    is not a choice.
    """
    if convention not in CONVENTIONS:
        raise ValueError(f"convention must be one of {list(CONVENTIONS)}")
    spec = CONVENTIONS[convention]

    df = fa.copy()
    order = spec["preferred_order"]
    preferred = df[order[0]]
    for col in order[1:]:
        preferred = preferred.fillna(df[col])
    df["preferred"] = preferred.fillna(0)

    if spec["se_cascade"]:
        # French: seq, else common equity plus par value of preferred, else
        # assets minus liabilities. OpenAP substitutes its own preferred
        # valuation for pstk in the middle term.
        middle = df["ceq"] + (
            df["preferred"] if convention == "openap" else df["pstk"]
        )
        shareholders = df["seq"].fillna(middle).fillna(df["at"] - df["lt"])
    else:
        # Drechsler: seq only. Firm-years without seq get no book equity at all
        # — a real coverage loss, and not a random one.
        shareholders = df["seq"]

    df["be"] = shareholders + df["txditc"].fillna(0) - df["preferred"]
    df["be_positive"] = df["be"] > 0
    if spec["negative_be"] == "drop":
        # Drechsler drops it outright. Kept as a convention because it is what
        # published replications ran, but note it removes distressed firms from
        # the sample rather than flagging them.
        df.loc[~df["be_positive"], "be"] = np.nan

    df["op"] = (
        df["sale"]
        - df["cogs"].fillna(0)
        - df["xsga"].fillna(0)
        - df["xint"].fillna(0)
    ) / df["be"].where(df["be"] > 0)
    return df


# =============================================================================
# §5  CRSP-COMPUSTAT LINK
# =============================================================================
# crsp.ccmxpf_lnkhist, linktype in ('LC','LU'), linkprim in ('P','C'), respecting
# linkdt/linkenddt. ccmxpf_linktable is the older flat view — prefer lnkhist.
# Looser linktype filters (LN, LX, LD, LS) admit links that are unresearched or
# have no reliable date range.


def ccm_link(conn, linktypes=("LC", "LU"), linkprims=("P", "C")) -> pd.DataFrame:
    """The gvkey-permno link history with its validity window.

    A NULL linkenddt (still-current link) is filled with a fixed far-future date
    rather than today's, so the same script run on two days gives one panel.
    """
    lt = "', '".join(linktypes)
    lp = "', '".join(linkprims)
    link = conn.raw_sql(
        f"""
        SELECT gvkey, lpermno AS permno, lpermco AS permco,
               linktype, linkprim, linkdt, linkenddt
          FROM crsp.ccmxpf_lnkhist
         WHERE linktype IN ('{lt}')
           AND linkprim IN ('{lp}')
        """,
        date_cols=["linkdt", "linkenddt"],
    )
    link[["permno", "permco"]] = link[["permno", "permco"]].astype("Int64")
    link["linkenddt"] = link["linkenddt"].fillna(pd.Timestamp("2099-12-31"))
    return link


def add_gvkey(crsp: pd.DataFrame, link: pd.DataFrame) -> pd.DataFrame:
    """Attach gvkey to a monthly CRSP panel, honoring the link date window."""
    merged = crsp.merge(link[["gvkey", "permno", "linkdt", "linkenddt"]],
                        on="permno", how="left")
    valid = merged["gvkey"].notna() & merged["date"].between(
        merged["linkdt"], merged["linkenddt"]
    )
    keys = (
        merged.loc[valid, ["permno", "date", "gvkey"]]
        .drop_duplicates(subset=["permno", "date"], keep="first")
    )
    return crsp.merge(keys, on=["permno", "date"], how="left")


# =============================================================================
# §6  MERGING ACCOUNTING DATA ONTO MONTHS  —  CONVENTION-DEPENDENT
# =============================================================================
# Accounting data is not public on datadate. Merge it onto the month it was
# actually knowable or you have built look-ahead into the panel before writing a
# single regression. The two conventions:
#
#   french, drechsler / 'calendar'   the fiscal year ending in calendar t-1 is
#        used from July of year t through June of t+1. Book-to-market divides by
#        DECEMBER t-1 market cap; the size sort uses JUNE t cap. This is what
#        reproduces published Fama-French factor sorts. The two agree here.
#
#   openap / 'monthly'   a fixed reporting lag (4 or 6 months) on datadate,
#        giving a monthly characteristic panel where every month carries the
#        most recent knowable fiscal year, and book-to-market divides by market
#        cap lagged to datadate.
#
# These are not interchangeable and neither is "correct" — they answer different
# questions. Say in the paper which one was used.
#
# A third option worth knowing: comp.fundq.rdq is the actual report date, so an
# rdq-based lag is tighter than any fixed rule. It is only reliably populated
# from the early 1970s, which is why fixed lags survive.


def merge_accounting_monthly(
    crsp: pd.DataFrame,
    fa: pd.DataFrame,
    lag_months: int = 6,
    cols: list[str] | None = None,
) -> pd.DataFrame:
    """OpenAP alignment: attach the most recent knowable fiscal year to each month.

    Each gvkey-month gets the latest datadate whose datadate + lag_months has
    already passed, so a firm keeps its prior fiscal year until the new one
    becomes public.
    """
    cols = cols or ["at", "be", "be_positive", "op", "sale", "ib", "ceq", "csho"]
    right = fa[["gvkey", "datadate", *cols]].copy()
    right["avail_date"] = (
        right["datadate"] + pd.DateOffset(months=lag_months)
    ).dt.to_period("M").dt.to_timestamp()

    # merge_asof cannot carry rows whose `by` key is null, so the asof match is
    # done on the linked subset and joined back. Every CRSP month survives: a
    # stock with no gvkey still has a return and a market cap, and silently
    # dropping it turns "unmatched to Compustat" into a survivorship screen
    # nobody wrote down.
    linked = (
        crsp.loc[crsp["gvkey"].notna(), ["permno", "date", "gvkey"]]
        .sort_values("date")
    )
    matched = pd.merge_asof(
        linked,
        right.sort_values("avail_date"),
        left_on="date",
        right_on="avail_date",
        by="gvkey",
        direction="backward",
    )
    # Do not carry stale fundamentals forever: cut a match more than two years
    # old, which means the firm stopped filing.
    too_old = (matched["date"] - matched["avail_date"]).dt.days > 730
    matched.loc[too_old, [*cols, "datadate", "avail_date"]] = np.nan

    out = crsp.merge(
        matched.drop(columns=["gvkey"]), on=["permno", "date"], how="left"
    )
    assert len(out) == len(crsp), "accounting merge changed the row count"
    return out


def merge_accounting_calendar(crsp: pd.DataFrame, fa: pd.DataFrame) -> pd.DataFrame:
    """French alignment: July of year t gets the fiscal year ending in t-1.

    Adds `ffyear` (t, for the July-t-to-June-t+1 holding period), `datadate`,
    the fundamentals, and `mktcap_dec` — the December-of-t-1 market cap that is
    French's book-to-market denominator.

    Two off-by-one-year traps live here, both of which produce a plausible
    number and a wrong answer:
      - Fiscal year ending in calendar t-1 maps to ffyear t, so the join key on
        the Compustat side is datadate.year + 1.
      - The December cap is DECEMBER OF t-1, not December of t, so the join key
        on the CRSP side is also date.year + 1. Using December of t leaks eight
        months of future prices into the sort.
    And the asymmetry that is not a bug: book-to-market uses December t-1 cap
    while the size sort uses JUNE t cap.
    """
    df = crsp.copy()
    df["ffyear"] = np.where(df["date"].dt.month >= 7,
                            df["date"].dt.year, df["date"].dt.year - 1)

    dec = df.loc[df["date"].dt.month == 12, ["permno", "date", "mktcap"]].copy()
    dec["ffyear"] = dec["date"].dt.year + 1  # December of t-1 serves ffyear t
    dec = dec[["permno", "ffyear", "mktcap"]].rename(columns={"mktcap": "mktcap_dec"})
    df = df.merge(dec, on=["permno", "ffyear"], how="left")

    right = fa.copy()
    right["ffyear"] = right["datadate"].dt.year + 1
    right = right.sort_values(["gvkey", "datadate"]).drop_duplicates(
        subset=["gvkey", "ffyear"], keep="last"
    )
    keep = [c for c in right.columns if c not in ("curcd",)]
    out = df.merge(right[keep], on=["gvkey", "ffyear"], how="left")
    assert len(out) == len(crsp), "accounting merge changed the row count"
    return out


# =============================================================================
# §7  FIRM AGE
# =============================================================================
# "Firm age" names two different variables, so both are provided under distinct
# names. Reporting one as "firm age" without saying which is how two papers on
# the same sample get different coefficients.
#
# Both are ROW COUNTS, not date differences, and that is deliberate: a listing
# gap should not credit a firm with age it did not trade through.


def add_compustat_age(fa: pd.DataFrame) -> pd.DataFrame:
    """Add `comp_age_yrs`: annual Compustat records to date, per gvkey."""
    df = fa.sort_values(["gvkey", "datadate"]).copy()
    df["comp_age_yrs"] = df.groupby("gvkey").cumcount() + 1
    return df


def add_crsp_age(crsp: pd.DataFrame) -> pd.DataFrame:
    """Add `crsp_age_mths`: monthly CRSP observations to date, per permno.

    Left-censored by the start of your pull. A firm listed in 1970 looks one
    month old if the sample starts in 2000 — pull CRSP from its beginning when
    age is a variable of interest, then subset.
    """
    df = crsp.sort_values(["permno", "date"]).copy()
    df["crsp_age_mths"] = df.groupby("permno").cumcount() + 1
    return df


# =============================================================================
# §8  ORCHESTRATOR — a worked example, not a required entry point
# =============================================================================
# Read this to see how the sections compose, then write the project's own
# version. Do not call it from a project script: a build should be explicit
# about its own choices, not inherit defaults from a plugin.


def build_monthly_panel(
    convention: str,
    lag_months: int | None = None,
    start_date: str = "1959-01-01",
    end_date: str = "2099-12-31",
    history_start: str = "1925-12-31",
) -> pd.DataFrame:
    """CRSP monthly + market cap + Compustat fundamentals + firm age.

    `convention` is required, not defaulted — 'french', 'drechsler' or
    'openap'. The whole point is that it is a decision, and a default would let
    it be made silently. See DIVERGENCES for what actually changes.

    `lag_months` applies only under 'openap' (monthly) alignment: 4 for
    Hou-Xue-Zhang, 6 for the conservative choice. Leaving it None takes the
    convention's own value. Under the calendar conventions the June/December
    structure supplies the lag, so passing it is an error rather than a
    silently ignored argument.

    `history_start` is deliberately separate from `start_date`. Anything
    cumulative — firm age, lagged market cap, the most recent fiscal year — must
    be built from the full history and only then subset to the analysis window,
    or it is left-censored by an arbitrary sample start. Pull from 1925,
    compute, then cut. A panel starting in 2010 whose firms are all "1 year old"
    is this mistake.
    """
    if convention not in CONVENTIONS:
        raise ValueError(f"convention must be one of {list(CONVENTIONS)}")
    spec = CONVENTIONS[convention]

    if spec["alignment"] == "calendar":
        if lag_months is not None:
            raise ValueError(
                f"lag_months does not apply to '{convention}' — the "
                "June/December calendar supplies the reporting lag. "
                "Use 'openap' to set one."
            )
        lag = None
    else:
        lag = spec["lag_months"] if lag_months is None else lag_months
        if lag not in LAG_CHOICES:
            raise ValueError(f"lag_months must be one of {sorted(LAG_CHOICES)}")

    conn = connect()
    try:
        crsp = crsp_monthly(conn, history_start, end_date)
        crsp = add_market_cap(crsp)
        crsp = lag_market_cap(crsp)
        crsp = add_crsp_age(crsp)
        crsp = add_gvkey(crsp, ccm_link(conn))

        fa = add_compustat_age(
            compustat_annual(conn, history_start, end_date, convention=convention)
        )

        if spec["alignment"] == "monthly":
            panel = merge_accounting_monthly(
                crsp, fa, lag,
                cols=["at", "be", "be_positive", "op", "sale", "ib",
                      "ceq", "csho", "comp_age_yrs"],
            )
            panel["bm"] = panel["be"] / panel["mktcap_lag"]
        else:
            panel = merge_accounting_calendar(crsp, fa)
            panel["bm"] = panel["be"] / panel["mktcap_dec"]

        panel.loc[~panel["be_positive"].fillna(False), "bm"] = np.nan
        # Stamp the choices so the panel can be audited after the fact.
        panel.attrs["convention"] = convention
        panel.attrs["lag_months"] = lag
        # Subset LAST, after every cumulative variable is built.
        return panel[panel["date"] >= pd.Timestamp(start_date)].reset_index(drop=True)
    finally:
        conn.close()


if __name__ == "__main__":
    print(describe_conventions())
    panel = build_monthly_panel("french", start_date="2015-01-01")
    print(panel.shape)
    print(panel[["permno", "date", "ret", "mktcap", "bm", "crsp_age_mths"]].tail())
