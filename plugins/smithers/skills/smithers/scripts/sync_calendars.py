#!/usr/bin/env python3
"""Keep the Smithers accounts' Google calendars in sync: full copies, every way.

For each event on one account's primary calendar, in a window from today to
--days ahead, the other calendars get a copy: title, times, location, and
description (plus the meeting link, if the event has one and the description
does not already carry it). Attendees are never copied, so a copy never sends
an invitation to anyone.

Each copy is tagged in Google's private extended properties with the account
and id of the event it came from. The tag is how the script knows its own
copies, so it never copies a copy and never makes a second one.

What it does on its own, and what it leaves to the user:
- Adds copies. Nothing else is written to a calendar.
- When a source event moves, changes, is cancelled, or is declined, the script
  does not touch the copy. It posts a proposal to the Smithers app
  (POST /api/calendar/proposals), and the user presses Apply in the Calendar tab.
  The same rule as for Claude: edits and deletions are the user's own clicks.
- An event already on both calendars is left alone: same iCalUID (an invitation
  sent to both addresses), same title and start (an event Smithers added to
  both), or exactly the same start and end (one meeting entered on each
  calendar under different titles). The last rule means two different events
  at exactly the same times are not copied across.
- If the user deletes a copy, it is not re-created; the state file remembers
  which sources were copied.

State: ~/.smithers/calendar_sync.json. Run with the Smithers venv's python:
    ~/.smithers/venv/bin/python sync_calendars.py [--dry-run] [--days 60]
Prints a short summary for the morning briefing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pickle
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

HOME_DIR = Path(os.environ.get("SMITHERS_HOME", Path.home() / ".smithers")).expanduser()
STATE_FILE = HOME_DIR / "calendar_sync.json"
APP = os.environ.get("SMITHERS_URL", "http://127.0.0.1:8020")
TAG_FROM, TAG_ID = "smithersSyncFrom", "smithersSyncId"


def load_accounts() -> dict:
    cfg = json.loads((HOME_DIR / "config.json").read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in cfg.get("accounts", {}).items()}


def credentials(account: str):
    """The account's saved token, refreshed if needed. Never starts the
    interactive OAuth flow: this runs unattended at 6 am."""
    token_file = HOME_DIR / f"token_{account}.pickle"
    with open(token_file, "rb") as f:
        creds = pickle.load(f)
    if not creds.valid:
        if not (creds.expired and creds.refresh_token):
            raise RuntimeError(f"{account}: Google token is invalid; re-run setup.py --authorize")
        creds.refresh(Request())
        with open(token_file, "wb") as f:
            pickle.dump(creds, f)
    return creds


def list_events(svc, start: datetime, end: datetime) -> list[dict]:
    items, page = [], None
    while True:
        resp = svc.events().list(
            calendarId="primary", timeMin=start.isoformat(), timeMax=end.isoformat(),
            singleEvents=True, showDeleted=False, maxResults=2500, pageToken=page).execute()
        items += resp.get("items", [])
        page = resp.get("nextPageToken")
        if not page:
            return items


def tag(ev: dict) -> tuple[str, str] | None:
    p = (ev.get("extendedProperties") or {}).get("private") or {}
    return (p[TAG_FROM], p[TAG_ID]) if TAG_FROM in p and TAG_ID in p else None


def declined(ev: dict) -> bool:
    return any(a.get("self") and a.get("responseStatus") == "declined"
               for a in ev.get("attendees", []))


def instant(t: dict) -> str:
    """A comparable key for a start or end: the UTC instant, or the date."""
    if "dateTime" in t:
        return datetime.fromisoformat(t["dateTime"].replace("Z", "+00:00")) \
            .astimezone(timezone.utc).isoformat()
    return t.get("date", "")


def meeting_link(ev: dict) -> str:
    for ep in (ev.get("conferenceData") or {}).get("entryPoints", []):
        if ep.get("entryPointType") == "video" and ep.get("uri"):
            return ep["uri"]
    return ev.get("hangoutLink", "")


def copy_body(src: dict, src_account: str) -> dict:
    desc = src.get("description", "") or ""
    link = meeting_link(src)
    if link and link not in desc:
        desc = f"Meeting link: {link}\n\n{desc}".strip()
    body = {"summary": src.get("summary", "(no title)"), "description": desc,
            "location": src.get("location", ""),
            "start": {k: v for k, v in src["start"].items() if k in ("date", "dateTime", "timeZone")},
            "end": {k: v for k, v in src["end"].items() if k in ("date", "dateTime", "timeZone")},
            "transparency": src.get("transparency", "opaque"),
            "extendedProperties": {"private": {TAG_FROM: src_account, TAG_ID: src["id"]}}}
    return body


def differences(copy: dict, want: dict) -> list[str]:
    diffs = []
    if (copy.get("summary") or "") != (want.get("summary") or ""):
        diffs.append("title")
    if instant(copy["start"]) != instant(want["start"]) or instant(copy["end"]) != instant(want["end"]):
        diffs.append("time")
    if (copy.get("description") or "").strip() != (want.get("description") or "").strip():
        diffs.append("description")
    return diffs


def post_proposal(note: str, changes: list[dict]) -> None:
    req = urllib.request.Request(
        APP + "/api/calendar/proposals", method="POST",
        data=json.dumps({"note": note, "changes": changes}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        r.read()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=60, help="days ahead to sync (default 60)")
    ap.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    args = ap.parse_args()

    accounts = list(load_accounts())
    if len(accounts) < 2:
        print("Calendar sync: fewer than two accounts configured; nothing to do.")
        return 0

    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    end = start + timedelta(days=args.days + 1)
    # Copies are looked for in a wider window, so a source that moved far
    # still finds its copy.
    copy_start, copy_end = start - timedelta(days=30), end + timedelta(days=120)

    state = {"copied": {}, "proposed": []}
    try:
        state.update(json.loads(STATE_FILE.read_text()))
    except Exception:
        pass
    proposed_before = set(state["proposed"])

    svcs, events, copies, errors = {}, {}, {}, []
    for a in accounts:
        try:
            svcs[a] = build("calendar", "v3", credentials=credentials(a), cache_discovery=False)
            events[a] = [e for e in list_events(svcs[a], start, end)
                         if e.get("status") != "cancelled"]
            copies[a] = {tag(e): e for e in list_events(svcs[a], copy_start, copy_end) if tag(e)}
        except Exception as ex:
            errors.append(f"{a}: {ex}")
    if errors:
        print("Calendar sync failed: " + "; ".join(errors))
        return 1

    added, changes = [], []
    for src_acct in accounts:
        for ev in events[src_acct]:
            if tag(ev) or declined(ev):
                continue                    # never copy a copy or a declined event
            for dst in accounts:
                if dst == src_acct:
                    continue
                key = f"{src_acct}:{ev['id']}>{dst}"
                if (src_acct, ev["id"]) in copies[dst] or key in state["copied"]:
                    continue                # already copied (or the user deleted the copy)
                # Already there: the same invitation, the same title at the same
                # start, or any event with exactly the same start and end (the
                # same meeting entered on each calendar under its own title).
                same = [d for d in events[dst] if not tag(d) and (
                    (ev.get("iCalUID") and d.get("iCalUID") == ev.get("iCalUID")) or
                    ((d.get("summary") or "").strip().lower() == (ev.get("summary") or "").strip().lower()
                     and instant(d["start"]) == instant(ev["start"])) or
                    (instant(d["start"]) == instant(ev["start"])
                     and instant(d["end"]) == instant(ev["end"])))]
                if same:
                    continue                # already on both calendars
                body = copy_body(ev, src_acct)
                if not args.dry_run:
                    made = svcs[dst].events().insert(calendarId="primary", body=body).execute()
                    state["copied"][key] = made.get("id", "")
                added.append(f"{body['summary']} ({instant(ev['start'])[:16]}) {src_acct} -> {dst}")

    # Copies whose source changed, was cancelled, or was declined: propose.
    for dst in accounts:
        for (src_acct, src_id), cp in copies[dst].items():
            if src_acct not in svcs:
                continue
            try:
                src = svcs[src_acct].events().get(calendarId="primary", eventId=src_id).execute()
            except HttpError as ex:
                if ex.resp.status not in (404, 410):
                    continue
                src = {"status": "cancelled"}
            title = cp.get("summary", "(no title)")
            if src.get("status") == "cancelled" or declined(src):
                why = "cancelled" if src.get("status") == "cancelled" else "declined"
                change = {"action": "delete", "event_id": cp["id"], "account": dst, "title": title,
                          "reason": f"the original on {src_acct} was {why}"}
            else:
                want = copy_body(src, src_acct)
                diffs = differences(cp, want)
                if not diffs:
                    continue
                if "time" in diffs and ("date" in want["start"] or "date" in cp["start"]):
                    # The app cannot move an all-day event: delete the copy and
                    # let the next run copy the source afresh.
                    state["copied"].pop(f"{src_acct}:{src_id}>{dst}", None)
                    change = {"action": "delete", "event_id": cp["id"], "account": dst, "title": title,
                              "reason": f"the original on {src_acct} moved; it will be copied again"}
                else:
                    change = {"action": "update", "event_id": cp["id"], "account": dst, "title": title,
                              "reason": f"the original on {src_acct} changed: {', '.join(diffs)}"}
                    if "title" in diffs:
                        change["new_title"] = want["summary"]
                    if "time" in diffs:
                        change["new_start"] = want["start"]["dateTime"]
                        change["new_end"] = want["end"]["dateTime"]
                    if "description" in diffs:
                        change["new_description"] = want["description"]
            sig = hashlib.sha1(json.dumps(change, sort_keys=True).encode()).hexdigest()[:16]
            if sig in proposed_before:
                continue                    # already proposed; the user applied or discarded it
            change["_sig"] = sig
            changes.append(change)

    if changes and not args.dry_run:
        try:
            post_proposal("Calendar sync: copies whose originals changed",
                          [{k: v for k, v in c.items() if k != "_sig"} for c in changes])
            state["proposed"] = (state["proposed"] + [c["_sig"] for c in changes])[-2000:]
        except Exception as ex:
            print(f"Calendar sync: could not post the proposal to Smithers ({ex}).")
    if not args.dry_run:
        STATE_FILE.write_text(json.dumps(state, indent=1))

    verb = "Would copy" if args.dry_run else "Copied"
    print(f"Calendar sync{' (dry run)' if args.dry_run else ''}: {verb} {len(added)} event(s); "
          f"{len(changes)} change(s) {'to propose' if args.dry_run else 'proposed'}.")
    for line in added:
        print("  + " + line)
    for c in changes:
        print(f"  ? {c['action']} {c['title']} on {c['account']}: {c['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
