"""Smithers Gmail MCP server.

Exposes your Gmail and Google Calendar to an agent as MCP tools --- the same
read/send/calendar functions Smithers uses, repackaged as a connector. Run this
locally with the OAuth credentials you already set up for Smithers
(credentials.json and token_<account>.pickle in this folder), then point the
Smithers agent's `gmail` connector at it.

It exposes a send tool, but the agent is configured not to use it --- sending is a
human action in the agent's Outbox. The agent reads and drafts; you approve and
the send happens through this connector.

Config: set ACCOUNTS to a JSON map of label -> email via the ACCOUNTS env var,
e.g.  ACCOUNTS='{"personal":"you@gmail.com","work":"you@org.com"}'.
Defaults to the two accounts below if unset.
"""
import os
import re
import html
import json
import base64
import pickle
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import uvicorn
from mcp.server.fastmcp import FastMCP
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# OAuth secrets live outside the package: they are per-user, and reinstalling or
# updating the skill must never move or wipe them. SMITHERS_HOME overrides.
HERE = Path(__file__).parent
HOME_DIR = Path(os.environ.get("SMITHERS_HOME", Path.home() / ".smithers")).expanduser()
HOME_DIR.mkdir(parents=True, exist_ok=True)
CREDS_FILE = HOME_DIR / "credentials.json"


def _local_timezone() -> str:
    """The machine's IANA time zone name, e.g. "Europe/Zurich".

    Events created or edited without a UTC offset are placed in this zone, so it
    must follow the machine rather than a hard-coded city: the user travels.
    Order: the TZ env var (if it names an IANA zone), then the /etc/localtime
    symlink (macOS and most Linux), then /etc/timezone (Debian), then UTC.
    """
    tz = os.environ.get("TZ", "").strip().lstrip(":")
    if tz and "/" in tz and not tz.startswith("/"):
        return tz
    try:
        target = os.path.realpath("/etc/localtime")
        marker = "zoneinfo/"
        if marker in target:
            name = target.split(marker, 1)[1]
            if name.startswith("posix/") or name.startswith("right/"):
                name = name.split("/", 1)[1]
            if name:
                return name
    except OSError:
        pass
    try:
        name = Path("/etc/timezone").read_text(encoding="utf-8").strip()
        if name:
            return name
    except OSError:
        pass
    return "UTC"


# TIMEZONE overrides; otherwise follow the machine. Read once at startup, so a
# connector left running across a time-zone change keeps the old zone until it
# is restarted.
TIMEZONE = os.environ.get("TIMEZONE", "").strip() or _local_timezone()

def _load_accounts() -> dict:
    """Which Google accounts this install serves, as {label: email}. Comes from
    the user's own ~/.smithers/config.json --- nothing is baked into the package.
    ACCOUNTS overrides for one-off runs. The same loader lives in backend/app.py.
    """
    raw = os.environ.get("ACCOUNTS")
    if raw:
        try:
            return dict(json.loads(raw))
        except Exception:
            pass
    try:
        cfg = json.loads((HOME_DIR / "config.json").read_text(encoding="utf-8"))
        accts = cfg.get("accounts")
        if isinstance(accts, dict):
            return {str(k): str(v) for k, v in accts.items()}
    except Exception:
        pass
    return {}


ACCOUNTS = _load_accounts()

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


def get_credentials(account: str):
    token_file = HOME_DIR / f"token_{account}.pickle"
    creds = None
    if token_file.exists():
        with open(token_file, "rb") as f:
            creds = pickle.load(f)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_file, "wb") as f:
            pickle.dump(creds, f)
        return creds
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
    creds = flow.run_local_server(port=0)
    with open(token_file, "wb") as f:
        pickle.dump(creds, f)
    return creds


def _strip_html(text):
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", text)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def _decode_part(payload):
    data = payload.get("body", {}).get("data", "")
    if not data:
        return ""
    return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")


def _find_body(payload, mime_wanted):
    if payload.get("mimeType", "") == mime_wanted:
        b = _decode_part(payload)
        if b:
            return b
    for part in payload.get("parts", []):
        b = _find_body(part, mime_wanted)
        if b:
            return b
    return ""


def _extract_body(payload):
    plain = _find_body(payload, "text/plain")
    if plain:
        return plain
    htm = _find_body(payload, "text/html")
    if htm:
        return _strip_html(htm)
    return ""


mcp = FastMCP("SmithersGmail", host="127.0.0.1")


@mcp.tool()
def list_inbox() -> str:
    """List inbox threads from the last day that have not been replied to, across
    all accounts. Deduplicates by subject. Returns account + message_id for each."""
    seen, errors = {}, []
    for account in ACCOUNTS:
        try:
            svc = build("gmail", "v1", credentials=get_credentials(account))
            result = svc.users().threads().list(
                userId="me", q="in:inbox newer_than:1d", maxResults=50).execute()
            for item in result.get("threads", []):
                thread = svc.users().threads().get(
                    userId="me", id=item["id"], format="metadata",
                    metadataHeaders=["From", "To", "Cc", "Subject", "Date"]).execute()
                last = thread["messages"][-1]
                headers = {h["name"]: h["value"] for h in last["payload"].get("headers", [])}
                subject = headers.get("Subject", "")
                key = subject.strip().lower()
                replied = "SENT" in last.get("labelIds", [])
                if key not in seen:
                    seen[key] = {"replied": replied, "candidate": None if replied else {
                        "account": account, "message_id": last["id"], "thread_id": thread["id"],
                        "subject": subject, "from": headers.get("From", ""),
                        "to": headers.get("To", ""), "cc": headers.get("Cc", ""),
                        "date": headers.get("Date", ""), "snippet": last.get("snippet", "")}}
                elif replied:
                    seen[key]["replied"] = True
        except Exception as ex:
            errors.append({"account": account, "error": str(ex)})
    out = [v["candidate"] for v in seen.values() if not v["replied"] and v["candidate"]]
    out.extend(errors)
    return json.dumps(out, indent=2)


@mcp.tool()
def get_message(message_id: str, account: str = "") -> str:
    """Return the full body of a message. The 'from' header is the verified sender.
    Pass the account from the list_inbox/search_inbox result that gave you the
    message_id; if omitted, every configured account is tried in turn."""
    accounts = [account] if account else list(ACCOUNTS)
    for acct in accounts:
        try:
            svc = build("gmail", "v1", credentials=get_credentials(acct))
            m = svc.users().messages().get(userId="me", id=message_id, format="full").execute()
            headers = {h["name"]: h["value"] for h in m["payload"].get("headers", [])}
            return json.dumps({
                "account": acct, "message_id": message_id,
                "from": headers.get("From", ""), "to": headers.get("To", ""),
                "subject": headers.get("Subject", ""), "date": headers.get("Date", ""),
                "thread_id": m.get("threadId", ""),
                "body": _extract_body(m.get("payload", {})) or "(no body)"}, indent=2)
        except Exception:
            continue
    return json.dumps({"error": f"Message {message_id} not found"})


@mcp.tool()
def search_inbox(query: str, max_results: int = 20) -> str:
    """Search email across all accounts with Gmail search syntax
    (e.g. 'from:x@y.com', 'subject:meeting', 'newer_than:7d')."""
    results = []
    for account in ACCOUNTS:
        try:
            svc = build("gmail", "v1", credentials=get_credentials(account))
            resp = svc.users().messages().list(
                userId="me", q=query, maxResults=max_results).execute()
            for msg in resp.get("messages", []):
                m = svc.users().messages().get(
                    userId="me", id=msg["id"], format="metadata",
                    metadataHeaders=["From", "Subject", "Date"]).execute()
                headers = {h["name"]: h["value"] for h in m["payload"].get("headers", [])}
                results.append({
                    "account": account, "message_id": msg["id"],
                    "from": headers.get("From", ""), "subject": headers.get("Subject", ""),
                    "date": headers.get("Date", ""), "snippet": m.get("snippet", "")})
        except Exception as ex:
            results.append({"account": account, "error": str(ex)})
    return json.dumps(results, indent=2)


@mcp.tool()
def get_emails_for_contact(email_address: str) -> str:
    """Return recent (14 days) email threads to or from a specific contact,
    across all accounts. Returns snippets only --- use get_message for full
    bodies. The 'from' header is the verified sender."""
    threads = []
    for account in ACCOUNTS:
        try:
            svc = build("gmail", "v1", credentials=get_credentials(account))
            query = f"from:{email_address} OR to:{email_address} newer_than:14d"
            result = svc.users().messages().list(
                userId="me", q=query, maxResults=10).execute()
            for msg in result.get("messages", []):
                m = svc.users().messages().get(
                    userId="me", id=msg["id"], format="metadata",
                    metadataHeaders=["From", "Subject", "Date"]).execute()
                headers = {h["name"]: h["value"] for h in m["payload"].get("headers", [])}
                threads.append({
                    "account": account, "message_id": msg["id"],
                    "subject": headers.get("Subject", ""), "from": headers.get("From", ""),
                    "date": headers.get("Date", ""), "snippet": m.get("snippet", "")})
        except Exception as ex:
            threads.append({"account": account, "error": str(ex)})
    return json.dumps(threads, indent=2)


@mcp.tool()
def search_emails_for_meetings() -> str:
    """Search all accounts for emails from the last 7 days whose subject suggests
    a meeting invitation (meeting, zoom, call, webinar, conference, invite,
    invitation, schedule). Returns snippets only."""
    results = []
    query = (
        "newer_than:7d ("
        "subject:meeting OR subject:zoom OR subject:call OR subject:webinar OR "
        "subject:conference OR subject:invite OR subject:invitation OR subject:schedule"
        ")"
    )
    for account in ACCOUNTS:
        try:
            svc = build("gmail", "v1", credentials=get_credentials(account))
            resp = svc.users().messages().list(
                userId="me", q=query, maxResults=30).execute()
            for msg in resp.get("messages", []):
                m = svc.users().messages().get(
                    userId="me", id=msg["id"], format="metadata",
                    metadataHeaders=["From", "Subject", "Date"]).execute()
                headers = {h["name"]: h["value"] for h in m["payload"].get("headers", [])}
                results.append({
                    "account": account, "message_id": msg["id"],
                    "subject": headers.get("Subject", ""), "from": headers.get("From", ""),
                    "date": headers.get("Date", ""), "snippet": m.get("snippet", "")})
        except Exception as ex:
            results.append({"account": account, "error": str(ex)})
    return json.dumps(results, indent=2)


@mcp.tool()
def get_message_html(message_id: str, account: str = "") -> str:
    """Return a message's raw HTML body (if any) and plain-text body, for
    rendering in a mail viewer. Prefer get_message for reading content as an
    agent; this tool exists for the app's email view."""
    accounts = [account] if account in ACCOUNTS else list(ACCOUNTS)
    for acct in accounts:
        try:
            svc = build("gmail", "v1", credentials=get_credentials(acct))
            m = svc.users().messages().get(userId="me", id=message_id, format="full").execute()
            payload = m.get("payload", {})
            return json.dumps({
                "account": acct, "message_id": message_id,
                "html": _find_body(payload, "text/html") or None,
                "text": _find_body(payload, "text/plain") or None})
        except Exception:
            continue
    return json.dumps({"error": f"Message {message_id} not found"})


def _collect_attachments(payload):
    result = []
    for part in payload.get("parts", []):
        filename = part.get("filename", "")
        att_id = part.get("body", {}).get("attachmentId", "")
        if filename and att_id:
            result.append({
                "filename": filename, "attachment_id": att_id,
                "mime_type": part.get("mimeType", ""),
                "size": part.get("body", {}).get("size", 0)})
        result.extend(_collect_attachments(part))
    return result


@mcp.tool()
def list_attachments(message_id: str, account: str = "") -> str:
    """List a message's attachments (filename, attachment_id, mime_type, size)."""
    accounts = [account] if account in ACCOUNTS else list(ACCOUNTS)
    for acct in accounts:
        try:
            svc = build("gmail", "v1", credentials=get_credentials(acct))
            m = svc.users().messages().get(userId="me", id=message_id, format="full").execute()
            return json.dumps({"account": acct,
                               "attachments": _collect_attachments(m.get("payload", {}))})
        except Exception:
            continue
    return json.dumps({"error": f"Message {message_id} not found"})


@mcp.tool()
def get_attachment(message_id: str, attachment_id: str, account: str) -> str:
    """Return one attachment's content as base64 (urlsafe) with its size."""
    try:
        svc = build("gmail", "v1", credentials=get_credentials(account))
        att = svc.users().messages().attachments().get(
            userId="me", messageId=message_id, id=attachment_id).execute()
        return json.dumps({"data": att.get("data", ""), "size": att.get("size", 0)})
    except Exception as ex:
        return json.dumps({"error": str(ex)})


# Title fragments: if two same-start-time events both contain any of these
# substrings (case-insensitive), treat them as duplicates and keep the longer title.
_DEDUP_FRAGMENTS = []


def _dedup_events(events):
    seen, unique = set(), []
    for e in events:
        if "error" in e:
            unique.append(e)
            continue
        key = (e.get("title", "").strip().lower(), e.get("start", ""))
        if key not in seen:
            seen.add(key)
            unique.append(e)
    real = [(i, e) for i, e in enumerate(unique) if "error" not in e]
    to_remove = set()
    for ci in range(len(real)):
        for cj in range(ci + 1, len(real)):
            i, a = real[ci]
            j, b = real[cj]
            if a.get("start") != b.get("start"):
                continue
            ta, tb = a.get("title", ""), b.get("title", "")
            for frag in _DEDUP_FRAGMENTS:
                fl = frag.lower()
                if fl in ta.lower() and fl in tb.lower():
                    to_remove.add(i if len(tb) >= len(ta) else j)
                    break
    return [e for k, e in enumerate(unique) if k not in to_remove]


@mcp.tool()
def list_calendar(start_date: str = "", end_date: str = "") -> str:
    """List calendar events across all accounts, deduplicated across calendars.
    Defaults to the next 7 days; pass start_date and end_date (YYYY-MM-DD) for a
    custom range. Each event includes event_id, account, attendees (external
    only), date, and location."""
    events = []
    own_emails = set(ACCOUNTS.values())
    for account in ACCOUNTS:
        try:
            svc = build("calendar", "v3", credentials=get_credentials(account))
            if start_date and end_date:
                start, end = f"{start_date}T00:00:00Z", f"{end_date}T23:59:59Z"
            else:
                now = datetime.now(timezone.utc)
                start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
                end = (now + timedelta(days=7)).replace(hour=23, minute=59, second=59).isoformat()
            result = svc.events().list(
                calendarId="primary", timeMin=start, timeMax=end,
                singleEvents=True, orderBy="startTime").execute()
            for e in result.get("items", []):
                attendees = [
                    a["email"] for a in e.get("attendees", [])
                    if not a.get("self") and a.get("email") and a["email"] not in own_emails]
                s = e["start"].get("dateTime", e["start"].get("date", ""))
                en = e["end"].get("dateTime", e["end"].get("date", ""))
                events.append({"account": account, "event_id": e.get("id", ""),
                               "title": e.get("summary", "(no title)"),
                               "start": s, "end": en, "date": s[:10],
                               "attendees": attendees,
                               "location": e.get("location", "")})
        except Exception as ex:
            events.append({"account": account, "error": str(ex)})
    return json.dumps(_dedup_events(events), indent=2)


@mcp.tool()
def get_calendar_event(event_id: str, account: str) -> str:
    """Return full details of one calendar event: times, location, description,
    meeting link, organizer, and attendees with response status."""
    try:
        svc = build("calendar", "v3", credentials=get_credentials(account))
        event = svc.events().get(calendarId="primary", eventId=event_id).execute()
        meeting_url = event.get("hangoutLink", "")
        for ep in event.get("conferenceData", {}).get("entryPoints", []):
            if ep.get("entryPointType") == "video":
                meeting_url = ep.get("uri", meeting_url)
                break
        attendees = [{"email": a.get("email", ""), "name": a.get("displayName", ""),
                      "status": a.get("responseStatus", ""), "self": a.get("self", False)}
                     for a in event.get("attendees", [])]
        start, end = event.get("start", {}), event.get("end", {})
        return json.dumps({
            "account": account, "event_id": event_id,
            "title": event.get("summary", ""),
            "start": start.get("dateTime", start.get("date", "")),
            "end": end.get("dateTime", end.get("date", "")),
            "location": event.get("location", ""),
            "description": event.get("description", ""),
            "meeting_url": meeting_url,
            "organizer": event.get("organizer", {}).get("email", ""),
            "attendees": attendees,
            "status": event.get("status", "")})
    except Exception as ex:
        return json.dumps({"error": str(ex)})


@mcp.tool()
def add_calendar_event(title: str, start_datetime: str, end_datetime: str,
                       description: str = "", account: str = "") -> str:
    """Add an event. Times are ISO 8601, e.g. 2026-06-12T14:00:00. If account is
    given, only that calendar gets the event; if empty, it is added to all
    calendars."""
    accounts = [account] if account in ACCOUNTS else list(ACCOUNTS)
    added, errors = [], []
    for acct in accounts:
        try:
            svc = build("calendar", "v3", credentials=get_credentials(acct))
            event = {"summary": title, "description": description,
                     "start": {"dateTime": start_datetime, "timeZone": TIMEZONE},
                     "end": {"dateTime": end_datetime, "timeZone": TIMEZONE}}
            result = svc.events().insert(calendarId="primary", body=event).execute()
            added.append({"account": acct, "event_id": result.get("id", "")})
        except Exception as ex:
            errors.append({"account": acct, "error": str(ex)})
    return json.dumps({"added": added, "errors": errors})


@mcp.tool()
def update_calendar_event(event_id: str, account: str,
                          title: Optional[str] = None,
                          start_datetime: Optional[str] = None,
                          end_datetime: Optional[str] = None,
                          description: Optional[str] = None) -> str:
    """Update an existing calendar event's title, times, and description.

    This is a partial update: a field that is left out keeps whatever the event
    already has. Only description distinguishes "" from omitted --- passing an
    empty description clears it, while an empty title or time is treated as
    "leave alone" rather than sent on to Google, which rejects a blank one."""
    try:
        svc = build("calendar", "v3", credentials=get_credentials(account))
        event = svc.events().get(calendarId="primary", eventId=event_id).execute()
        if title:
            event["summary"] = title
        if description is not None:
            event["description"] = description
        if start_datetime:
            event["start"] = {"dateTime": start_datetime, "timeZone": TIMEZONE}
        if end_datetime:
            event["end"] = {"dateTime": end_datetime, "timeZone": TIMEZONE}
        svc.events().update(calendarId="primary", eventId=event_id, body=event).execute()
        return json.dumps({"status": "updated", "account": account, "event_id": event_id})
    except Exception as ex:
        return json.dumps({"error": str(ex)})


@mcp.tool()
def delete_calendar_event(event_id: str, account: str) -> str:
    """Delete a calendar event from one account's calendar."""
    try:
        svc = build("calendar", "v3", credentials=get_credentials(account))
        svc.events().delete(calendarId="primary", eventId=event_id).execute()
        return json.dumps({"status": "deleted", "account": account, "event_id": event_id})
    except Exception as ex:
        return json.dumps({"error": str(ex)})


@mcp.tool()
def send_email(to: str, subject: str, body: str, account: str = "",
               cc: str = "", thread_id: str = "") -> str:
    """Send an email through Gmail. If account is empty, the first configured
    account is used. Pass thread_id to keep a reply in its thread."""
    acct = account or next(iter(ACCOUNTS))
    try:
        svc = build("gmail", "v1", credentials=get_credentials(acct))
        msg = MIMEText(body)
        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        send_body = {"raw": raw}
        if thread_id:
            send_body["threadId"] = thread_id
        svc.users().messages().send(userId="me", body=send_body).execute()
        return json.dumps({"status": "sent", "account": acct, "to": to})
    except Exception as ex:
        return json.dumps({"error": str(ex)})


if __name__ == "__main__":
    app = mcp.streamable_http_app()
    port = int(os.environ.get("PORT", 8800))
    uvicorn.run(app, host="127.0.0.1", port=port)
