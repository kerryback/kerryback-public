import os
import re
import hmac
import secrets
import json
import uuid
import base64
import asyncio
import mimetypes
import html as html_module
from collections import defaultdict
from datetime import date as date_cls, datetime as dt_cls
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from dotenv import load_dotenv

try:
    import anthropic
except ImportError:
    anthropic = None

load_dotenv()

# ---------------------------------------------------------------------------
# Smithers --- the personal email and calendar assistant --- as a Claude Code
# skill.  The app holds the mailbox, calendar, tasks, and drafts; Claude Code is
# the assistant.  There is no model inside this process and no API key: the app
# makes no model calls of its own.  Claude Code reads the mailbox through the
# same Gmail connector (mcp-servers/gmail_mcp.py, both Google accounts from one
# server) and writes back into the app over HTTP --- POST /api/drafts to park a
# reply in the Compose tab, POST /api/briefing to publish the morning overview.
#
# The trust boundary is the point of the design.  The agent drafts; the human
# sends.  Sending mail, editing an event, deleting events, and applying a
# calendar proposal are the user's own clicks in the browser.  The routes behind
# those clicks (see USER_ONLY_ROUTES below) do exist, and this process listens on
# 127.0.0.1, where Claude Code's Bash tool can reach it.  Three things keep the
# agent off them, and none of them is a hard guarantee:
#   1. SKILL.md lists the user-only routes and tells the agent never to call them.
#   2. The plugin's PreToolUse hook (hooks/block_user_routes.py) denies tool calls
#      that target those paths.  It matches text, so a determined agent can
#      disguise a request and get past it.
#   3. Each of those routes needs the per-launch token below, which only the page
#      served at / carries.  That stops a careless curl, not an agent that reads
#      the page first.
# ---------------------------------------------------------------------------
CONNECTOR_URL = os.environ.get(
    "CONNECTOR_URL", "http://127.0.0.1:8800/mcp")
CONNECTOR_TOKEN = os.environ.get("CONNECTOR_TOKEN", "")

# Personal state (tasks, drafts, the saved briefing) lives outside the package so
# updating or reinstalling the skill never wipes it.
HERE = Path(__file__).parent
DATA_DIR = Path(os.environ.get("SMITHERS_HOME", Path.home() / ".smithers")).expanduser()
DATA_DIR.mkdir(parents=True, exist_ok=True)
TASKS_FILE = DATA_DIR / "tasks.json"
DRAFTS_FILE = DATA_DIR / "drafts.json"
PROPOSALS_FILE = DATA_DIR / "proposals.json"
BRIEFING_JSON = DATA_DIR / "briefing.json"
BANNER_PATH = DATA_DIR / "smithers.webp"  # optional, the user's own
CONFIG_FILE = DATA_DIR / "config.json"
MAX_DRAFTS = 50            # keep the Compose tab from growing without bound


def _load_accounts() -> dict:
    """Which Google accounts this install serves, as {label: email}.

    Whose mailbox this is comes from the user's own ~/.smithers/config.json ---
    nothing about the accounts is baked into the package, so a second person
    installs the plugin, writes their own config, and signs in. The ACCOUNTS env
    var overrides for one-off runs. The same loader lives in the connector; the
    two processes read the same file. An empty result means "not set up yet" and
    the UI says so rather than pretending to be someone else's mailbox.
    """
    raw = os.environ.get("ACCOUNTS")
    if raw:
        try:
            return dict(json.loads(raw))
        except Exception:
            pass
    try:
        cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        accts = cfg.get("accounts")
        if isinstance(accts, dict):
            return {str(k): str(v) for k, v in accts.items()}
    except Exception:
        pass
    return {}


ACCOUNTS = _load_accounts()

# --- The page's token for user-only routes ------------------------------------
#
# A fresh random token per launch.  It is injected into the page served at /,
# and the page's JavaScript sends it as the X-Smithers-Action header on every
# user-only route.  A request without it gets 403 before any Gmail or Calendar
# call is made.
#
# This is defense in depth against a careless curl, not a security boundary
# against the agent: anything that can reach 127.0.0.1 can GET / and read the
# token out of the page.  The real limits on the agent are SKILL.md and the
# plugin's PreToolUse hook, and the hook can also be got round.
ACTION_TOKEN = secrets.token_urlsafe(32)
ACTION_HEADER = "X-Smithers-Action"
USER_ONLY_ROUTES = [            # documented in SKILL.md and blocked by the hook
    "POST   /api/email/send",
    "PATCH  /api/calendar/events/{event_id}",
    "DELETE /api/calendar/events/{event_id}",
    "POST   /api/calendar/events/delete",
    "POST   /api/calendar/proposals/{proposal_id}/apply",
    "POST   /api/chat",             # the Chat tab's Send; starts a Claude Code run
    "DELETE /api/chat",             # the Chat tab's New chat
]


def require_page_token(request: Request) -> None:
    """Reject a user-only request that lacks the page's token.  Runs as a route
    dependency, so FastAPI calls it before the body is validated and before the
    handler can reach the connector."""
    sent = request.headers.get(ACTION_HEADER, "")
    if not sent or not hmac.compare_digest(sent, ACTION_TOKEN):
        raise HTTPException(
            403, "This action is the user's own, from the Smithers page in the "
                 "browser. Reload the page if you restarted the app.")
ACCOUNT_LABELS = list(ACCOUNTS)
DEFAULT_ACCOUNT = ACCOUNT_LABELS[0] if ACCOUNT_LABELS else ""
MY_EMAILS = [e.lower() for e in ACCOUNTS.values() if e]

try:
    _banner_src = "data:image/webp;base64," + base64.b64encode(BANNER_PATH.read_bytes()).decode()
except Exception:
    _banner_src = ""


# --- Persistence --------------------------------------------------------------

def _load_tasks() -> list:
    if TASKS_FILE.exists():
        try:
            return json.loads(TASKS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_tasks(tasks: list) -> None:
    TASKS_FILE.write_text(json.dumps(tasks, indent=2), encoding="utf-8")


def _load_proposals() -> list:
    if PROPOSALS_FILE.exists():
        try:
            data = json.loads(PROPOSALS_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []
    return []


def _save_proposals(proposals: list) -> None:
    PROPOSALS_FILE.write_text(json.dumps(proposals, indent=2), encoding="utf-8")


def _load_drafts() -> list:
    if DRAFTS_FILE.exists():
        try:
            data = json.loads(DRAFTS_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []
    return []


def _save_drafts(drafts: list) -> None:
    DRAFTS_FILE.write_text(json.dumps(drafts, indent=2), encoding="utf-8")


def _load_briefing() -> tuple[str | None, str | None]:
    """Return (overview_html, generated_at) from disk."""
    if BRIEFING_JSON.exists():
        try:
            data = json.loads(BRIEFING_JSON.read_text(encoding="utf-8"))
            return ((data.get("overview") or "").strip() or None,
                    data.get("generated_at") or None)
        except Exception:
            return None, None
    return None, None


def _save_briefing(overview_html: str) -> str:
    generated_at = dt_cls.now().isoformat(timespec="seconds")
    BRIEFING_JSON.write_text(json.dumps({
        "generated_at": generated_at,
        "overview": overview_html,
    }, indent=2), encoding="utf-8")
    return generated_at


_briefing_html, _briefing_generated_at = _load_briefing()

# Set when the app is opened (the launcher posts /api/briefing/refresh-request)
# and cleared when a new briefing arrives.  The app cannot write the briefing
# itself --- it has no model --- so all it can do is record that one was asked
# for, show that in the Overview tab, and let Claude Code answer.
_briefing_requested_at: str | None = None
# How long the "refreshing" note stays up before we assume nobody is coming.
BRIEFING_REQUEST_TTL = 15 * 60


def _briefing_refresh_pending() -> bool:
    if not _briefing_requested_at:
        return False
    try:
        asked = dt_cls.fromisoformat(_briefing_requested_at)
    except ValueError:
        return False
    if (dt_cls.now() - asked).total_seconds() > BRIEFING_REQUEST_TTL:
        return False
    # A briefing published after the request answers it.
    if _briefing_generated_at:
        try:
            if dt_cls.fromisoformat(_briefing_generated_at) >= asked:
                return False
        except ValueError:
            pass
    return True


def _briefing_is_stale() -> bool:
    """True when the saved briefing was not generated today."""
    if not _briefing_generated_at:
        return True
    try:
        return dt_cls.fromisoformat(_briefing_generated_at).date() != date_cls.today()
    except ValueError:
        return True


# --- Connector access (the app is itself an MCP client of the connector) -----

def _conn_cfg():
    cfg = {"type": "http", "url": CONNECTOR_URL}
    if CONNECTOR_TOKEN:
        cfg["headers"] = {"Authorization": f"Bearer {CONNECTOR_TOKEN}"}
    return cfg


async def _call_connector(tool_name: str, args: dict) -> str:
    headers = {"Authorization": f"Bearer {CONNECTOR_TOKEN}"} if CONNECTOR_TOKEN else None
    async with streamablehttp_client(CONNECTOR_URL, headers=headers) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            res = await s.call_tool(tool_name, args)
            return res.content[0].text if res.content else "[]"


# --- Draft creation (used by POST /api/drafts) --------------------------------
#
# Claude Code parks a reply here instead of sending it. This is the only write
# path from the assistant toward the mailbox, and it stops well short of it: the
# draft lands in the Compose tab and goes nowhere until the human presses Send.

def _add_draft(*, to: str, subject: str, body: str, cc: str = "",
               account: str = "", thread_id: str = "") -> dict:
    account = (account or "").strip().lower()
    if account not in ACCOUNT_LABELS:
        account = DEFAULT_ACCOUNT
    draft = {
        "id": uuid.uuid4().hex[:12],
        "account": account,
        "to": to.strip(),
        "cc": (cc or "").strip(),
        "subject": (subject or "").strip(),
        "body": body or "",
        "thread_id": (thread_id or "").strip(),
        "created_at": dt_cls.now().isoformat(timespec="seconds"),
    }
    drafts = _load_drafts()
    drafts.append(draft)
    _save_drafts(drafts[-MAX_DRAFTS:])
    return draft


# --- Email classification (Needs Reply vs Other) -----------------------------

def _classify_emails_sync(items):
    """Split inbox items into (needs_reply, other) with a fast Haiku call.
    Falls back to everything-needs-reply if the call is unavailable or fails."""
    if not items:
        return [], []
    if anthropic is None or not os.environ.get("ANTHROPIC_API_KEY"):
        return items, []
    summary = "\n".join(
        f"{i}. From: {e.get('from','')} | Subject: {e.get('subject','')} | {e.get('snippet','')[:120]}"
        for i, e in enumerate(items)
    )
    try:
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content":
                f"Classify each email as 'reply' (needs a personal reply from the mailbox owner) "
                f"or 'other' (newsletter, automated, mailing list, CC-only, no-action-needed). "
                f"Return ONLY a JSON object, no explanation: {{\"reply\": [0,2,...], \"other\": [1,3,...]}}\n\n{summary}"}],
        )
        text = resp.content[0].text.strip()
        m = re.search(r"\{.*\}", text, re.DOTALL)
        result = json.loads(m.group() if m else text)
        reply_idx = set(result.get("reply", []))
        other_idx = set(result.get("other", []))
    except Exception:
        return items, []
    return (
        [items[i] for i in sorted(reply_idx) if i < len(items)],
        [items[i] for i in sorted(other_idx) if i < len(items)],
    )


# --- HTML rendering for the Calendar and Emails tabs -------------------------

# Account badges are coloured by position in the configured account list, so any
# set of labels gets distinct colours without naming them here.
_BADGE_STYLES = [
    "background:#dbeafe;color:#1d4ed8",   # blue
    "background:#fef3c7;color:#92400e",   # amber
    "background:#dcfce7;color:#166534",   # green
    "background:#ede9fe;color:#6d28d9",   # violet
]


def _account_badge(acct: str) -> tuple[str, str]:
    """(display label, inline style) for an account label."""
    if not acct:
        return "Mail", _BADGE_STYLES[0]
    try:
        idx = ACCOUNT_LABELS.index(acct)
    except ValueError:
        idx = len(_BADGE_STYLES) - 1
    return acct.replace("_", " ").title(), _BADGE_STYLES[idx % len(_BADGE_STYLES)]


def _email_card(e):
    acct = e.get("account") or DEFAULT_ACCOUNT
    label, badge = _account_badge(acct)
    # Gmail pre-escapes text (&#39; etc); unescape first to avoid double-escaping
    raw_from = html_module.unescape(e.get("from", ""))
    raw_subj = html_module.unescape(e.get("subject", ""))
    raw_snip = html_module.unescape(e.get("snippet", ""))
    attr_from = html_module.escape(raw_from)
    attr_subj = html_module.escape(raw_subj)
    disp_from = html_module.escape(raw_from, quote=False)
    disp_subj = html_module.escape(raw_subj, quote=False)
    disp_snip = html_module.escape(raw_snip, quote=False)
    attr_to = html_module.escape(html_module.unescape(e.get("to", "")))
    attr_cc = html_module.escape(html_module.unescape(e.get("cc", "")))
    return (
        f'<div class="email-item" data-from="{attr_from}" data-subject="{attr_subj}" data-account="{acct}" '
        f'data-message-id="{e.get("message_id","")}" data-thread-id="{e.get("thread_id","")}" '
        f'data-to="{attr_to}" data-cc="{attr_cc}" '
        f'style="padding:.75rem;border:1px solid #e2e8f0;border-radius:6px;margin-bottom:.5rem;background:#fff">'
        f'<span style="display:inline-block;padding:.1rem .5rem;border-radius:10px;font-size:.75rem;'
        f'font-weight:700;margin-right:.4rem;{badge}">{label}</span>'
        f'<strong>{disp_from}</strong>'
        f'<div style="font-weight:600;margin:.2rem 0">{disp_subj}</div>'
        f'<div style="color:#64748b;font-size:.85rem">{disp_snip}</div></div>'
    )


def _google_error_banner(errors):
    """Surface Gmail/Calendar failures (esp. expired auth) instead of letting
    them silently masquerade as 'no data'."""
    if not errors:
        return ""
    blob = " ".join(str(e.get("error", "")) for e in errors).lower()
    if any(k in blob for k in ("invalid_grant", "expired", "revoked", "token")):
        msg = ("Google sign-in has expired. Ask Claude Code to reconnect your "
               "Smithers accounts, or run <code>python scripts/setup.py "
               "--authorize</code> in the skill folder, then restart Smithers.")
    else:
        msg = "Couldn't reach Google: " + html_module.escape(
            "; ".join(str(e.get("error", ""))[:160] for e in errors))
    return (
        "<div style='padding:.7rem .9rem;border:1px solid #fca5a5;background:#fef2f2;"
        "color:#991b1b;border-radius:8px;margin-bottom:1rem;font-size:.88rem'>"
        f"&#9888; {msg}</div>"
    )


def _email_html(needs, other):
    if not needs and not other:
        return "<p style='color:#94a3b8;padding:.5rem'>No unreplied emails.</p>"
    parts = []
    if needs:
        parts.append("<div style='font-size:.75rem;font-weight:700;text-transform:uppercase;"
                     "letter-spacing:.06em;color:#dc2626;margin-bottom:.4rem'>Needs Reply</div>")
        parts.extend(_email_card(e) for e in needs)
    else:
        parts.append("<p style='color:#94a3b8;padding:.5rem 0'>No emails need a reply.</p>")
    if other:
        cards = "\n".join(_email_card(e) for e in other)
        parts.append(
            f"<details style='margin-top:.75rem'>"
            f"<summary style='cursor:pointer;font-size:.78rem;color:#94a3b8;font-weight:600;"
            f"list-style:none;padding:.3rem 0'>&#9658; Other ({len(other)})</summary>"
            f"<div style='margin-top:.5rem'>{cards}</div></details>"
        )
    return "\n".join(parts)


def _calendar_html(events):
    items = [e for e in events if "error" not in e]
    if not items:
        return "<p style='color:#94a3b8;padding:.5rem'>No events in the next 7 days.</p>"
    by_date = defaultdict(list)
    for e in items:
        by_date[e.get("date") or (e.get("start", "") or "")[:10]].append(e)
    today = date_cls.today().isoformat()
    parts = []
    for day in sorted(by_date):
        try:
            d = dt_cls.strptime(day, "%Y-%m-%d").date()
            label = d.strftime("%A, %B %-d") + (" --- Today" if day == today else "")
        except Exception:
            label = day or "(undated)"
        parts.append(
            f"<div style='font-size:.8rem;font-weight:700;text-transform:uppercase;"
            f"letter-spacing:.06em;color:#1a2744;margin:1rem 0 .4rem;padding-bottom:.2rem;"
            f"border-bottom:2px solid #e2e8f0'>{html_module.escape(label)}</div>")
        for e in by_date[day]:
            acct = e.get("account") or DEFAULT_ACCOUNT
            lbl, badge = _account_badge(acct)
            eid = html_module.escape(e.get("event_id", ""))
            title = html_module.escape(e.get("title", ""))
            start = html_module.escape(e.get("start", ""))
            time_str = ""
            if "T" in e.get("start", ""):
                try:
                    time_str = dt_cls.fromisoformat(e["start"].replace("Z", "+00:00")).strftime("%-I:%M %p")
                except Exception:
                    time_str = e["start"][11:16]
            parts.append(
                f'<details class="event-item" data-event-id="{eid}" data-title="{title}" '
                f'data-start="{start}" data-account="{acct}" '
                f'style="border:1px solid #e2e8f0;border-radius:6px;margin-bottom:.5rem;background:#fff;padding:.1rem">'
                f'<summary style="padding:.6rem .75rem;cursor:pointer;list-style:none;display:flex;align-items:center;gap:.5rem">'
                f'<span style="display:inline-block;padding:.1rem .5rem;border-radius:10px;font-size:.75rem;font-weight:700;{badge}">{lbl}</span>'
                f'<strong>{title}</strong>'
                + (f'<span style="color:#64748b;font-size:.85rem;margin-left:.3rem">{html_module.escape(time_str)}</span>' if time_str else '') +
                f'</summary>'
                f'<div class="event-detail-body" style="padding:.5rem 1rem;color:#475569;font-size:.88rem">'
                f'<span class="loading" style="color:#94a3b8;font-style:italic">Loading&hellip;</span>'
                f'</div></details>'
            )
    return "\n".join(parts)


# --- App ---------------------------------------------------------------------

app = FastAPI(title="Smithers")


class DraftPayload(BaseModel):
    to: str
    subject: str
    body: str
    cc: str = ""
    account: str = ""        # defaults to the first configured account
    thread_id: str = ""


class BriefingPayload(BaseModel):
    html: str


class EmailPayload(BaseModel):
    account: str = ""
    to: str
    cc: str = ""
    subject: str
    body: str
    thread_id: str = ""
    draft_id: str = ""      # set when sending a draft the agent parked in Compose


class EventPayload(BaseModel):
    account: str = ""
    title: str
    start: str
    end: str
    description: str = ""


class EventRef(BaseModel):
    event_id: str
    account: str = ""


class ProposedChange(BaseModel):
    action: str                    # "delete" or "update"
    event_id: str
    account: str = ""
    title: str = ""                # for display in the confirmation panel
    reason: str = ""               # why Smithers thinks this should change
    # update only --- the new values, omitted fields keep their current value
    new_title: str = ""
    new_start: str = ""
    new_end: str = ""
    new_description: str = ""


class ProposalPayload(BaseModel):
    note: str = ""                 # one line on what this proposal is about
    changes: list[ProposedChange]


class ApplyPayload(BaseModel):
    indexes: list[int] | None = None   # omit to apply every change


class DeleteEventsPayload(BaseModel):
    events: list[EventRef]


@app.get("/", response_class=HTMLResponse)
async def serve():
    return HTMLResponse(SHELL_HTML
                        .replace("__SMITHERS_SRC__", _banner_src)
                        .replace("__ACTION_TOKEN__", ACTION_TOKEN)
                        .replace("__MY_EMAILS__", json.dumps(MY_EMAILS))
                        .replace("__ACCOUNTS__", json.dumps(
                            [{"label": k, "email": v} for k, v in ACCOUNTS.items()])))


@app.get("/api/ping")
async def ping():
    return {"status": "ok"}


@app.get("/api/accounts")
async def api_accounts():
    """The configured accounts, in order. The first is the default. Empty until
    the user writes ~/.smithers/config.json and signs in."""
    return {"accounts": [{"label": k, "email": v} for k, v in ACCOUNTS.items()],
            "default": DEFAULT_ACCOUNT,
            "configured": bool(ACCOUNTS)}


@app.post("/api/briefing")
async def publish_briefing(payload: BriefingPayload):
    """Claude Code writes the morning overview here after reading the calendar
    and inbox. The app stores and timestamps it; it generates nothing itself."""
    global _briefing_html, _briefing_generated_at, _briefing_requested_at
    reply = (payload.html or "").strip()
    if not reply:
        raise HTTPException(400, "Empty briefing")
    # Keep only the HTML, dropping any chatty preamble that came with it.
    idx = reply.find("<div")
    _briefing_html = (reply[idx:] if idx >= 0
                      else f"<div class='card'>{html_module.escape(reply)}</div>")
    _briefing_generated_at = _save_briefing(_briefing_html)
    _briefing_requested_at = None          # the open request is answered
    return {"status": "published", "generated_at": _briefing_generated_at}


@app.get("/api/briefing/status")
async def briefing_status():
    """Whether the briefing on screen is today's, and whether a refresh has been
    asked for and not yet answered. The launcher reads this on every open."""
    return {"generated_at": _briefing_generated_at,
            "stale": _briefing_is_stale(),
            "refreshing": _briefing_refresh_pending(),
            "requested_at": _briefing_requested_at}


@app.post("/api/briefing/refresh-request")
async def request_briefing_refresh():
    """Record that a fresh briefing was asked for --- the launcher posts this
    every time Smithers is opened. The app writes nothing itself: it shows
    'refreshing' on the Overview tab until Claude Code POSTs the new briefing."""
    global _briefing_requested_at
    _briefing_requested_at = dt_cls.now().isoformat(timespec="seconds")
    return {"status": "requested", "requested_at": _briefing_requested_at,
            "generated_at": _briefing_generated_at, "stale": _briefing_is_stale()}


@app.get("/api/tasks")
async def get_tasks():
    return _load_tasks()


@app.post("/api/tasks")
async def save_tasks(request: Request):
    body = await request.json()
    if not isinstance(body, list):
        raise HTTPException(400, "Expected a JSON array")
    _save_tasks(body)
    return {"status": "saved"}


@app.post("/api/drafts")
async def create_draft(payload: DraftPayload):
    """Claude Code parks a drafted reply in the Compose tab. This sends nothing:
    the draft waits there until the human reviews it and presses Send."""
    if not payload.to.strip():
        raise HTTPException(400, "'to' is required")
    draft = _add_draft(to=payload.to, subject=payload.subject, body=payload.body,
                       cc=payload.cc, account=payload.account,
                       thread_id=payload.thread_id)
    return {"status": "drafted", "draft_id": draft["id"],
            "note": "Waiting in the Compose tab. Nothing was sent."}


# --- Read surface for Claude Code ---------------------------------------------
#
# Claude Code reaches the mailbox and calendar only through these endpoints, not
# by connecting to the connector itself. That is deliberate: the connector also
# exposes send_email, update_calendar_event, and delete_calendar_event, and
# registering it as an MCP server would hand those to every Claude session.
# Proxying here means the assistant gets exactly the read tools listed below, and
# the write paths stay behind the app's own buttons.

@app.get("/api/inbox")
async def api_inbox():
    """Unreplied messages, both accounts. Snippets only --- call /api/message for
    what a message actually says."""
    return json.loads(await _call_connector("list_inbox", {}))


@app.get("/api/message/{message_id}")
async def api_message(message_id: str, account: str = ""):
    """Full body of one message. Read this before summarizing or replying."""
    return json.loads(await _call_connector(
        "get_message", {"message_id": message_id, "account": account}))


@app.get("/api/search")
async def api_search(q: str, max_results: int = 20):
    return json.loads(await _call_connector(
        "search_inbox", {"query": q, "max_results": max_results}))


@app.get("/api/contact")
async def api_contact(email: str):
    """Recent correspondence with one person --- meeting-prep context."""
    return json.loads(await _call_connector(
        "get_emails_for_contact", {"email_address": email}))


@app.get("/api/meeting-invitations")
async def api_meeting_invitations():
    return json.loads(await _call_connector("search_emails_for_meetings", {}))


@app.get("/api/calendar")
async def api_calendar(start_date: str = "", end_date: str = ""):
    return json.loads(await _call_connector(
        "list_calendar", {"start_date": start_date, "end_date": end_date}))


@app.get("/api/section/overview")
async def section_overview():
    # The date and the "generated at" stamp are returned separately so the tab
    # header always shows today's real date and how old the briefing under it
    # is --- a briefing left over from a previous day is then obvious.
    meta = {"date": date_cls.today().strftime("%A, %B %-d, %Y"),
            "generated_at": _briefing_generated_at,
            "refreshing": _briefing_refresh_pending()}
    if _briefing_html:
        overview = re.sub(
            r"<p class=[\"']date-display[\"']>.*?</p>", "", _briefing_html, count=1
        ).strip()
        return {"html": overview, **meta}
    return {"html": "<p class='loading'>No Overview yet. Ask Claude Code when you "
                    "want your Overview updated and it will appear here.</p>", **meta}


@app.get("/api/section/calendar")
async def section_calendar():
    try:
        events = json.loads(await _call_connector("list_calendar", {}))
        errors = [e for e in events if "error" in e]
        return {"html": _google_error_banner(errors) + _calendar_html(events)}
    except Exception as ex:
        raise HTTPException(500, str(ex))


@app.get("/api/section/emails")
async def section_emails():
    try:
        emails = json.loads(await _call_connector("list_inbox", {}))
        errors = [e for e in emails if "error" in e]
        items = [e for e in emails if "error" not in e]
        needs, other = await asyncio.to_thread(_classify_emails_sync, items)
        return {"html": _google_error_banner(errors) + _email_html(needs, other)}
    except Exception as ex:
        raise HTTPException(500, str(ex))


# --- Email actions ------------------------------------------------------------

@app.get("/api/email/body")
async def email_body(account: str, message_id: str):
    try:
        data = json.loads(await _call_connector(
            "get_message_html", {"message_id": message_id, "account": account}))
        if "error" in data:
            raise HTTPException(500, data["error"])
        if data.get("html"):
            return {"html": data["html"], "text": None}
        return {"html": None, "text": data.get("text") or "(no body)"}
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(500, str(ex))


@app.get("/api/email/attachments")
async def email_attachments(account: str, message_id: str):
    try:
        data = json.loads(await _call_connector(
            "list_attachments", {"message_id": message_id, "account": account}))
        if "error" in data:
            raise HTTPException(500, data["error"])
        return {"attachments": data.get("attachments", [])}
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(500, str(ex))


@app.get("/api/email/attachment")
async def email_attachment(account: str, message_id: str, attachment_id: str,
                           filename: str = "attachment"):
    try:
        data = json.loads(await _call_connector("get_attachment", {
            "message_id": message_id, "attachment_id": attachment_id, "account": account}))
        if "error" in data:
            raise HTTPException(500, data["error"])
        content = base64.urlsafe_b64decode(data.get("data", "") + "==")
        mime, _ = mimetypes.guess_type(filename)
        return Response(
            content=content,
            media_type=mime or "application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(500, str(ex))


@app.post("/api/email/send", dependencies=[Depends(require_page_token)])
async def send_email(payload: EmailPayload):
    # The human composed (or reviewed the agent's draft) and clicked Send. The
    # agent is told never to call this route, the plugin's hook blocks it, and
    # it needs the page's token; see the comment at the top of this file.
    try:
        out = json.loads(await _call_connector("send_email", {
            "to": payload.to, "subject": payload.subject, "body": payload.body,
            "account": payload.account, "cc": payload.cc, "thread_id": payload.thread_id}))
        if "error" in out:
            raise HTTPException(500, out["error"])
        if payload.draft_id:
            _discard_draft(payload.draft_id)
        return {"status": "sent"}
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(500, str(ex))


# --- Drafts the agent parked in the Compose tab --------------------------------

def _discard_draft(draft_id: str) -> bool:
    drafts = _load_drafts()
    kept = [d for d in drafts if d.get("id") != draft_id]
    if len(kept) == len(drafts):
        return False
    _save_drafts(kept)
    return True


@app.get("/api/drafts")
async def list_drafts():
    return {"drafts": _load_drafts()}


@app.delete("/api/drafts/{draft_id}")
async def delete_draft(draft_id: str):
    if not _discard_draft(draft_id):
        raise HTTPException(404, "No such draft")
    return {"status": "discarded"}


# --- Calendar actions ----------------------------------------------------------

@app.post("/api/calendar/events")
async def add_event(payload: EventPayload):
    try:
        out = json.loads(await _call_connector("add_calendar_event", {
            "title": payload.title, "start_datetime": payload.start,
            "end_datetime": payload.end, "description": payload.description,
            "account": payload.account}))
        if out.get("errors"):
            raise HTTPException(500, json.dumps(out["errors"]))
        return {"status": "created"}
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(500, str(ex))


@app.patch("/api/calendar/events/{event_id}", dependencies=[Depends(require_page_token)])
async def update_event(event_id: str, payload: EventPayload):
    try:
        out = json.loads(await _call_connector("update_calendar_event", {
            "event_id": event_id, "account": payload.account,
            "title": payload.title, "start_datetime": payload.start,
            "end_datetime": payload.end, "description": payload.description}))
        if "error" in out:
            raise HTTPException(500, out["error"])
        return {"status": "updated"}
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(500, str(ex))


@app.post("/api/calendar/events/delete", dependencies=[Depends(require_page_token)])
async def delete_events(payload: DeleteEventsPayload):
    # Bulk delete from the Calendar tab. Like sending email, this is a human
    # action. Nothing makes it unreachable: the app listens on 127.0.0.1, where
    # the agent's Bash tool can reach it. What keeps the agent off it is SKILL.md
    # (which tells it never to call this route), the plugin's PreToolUse hook
    # (which denies tool calls that target it, but matches text and can be got
    # round), and the page's token (which a careless curl lacks, but which any
    # caller can read from the page). See the comment at the top of this file.
    if not payload.events:
        raise HTTPException(400, "No events given")
    deleted, failed = [], []
    for ref in payload.events:
        if not ref.event_id:
            continue
        try:
            out = json.loads(await _call_connector("delete_calendar_event", {
                "event_id": ref.event_id, "account": ref.account}))
            if "error" in out:
                failed.append({"event_id": ref.event_id, "error": out["error"]})
            else:
                deleted.append(ref.event_id)
        except Exception as ex:
            failed.append({"event_id": ref.event_id, "error": str(ex)})
    return {"deleted": deleted, "failed": failed}


@app.delete("/api/calendar/events/{event_id}", dependencies=[Depends(require_page_token)])
async def delete_event(event_id: str, account: str):
    try:
        out = json.loads(await _call_connector("delete_calendar_event", {
            "event_id": event_id, "account": account}))
        if "error" in out:
            raise HTTPException(500, out["error"])
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(500, str(ex))


# --- Proposed calendar changes -------------------------------------------------
#
# Claude Code may propose edits and deletions but may not perform them. A
# proposal is inert: it sits in the Calendar tab with its reasons until the human
# presses Apply, which is what actually reaches the connector. Discarding costs
# nothing. This is the same shape as a drafted reply waiting for Send.

def _proposal_summary(p: dict) -> dict:
    kinds = [c.get("action") for c in p.get("changes", [])]
    return {**p, "count": len(kinds),
            "deletes": kinds.count("delete"), "updates": kinds.count("update")}


@app.get("/api/calendar/proposals")
async def list_proposals():
    return {"proposals": [_proposal_summary(p) for p in _load_proposals()]}


@app.post("/api/calendar/proposals")
async def create_proposal(payload: ProposalPayload):
    """Claude Code proposes calendar changes for the user to confirm. Nothing is
    applied here --- this only puts the proposal in front of the human."""
    changes = [c for c in payload.changes if c.event_id]
    if not changes:
        raise HTTPException(400, "No changes with an event_id")
    for c in changes:
        if c.action not in ("delete", "update"):
            raise HTTPException(400, f"Unknown action: {c.action}")
    proposal = {
        "id": uuid.uuid4().hex[:12],
        "note": payload.note.strip(),
        "created_at": dt_cls.now().isoformat(timespec="seconds"),
        "changes": [c.model_dump() for c in changes],
    }
    proposals = _load_proposals()
    proposals.append(proposal)
    _save_proposals(proposals[-20:])
    return {"status": "proposed", "proposal_id": proposal["id"],
            "count": len(changes),
            "note": "Waiting in the Calendar tab. Nothing was changed; the user "
                    "applies it themselves."}


@app.delete("/api/calendar/proposals/{proposal_id}")
async def discard_proposal(proposal_id: str):
    proposals = _load_proposals()
    kept = [p for p in proposals if p.get("id") != proposal_id]
    if len(kept) == len(proposals):
        raise HTTPException(404, "No such proposal")
    _save_proposals(kept)
    return {"status": "discarded"}


@app.post("/api/calendar/proposals/{proposal_id}/apply", dependencies=[Depends(require_page_token)])
async def apply_proposal(proposal_id: str, payload: ApplyPayload):
    """The human pressed Apply. This is the only path from a proposal to Google."""
    proposals = _load_proposals()
    proposal = next((p for p in proposals if p.get("id") == proposal_id), None)
    if proposal is None:
        raise HTTPException(404, "No such proposal")
    changes = proposal.get("changes", [])
    picked = (changes if payload.indexes is None
              else [changes[i] for i in payload.indexes if 0 <= i < len(changes)])
    if not picked:
        raise HTTPException(400, "Nothing selected")

    applied, failed = [], []
    for c in picked:
        try:
            if c["action"] == "delete":
                out = json.loads(await _call_connector("delete_calendar_event", {
                    "event_id": c["event_id"], "account": c.get("account", "")}))
            else:
                # Omitted fields go over as null, not "", so the connector leaves
                # them alone. Sending "" here used to blank the event's start and
                # end, which Google rejects --- a proposal that changed only the
                # title failed outright.
                out = json.loads(await _call_connector("update_calendar_event", {
                    "event_id": c["event_id"], "account": c.get("account", ""),
                    "title": c.get("new_title"),
                    "start_datetime": c.get("new_start"),
                    "end_datetime": c.get("new_end"),
                    "description": c.get("new_description")}))
            if isinstance(out, dict) and "error" in out:
                failed.append({"event_id": c["event_id"], "error": out["error"]})
            else:
                applied.append({"event_id": c["event_id"], "action": c["action"]})
        except Exception as ex:
            failed.append({"event_id": c["event_id"], "error": str(ex)})

    # Keep only what was neither applied nor picked, so a partial apply leaves the
    # rest of the proposal standing rather than silently dropping it.
    done = {a["event_id"] for a in applied}
    remaining = [c for c in changes if c["event_id"] not in done]
    proposals = [p for p in proposals if p.get("id") != proposal_id]
    if remaining and failed:
        proposal["changes"] = remaining
        proposals.append(proposal)
    _save_proposals(proposals)
    return {"applied": applied, "failed": failed}


@app.get("/api/calendar/event/{event_id}")
async def get_event_details(event_id: str, account: str):
    try:
        data = json.loads(await _call_connector("get_calendar_event", {
            "event_id": event_id, "account": account}))
        if "error" in data:
            raise HTTPException(500, data["error"])
        return data
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(500, str(ex))


# --- Chat tab: a relay to Claude Code ------------------------------------------
#
# The app still holds no model.  Each message typed in the Chat tab starts a
# headless Claude Code run (`claude -p`), resumed on the same session so the
# conversation carries on, and the reply streams back to the page.  The run uses
# the user's own Claude Code login and the same smithers skill and PreToolUse
# hook as any other session, so the trust boundary is unchanged: Claude can read,
# park drafts, add events, and propose changes; the user still sends and applies.
#
# POST /api/chat needs the page's token.  Without it, any web page open in the
# browser could POST to 127.0.0.1 and start a Claude Code run on this machine.
# It is also on the hook's list, so an agent cannot start a second agent.
CHAT_FILE = DATA_DIR / "chat.json"
CHAT_MAX_MESSAGES = 200
CHAT_TOOLS = os.environ.get(
    "SMITHERS_CHAT_TOOLS", "Skill,Bash(curl:*),Bash(date:*)").split(",")
# Other mail tools the user's Claude Code login may carry (a claude.ai Gmail
# connector, say) see one account, not the configured set; keep the chat off them.
CHAT_DISALLOWED = os.environ.get(
    "SMITHERS_CHAT_DISALLOWED", "mcp__claude_ai_Gmail").split(",")
_chat_lock = asyncio.Lock()


def _claude_bin() -> str:
    import shutil
    found = os.environ.get("SMITHERS_CLAUDE") or shutil.which("claude")
    if found:
        return found
    fallback = Path.home() / ".local" / "bin" / "claude"
    return str(fallback) if fallback.exists() else "claude"


def _load_chat() -> dict:
    try:
        data = json.loads(CHAT_FILE.read_text())
        if isinstance(data, dict):
            data.setdefault("messages", [])
            return data
    except Exception:
        pass
    return {"session_id": None, "messages": []}


def _save_chat(chat: dict) -> None:
    chat["messages"] = chat.get("messages", [])[-CHAT_MAX_MESSAGES:]
    CHAT_FILE.write_text(json.dumps(chat, indent=2))


def _chat_system_prompt(base: str) -> str:
    return (
        "You are answering in the Chat tab of the Smithers app, which the user "
        f"has open in the browser. The app is already running at {base}; do not "
        "run the launcher. Use the smithers skill and its API for mail, calendar, "
        "tasks, drafts, and the briefing. The API covers every configured mail "
        "account; use no other mail tool. For links in an email, use "
        "/api/email/body. Today's date comes from `date`. Reply "
        "briefly, in plain Markdown, for a reader who sees only your final text, "
        "not your tool calls. When you park a draft or post a proposal, say it is "
        "waiting in the Compose or Calendar tab.")


def _tool_label(block: dict) -> str:
    name = block.get("name", "tool")
    inp = block.get("input") or {}
    if name == "Bash":
        cmd = " ".join(str(inp.get("command", "")).split())
        m = re.search(r"(?:-X\s*(\w+)\s.*?)?(/api/[\w/\-{}?=&%.@+]*)", cmd)
        if m:
            method = (m.group(1) or ("POST" if " -d " in cmd or "--data" in cmd else "GET")).upper()
            return f"{method} {m.group(2)[:80]}"
        return cmd[:100]
    if name == "Skill":
        return f"skill: {inp.get('skill', '')}"
    return name


class ChatPayload(BaseModel):
    message: str


@app.get("/api/chat")
async def chat_history():
    chat = _load_chat()
    return {"messages": chat["messages"], "busy": _chat_lock.locked()}


@app.delete("/api/chat", dependencies=[Depends(require_page_token)])
async def chat_reset():
    if _chat_lock.locked():
        raise HTTPException(409, "Claude is still answering.")
    _save_chat({"session_id": None, "messages": []})
    return {"status": "cleared"}


@app.post("/api/chat", dependencies=[Depends(require_page_token)])
async def chat_send(payload: ChatPayload, request: Request):
    from fastapi.responses import StreamingResponse

    text = payload.message.strip()
    if not text:
        raise HTTPException(400, "Empty message")
    if _chat_lock.locked():
        raise HTTPException(409, "Claude is still answering the last message.")

    base = str(request.base_url).rstrip("/")

    async def stream():
        def ev(kind, value=None):
            return json.dumps({"t": kind, "v": value}) + "\n"

        async with _chat_lock:
            chat = _load_chat()
            chat["messages"].append({"role": "user", "text": text})
            _save_chat(chat)

            # The message goes in on stdin, so text that starts with "-" is
            # never read as a command-line flag.
            args = [_claude_bin(), "-p",
                    "--output-format", "stream-json", "--verbose",
                    "--include-partial-messages",
                    "--append-system-prompt", _chat_system_prompt(base),
                    "--allowedTools", *CHAT_TOOLS,
                    "--disallowedTools", *CHAT_DISALLOWED]
            if chat.get("session_id"):
                args += ["--resume", chat["session_id"]]

            # Run on the user's Claude Code login, not an API key the app's .env
            # may hold, and not as a child of whatever session launched the app.
            env = {k: v for k, v in os.environ.items()
                   if k not in ("ANTHROPIC_API_KEY", "CLAUDECODE")
                   and not k.startswith("CLAUDE_CODE_")}

            reply, tools, error = "", [], None
            try:
                proc = await asyncio.create_subprocess_exec(
                    *args, cwd=str(DATA_DIR), env=env,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    limit=16 * 1024 * 1024)
                proc.stdin.write(text.encode())
                await proc.stdin.drain()
                proc.stdin.close()
            except FileNotFoundError:
                error = ("Claude Code (the `claude` command) was not found. "
                         "Set SMITHERS_CLAUDE to its path and restart Smithers.")
                proc = None

            try:
                if proc is not None:
                    while True:
                        line = await proc.stdout.readline()
                        if not line:
                            break
                        try:
                            msg = json.loads(line)
                        except ValueError:
                            continue
                        kind = msg.get("type")
                        if kind == "system" and msg.get("session_id"):
                            chat["session_id"] = msg["session_id"]
                        elif kind == "stream_event":
                            e = msg.get("event") or {}
                            if e.get("type") == "message_start" and reply and not reply.endswith("\n\n"):
                                reply += "\n\n"
                                yield ev("text", "\n\n")
                            elif e.get("type") == "content_block_delta":
                                d = e.get("delta") or {}
                                if d.get("type") == "text_delta" and d.get("text"):
                                    reply += d["text"]
                                    yield ev("text", d["text"])
                        elif kind == "assistant":
                            for block in (msg.get("message") or {}).get("content", []):
                                if block.get("type") == "tool_use":
                                    label = _tool_label(block)
                                    tools.append(label)
                                    yield ev("tool", label)
                        elif kind == "result":
                            if msg.get("session_id"):
                                chat["session_id"] = msg["session_id"]
                            if msg.get("is_error"):
                                error = str(msg.get("result") or msg.get("subtype") or "Claude Code reported an error.")
                            elif not reply.strip() and msg.get("result"):
                                reply = str(msg["result"])
                                yield ev("text", reply)
                    await proc.wait()
                    if proc.returncode and not error and not reply.strip():
                        err = (await proc.stderr.read()).decode(errors="replace").strip()
                        error = err[-800:] or f"Claude Code exited with code {proc.returncode}."
            finally:
                # The page closed or the request was cancelled: stop the run.
                if proc is not None and proc.returncode is None:
                    proc.kill()
                    await proc.wait()
                entry = {"role": "assistant", "text": reply.strip(), "tools": tools}
                if error:
                    entry["error"] = error
                chat["messages"].append(entry)
                _save_chat(chat)

            if error:
                yield ev("error", error)
            yield ev("done")

    return StreamingResponse(stream(), media_type="application/x-ndjson")


SHELL_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Smithers</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: system-ui, -apple-system, sans-serif;
  font-size: 15px; line-height: 1.6;
  background: #f0f3f8; color: #1e293b;
  padding-top: 176px;
}
#nav {
  position: fixed; top: 0; left: 0; right: 0; z-index: 200;
  display: flex; flex-direction: column;
  background: linear-gradient(135deg,#111c36 0%,#1e2f55 50%,#111c36 100%);
  box-shadow: 0 2px 14px rgba(0,0,0,.45);
}
.nav-banner { display: flex; align-items: center; justify-content: center; padding: 1.25rem 0 .75rem; }
.nav-banner img { height: 100px; object-fit: contain; display: block; }
.nav-tabs-row { background: transparent; display: flex; align-items: center; flex-wrap: wrap; border-top: 1px solid rgba(200,169,110,.2); }
.nav-tab {
  padding: .55rem 1.1rem; background: transparent; color: rgba(255,255,255,.65);
  border: none; border-bottom: 3px solid transparent;
  cursor: pointer; font-size: .82rem; font-weight: 600;
  white-space: nowrap; transition: all .15s; letter-spacing: .02em;
}
.nav-tab:hover { color: #fff; background: rgba(255,255,255,.07); }
.nav-tab.active { color: #fff; border-bottom-color: #c8a96e; }
.tab-badge {
  display: inline-block; min-width: 17px; padding: 0 5px; margin-left: .35rem;
  border-radius: 9px; background: #c8a96e; color: #111c36;
  font-size: .68rem; font-weight: 800; line-height: 17px; text-align: center; vertical-align: middle;
}
.nav-right { margin-left: auto; display: flex; align-items: center; gap: .15rem; padding: 0 .75rem; }
.nav-action {
  padding: .35rem .75rem; background: rgba(255,255,255,.08); color: rgba(255,255,255,.85);
  border: 1px solid rgba(255,255,255,.18); border-radius: 4px; cursor: pointer;
  font-size: .76rem; font-weight: 600; margin: 0 .12rem; white-space: nowrap; transition: background .12s;
}
.nav-action:hover { background: rgba(255,255,255,.18); }
.nav-action.accent { background: #2563eb; border-color: #1d4ed8; color: #fff; }
.nav-action.accent:hover { background: #1d4ed8; }
.nav-action:disabled { opacity: .35; cursor: not-allowed; pointer-events: none; }
#server-dot { width: 7px; height: 7px; border-radius: 50%; background: #ef4444; display: inline-block; margin-right: .3rem; flex-shrink: 0; }
#server-dot.online { background: #4ade80; }
#server-label { font-size: .68rem; color: rgba(255,255,255,.4); white-space: nowrap; }
.section { display: none; max-width: 880px; margin: 1.5rem auto; padding: 0 1.25rem; }
.section.active { display: block; }
.section > h2 { font-size: 1.1rem; font-weight: 700; color: #1a2744; padding: .25rem 0 .4rem .7rem; margin-bottom: 1rem; border-left: 3px solid #c8a96e; border-bottom: 1px solid #e8ecf2; }
.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.06); padding: 1rem; margin-bottom: .75rem; }
.card h3 { font-size: .95rem; font-weight: 700; color: #1a2744; margin-bottom: .5rem; }
.date-display { font-size: 1rem; color: #64748b; }
.ov-hdr { display: flex; align-items: flex-start; gap: 1rem; margin-bottom: 1.25rem; }
.ov-meta { min-width: 0; }
.ov-stamp { font-size: .78rem; color: #94a3b8; margin-top: .15rem; }
.ov-stamp.stale { color: #b45309; font-weight: 600; }
.ov-stamp.refreshing { color: #2563eb; font-weight: 600; }
.ov-hint {
  margin-left: auto; flex-shrink: 0; align-self: center; padding: .3rem .7rem;
  background: #eef2ff; border: 1px solid #c7d2fe; border-radius: 6px;
  font-size: .78rem; font-weight: 600; color: #4338ca;
}
.overview-grid { display: grid; grid-template-columns: repeat(2,1fr); gap: .75rem; margin-bottom: .75rem; }
.overview-stat { text-align: center; padding: .5rem; }
.stat-num { font-size: 1.8rem; font-weight: 700; color: #1a2744; }
.stat-label { font-size: .8rem; color: #64748b; text-transform: uppercase; letter-spacing: .04em; }
.overview-note { font-size: .88rem; color: #475569; margin-top: .5rem; }
.talking-points { padding-left: 1.2rem; margin-top: .4rem; }
.talking-points li { font-size: .88rem; color: #334155; margin-bottom: .25rem; }
.loading { color: #94a3b8; padding: .75rem; font-style: italic; }
.load-error { color: #ef4444; padding: .75rem; font-size: .88rem; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.55); z-index: 300; display: flex; align-items: center; justify-content: center; padding: 1rem; }
.modal { background: #fff; border-radius: 10px; width: 100%; max-width: 500px; box-shadow: 0 20px 60px rgba(0,0,0,.35); }
.modal-hdr { display: flex; justify-content: space-between; align-items: center; padding: .9rem 1.3rem; border-bottom: 1px solid #e2e8f0; }
.modal-hdr h3 { margin: 0; color: #1a2744; font-size: 1rem; }
.modal-x { background: none; border: none; font-size: 1.4rem; cursor: pointer; color: #94a3b8; line-height: 1; }
.modal-x:hover { color: #1a2744; }
.modal-body { padding: 1.1rem 1.3rem; }
.modal-ftr { display: flex; justify-content: flex-end; gap: .5rem; padding: .9rem 1.3rem; border-top: 1px solid #e2e8f0; }
.frow { margin-bottom: .8rem; }
.frow label { display: block; font-size: .75rem; font-weight: 700; color: #475569; margin-bottom: .25rem; text-transform: uppercase; letter-spacing: .05em; }
.frow input, .frow select, .frow textarea { width: 100%; padding: .45rem .7rem; border: 1px solid #cbd5e1; border-radius: 6px; font-size: .88rem; font-family: inherit; box-sizing: border-box; }
.frow textarea { resize: vertical; }
.frow.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: .6rem; }
.btn-ok { padding: .45rem 1.1rem; background: #1a2744; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: .88rem; font-weight: 600; }
.btn-ok:hover { background: #233260; }
.btn-cancel { padding: .45rem 1.1rem; background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; border-radius: 6px; cursor: pointer; font-size: .88rem; }
.cmp-ftr { display: flex; justify-content: flex-end; gap: .5rem; margin-top: .25rem; }
#cmp-body { min-height: 240px; }
.draft-row { display: flex; align-items: flex-start; gap: .75rem; padding: .6rem .1rem; border-top: 1px solid #f1f5f9; }
.draft-row:first-of-type { border-top: none; padding-top: .2rem; }
.draft-row.current { background: #fffbeb; border-radius: 6px; padding-left: .5rem; padding-right: .5rem; }
.draft-meta { flex: 1; min-width: 0; font-size: .88rem; }
.draft-acct { display: inline-block; padding: .1rem .5rem; border-radius: 10px; font-size: .7rem; font-weight: 700; background: #dbeafe; color: #1d4ed8; margin-right: .4rem; vertical-align: 1px; }
.draft-acct.acct-0 { background: #dbeafe; color: #1d4ed8; }
.draft-acct.acct-1 { background: #fef3c7; color: #92400e; }
.draft-acct.acct-2 { background: #dcfce7; color: #166534; }
.draft-acct.acct-3 { background: #ede9fe; color: #6d28d9; }
#setup-banner { display: none; margin: 0 auto 1rem; max-width: 880px; padding: .75rem 1rem;
  background: #fffbeb; border: 1px solid #fcd34d; border-radius: 8px; font-size: .88rem; color: #78350f; }
.draft-to, .draft-snip { color: #64748b; font-size: .8rem; margin-top: .12rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.draft-snip { color: #94a3b8; }
.draft-btns { display: flex; flex-direction: column; gap: .3rem; flex-shrink: 0; }
.draft-btns .action-btn { margin: 0; }
.action-btn { margin: .4rem .3rem 0 0; padding: .22rem .65rem; font-size: .78rem; border: 1px solid #cbd5e1; border-radius: 4px; background: #f8fafc; cursor: pointer; color: #475569; }
.action-btn:hover { background: #e2e8f0; }
.action-btn.danger { color: #dc2626; border-color: #fca5a5; }
.action-btn.danger:hover { background: #fee2e2; }
.action-btn:disabled { opacity: .4; cursor: not-allowed; pointer-events: none; }
.prop-card { background: #fffbeb; border: 1px solid #fcd34d; border-radius: 8px; padding: .75rem .9rem; margin-bottom: .6rem; }
.prop-hdr { font-size: .85rem; font-weight: 700; color: #78350f; margin-bottom: .5rem; }
.prop-row { display: flex; align-items: baseline; gap: .5rem; padding: .25rem 0; font-size: .86rem; cursor: pointer; }
.prop-row input { accent-color: #b45309; cursor: pointer; }
.prop-act { flex-shrink: 0; font-size: .7rem; font-weight: 800; text-transform: uppercase; letter-spacing: .04em; padding: .1rem .45rem; border-radius: 10px; }
.prop-act.delete { background: #fee2e2; color: #991b1b; }
.prop-act.update { background: #dbeafe; color: #1d4ed8; }
.prop-title { color: #1a2744; }
.prop-reason { color: #92400e; font-size: .8rem; }
.prop-btns { display: flex; justify-content: flex-end; gap: .4rem; margin-top: .5rem; }
.prop-btns .action-btn { margin: 0; }
.action-btn.primary { background: #1a2744; color: #fff; border-color: #1a2744; font-weight: 600; }
.action-btn.primary:hover { background: #233260; }
.selbar { display: flex; align-items: center; gap: .6rem; flex-wrap: wrap; margin-bottom: .6rem; padding: .5rem .75rem; background: #fff; border: 1px solid #e2e8f0; border-radius: 6px; }
.selbar-count { font-size: .82rem; font-weight: 600; color: #64748b; }
.selbar-btns { margin-left: auto; display: flex; gap: .35rem; flex-wrap: wrap; }
.selbar-btns .action-btn { margin: 0; }
.sec-actions { display: flex; gap: .35rem; flex-wrap: wrap; margin: -.5rem 0 .8rem; }
.sec-actions .action-btn { margin: 0; }
.evt-check { width: 15px; height: 15px; accent-color: #1a2744; cursor: pointer; flex-shrink: 0; }
#toast { position: fixed; bottom: 1.5rem; right: 1.5rem; padding: .65rem 1.1rem; background: #1a2744; color: #fff; border-radius: 8px; font-size: .85rem; z-index: 400; display: none; box-shadow: 0 4px 20px rgba(0,0,0,.3); max-width: 300px; }
.tm-tabs { display: flex; gap: .5rem; flex-wrap: wrap; margin-bottom: 1rem; }
.tm-tab { padding: .35rem .9rem; border: 2px solid #1a2744; border-radius: 20px; background: #fff; color: #1a2744; cursor: pointer; font-size: .85rem; font-weight: 600; }
.tm-tab.active { background: #1a2744; color: #fff; }
.tm-add-row { display: flex; gap: .5rem; margin-bottom: 1.2rem; flex-wrap: wrap; }
.tm-add-row input { flex: 1; min-width: 180px; padding: .45rem .75rem; border: 1px solid #cbd5e1; border-radius: 6px; font-size: .9rem; }
.tm-add-row button { padding: .45rem 1rem; background: #1a2744; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: .9rem; font-weight: 600; }
.tm-cat-label { font-size: .75rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; padding: .2rem .7rem; border-radius: 12px; display: inline-block; margin-bottom: .5rem; }
.cat-teaching { background: #dbeafe; color: #1d4ed8; }
.cat-research { background: #ede9fe; color: #6d28d9; }
.cat-admin    { background: #fef3c7; color: #92400e; }
.cat-personal { background: #dcfce7; color: #166534; }
.tm-task { display: flex; align-items: center; gap: .6rem; padding: .5rem .75rem; background: #fff; border: 1px solid #e2e8f0; border-radius: 6px; margin-bottom: .4rem; }
.tm-task.done .tm-title { text-decoration: line-through; color: #94a3b8; }
.tm-task input[type=checkbox] { width: 16px; height: 16px; cursor: pointer; accent-color: #1a2744; }
.tm-title { flex: 1; font-size: .9rem; outline: none; border: none; background: transparent; font-family: inherit; cursor: text; }
.tm-title:focus { border-bottom: 1px solid #1a2744; }
.tm-edit-cat { padding: .2rem .5rem; border: 1px solid #e2e8f0; border-radius: 4px; font-size: .8rem; background: #f8fafc; display: none; }
.tm-task:hover .tm-edit-cat { display: inline-block; }
.tm-del { background: none; border: none; cursor: pointer; color: #cbd5e1; font-size: 1rem; padding: 0 .2rem; }
.tm-del:hover { color: #ef4444; }
.tm-completed-toggle { background: none; border: none; cursor: pointer; color: #94a3b8; font-size: .8rem; margin-top: .5rem; padding: 0; }
#chat-log { display: flex; flex-direction: column; gap: .6rem; margin-bottom: 1rem; }
.chat-empty { font-size: .88rem; color: #64748b; }
.chat-msg { max-width: 88%; padding: .6rem .85rem; border-radius: 10px; font-size: .9rem; line-height: 1.55; word-wrap: break-word; }
.chat-msg.user { align-self: flex-end; background: #1a2744; color: #fff; white-space: pre-wrap; }
.chat-msg.assistant { align-self: flex-start; background: #fff; border: 1px solid #e2e8f0; box-shadow: 0 1px 4px rgba(0,0,0,.05); }
.chat-msg.assistant p { margin: 0 0 .5rem; }
.chat-msg.assistant p:last-child { margin-bottom: 0; }
.chat-msg.assistant ul, .chat-msg.assistant ol { margin: 0 0 .5rem 1.25rem; }
.chat-msg.assistant code { background: #f1f5f9; border-radius: 3px; padding: 0 .25rem; font-size: .84em; }
.chat-msg.assistant pre { background: #f1f5f9; border-radius: 6px; padding: .5rem .7rem; overflow-x: auto; margin: 0 0 .5rem; }
.chat-msg.assistant pre code { background: none; padding: 0; }
.chat-msg.assistant h1, .chat-msg.assistant h2, .chat-msg.assistant h3, .chat-msg.assistant h4 { font-size: .95rem; margin: .4rem 0 .3rem; color: #1a2744; }
.chat-tools { font-size: .74rem; color: #94a3b8; margin-bottom: .35rem; font-family: ui-monospace, Menlo, monospace; }
.chat-tools div::before { content: "\2192  "; }
.chat-err { color: #b91c1c; font-size: .84rem; margin-top: .3rem; }
.chat-wait { color: #94a3b8; font-style: italic; }
.chat-input { display: flex; gap: .5rem; align-items: flex-end; position: sticky; bottom: 0; background: #f0f3f8; padding: .5rem 0 1rem; }
.chat-input textarea { flex: 1; padding: .55rem .75rem; border: 1px solid #cbd5e1; border-radius: 8px; font: inherit; font-size: .9rem; resize: vertical; }
.chat-input .btn-ok:disabled { opacity: .45; cursor: not-allowed; }
</style>
</head>
<body>

<nav id="nav">
  <div class="nav-banner">
    <img src="__SMITHERS_SRC__" alt="Smithers">
  </div>
  <div class="nav-tabs-row">
    <button class="nav-tab active" data-sec="section-overview" onclick="showSection('section-overview')">Overview</button>
    <button class="nav-tab" data-sec="section-calendar" onclick="showSection('section-calendar')">Calendar</button>
    <button class="nav-tab" data-sec="section-emails"  onclick="showSection('section-emails')">Emails</button>
    <button class="nav-tab" data-sec="section-compose" onclick="showSection('section-compose')">Compose<span id="draft-badge" class="tab-badge" style="display:none">0</span></button>
    <button class="nav-tab" data-sec="section-tasks"   onclick="showSection('section-tasks')">Tasks</button>
    <button class="nav-tab" data-sec="section-chat"    onclick="showSection('section-chat')">Chat</button>
    <div class="nav-right">
      <button class="nav-action" id="btn-refresh" onclick="refreshSection()" style="visibility:hidden" title="Refresh">&#8635;</button>
      <!-- No New Email or Add Event buttons here. Both lived next to the tabs
           that already own them: Compose (where Clear starts a blank message)
           and Calendar (which now carries its own Add Event). A nav button
           beside the tab it duplicates reads as two ways to do one thing. -->
      <span id="server-dot"></span><span id="server-label">offline</span>
    </div>
  </div>
</nav>

<div id="setup-banner"></div>

<main>
  <section id="section-overview" class="section active">
    <div class="ov-hdr">
      <div class="ov-meta">
        <div class="date-display" id="overview-date"></div>
        <div class="ov-stamp" id="overview-stamp"></div>
      </div>
      <div class="ov-hint">Ask Claude Code when you want your Overview updated</div>
    </div>
    <div id="overview-content"><p class="loading">Loading overview&hellip;</p></div>
  </section>
  <section id="section-calendar" class="section">
    <h2>Calendar</h2>
    <div class="sec-actions">
      <button class="action-btn" onclick="openEventModal()" title="Add calendar event">&#128197; Add Event</button>
    </div>
    <div id="cal-proposals"></div>
    <div id="cal-selbar" class="selbar" style="display:none">
      <span class="selbar-count" id="cal-selcount">0 selected</span>
      <div class="selbar-btns">
        <button class="action-btn" onclick="calSelectAll()">Select all</button>
        <button class="action-btn" id="cal-clear-selected" onclick="calClearSelection()" disabled>Clear</button>
        <button class="action-btn danger" id="cal-del-selected" onclick="deleteSelectedEvents()" disabled>&#128465; Delete selected</button>
      </div>
    </div>
    <div id="calendar-content"><p class="loading">Loading&hellip;</p></div>
  </section>
  <section id="section-emails" class="section">
    <h2>Emails</h2>
    <div id="emails-content"><p class="loading">Loading&hellip;</p></div>
  </section>
  <section id="section-compose" class="section">
    <h2>Compose</h2>
    <div id="drafts-panel"></div>
    <div class="card">
      <div class="frow"><label>From</label>
        <select id="cmp-account">
        </select></div>
      <div class="frow"><label>To</label><input type="email" id="cmp-to" placeholder="recipient@example.com"></div>
      <div class="frow"><label>CC</label><input type="text" id="cmp-cc" placeholder="cc@example.com, another@example.com"></div>
      <div class="frow"><label>Subject</label><input type="text" id="cmp-subject"></div>
      <div class="frow"><label>Message</label><textarea id="cmp-body" rows="12"></textarea></div>
      <input type="hidden" id="cmp-thread-id">
      <input type="hidden" id="cmp-draft-id">
      <div class="cmp-ftr">
        <button class="btn-cancel" onclick="openCompose()" title="Empty the form and start a new message">Clear</button>
        <button class="btn-ok" onclick="sendEmail()">Send</button>
      </div>
    </div>
  </section>
  <section id="section-tasks" class="section">
    <h2>Tasks</h2>
    <div class="tm-tabs">
      <button class="tm-tab active" onclick="tmFilter('all')">All</button>
      <button class="tm-tab" onclick="tmFilter('teaching')">Teaching</button>
      <button class="tm-tab" onclick="tmFilter('research')">Research</button>
      <button class="tm-tab" onclick="tmFilter('admin')">Admin</button>
      <button class="tm-tab" onclick="tmFilter('personal')">Personal</button>
    </div>
    <div class="tm-add-row">
      <input id="tm-input" type="text" placeholder="New task&hellip;" onkeydown="if(event.key==='Enter')tmAdd()">
      <button onclick="tmAdd()">+ Add</button>
    </div>
    <div id="tm-list"></div>
  </section>
  <section id="section-chat" class="section">
    <h2>Chat</h2>
    <div class="sec-actions">
      <button class="action-btn" id="chat-new" onclick="chatReset()" title="Start a new conversation with Claude">New chat</button>
    </div>
    <div id="chat-log"><p class="chat-empty">Ask Claude about your mail, calendar, or tasks. Replies come from Claude Code on this computer. Drafts it writes wait in Compose; you still press Send.</p></div>
    <div class="chat-input">
      <textarea id="chat-text" rows="3" placeholder="Message Claude&hellip; (Enter to send, Shift+Enter for a new line)"
        onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();chatSend();}"></textarea>
      <button class="btn-ok" id="chat-send" onclick="chatSend()">Send</button>
    </div>
  </section>
</main>

<div id="modal-view-email" class="modal-overlay" style="display:none" onclick="if(event.target===this)closeModal('modal-view-email')">
  <div class="modal" style="max-width:680px">
    <div class="modal-hdr"><h3 id="view-email-subject" style="font-size:.95rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:560px"></h3><button class="modal-x" onclick="closeModal('modal-view-email')">&#215;</button></div>
    <div class="modal-body" style="max-height:70vh;overflow-y:auto">
      <div id="view-email-body" style="font-size:.9rem;line-height:1.6;white-space:pre-wrap;word-break:break-word"></div>
      <div id="view-email-attachments"></div>
    </div>
    <div class="modal-ftr">
      <button class="btn-cancel" onclick="closeModal('modal-view-email')">Close</button>
    </div>
  </div>
</div>

<div id="modal-event" class="modal-overlay" style="display:none" onclick="if(event.target===this)closeModal('modal-event')">
  <div class="modal">
    <div class="modal-hdr"><h3 id="evt-modal-title">Add Event</h3><button class="modal-x" onclick="closeModal('modal-event')">&#215;</button></div>
    <div class="modal-body">
      <input type="hidden" id="evt-id">
      <div class="frow"><label>Calendar</label>
        <select id="evt-account">
        </select></div>
      <div class="frow"><label>Title</label><input type="text" id="evt-title"></div>
      <div class="frow two-col">
        <div><label>Start</label><input type="datetime-local" id="evt-start"></div>
        <div><label>End</label><input type="datetime-local" id="evt-end"></div>
      </div>
      <div class="frow"><label>Description</label><textarea id="evt-desc" rows="3"></textarea></div>
    </div>
    <div class="modal-ftr">
      <button class="btn-cancel" onclick="closeModal('modal-event')">Cancel</button>
      <button class="btn-ok" onclick="saveEvent()">Save</button>
    </div>
  </div>
</div>

<div id="toast"></div>

<script>
const SRV = '.';   // relative base, so requests work behind an nginx sub-path
const MY_EMAILS = __MY_EMAILS__;
// Per-launch token for the user-only routes (send, edit, delete, apply). The app
// rejects those routes without it. Defense in depth only: see app.py.
const ACTION_TOKEN = '__ACTION_TOKEN__';
const ACTION_HEADERS = {'X-Smithers-Action': ACTION_TOKEN};
const ACCOUNTS = __ACCOUNTS__;   // [{label, email}], first is the default
const DEFAULT_ACCOUNT = ACCOUNTS.length ? ACCOUNTS[0].label : '';
const REFRESHABLE = new Set(['section-overview', 'section-calendar', 'section-emails']);
const loaded = {};

function showSection(id) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(b => b.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  const tab = document.querySelector('.nav-tab[data-sec="' + id + '"]');
  if (tab) tab.classList.add('active');
  document.getElementById('btn-refresh').style.visibility = REFRESHABLE.has(id) ? 'visible' : 'hidden';
  if (id === 'section-compose') refreshDrafts();
  if (id === 'section-calendar') refreshProposals();
  loadSection(id);
}

const SECTION_MAP = {
  'section-overview': ['overview', 'overview-content'],
  'section-calendar': ['calendar', 'calendar-content'],
  'section-emails':   ['emails',   'emails-content'],
};

async function loadSection(id) {
  if (loaded[id]) return;
  const entry = SECTION_MAP[id];
  if (!entry) return;
  const [name, contentId] = entry;
  try {
    const r = await fetch(SRV + '/api/section/' + name);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const data = await r.json();
    document.getElementById(contentId).innerHTML = data.html;
    if (id === 'section-overview') renderOverviewMeta(data);
    loaded[id] = true;
    injectActionButtons();
  } catch(e) {
    document.getElementById(contentId).innerHTML = '<p class="load-error">Failed to load: ' + e.message + '</p>';
  }
}

// Today's date always comes from the server; the stamp underneath says when the
// briefing below it was built, and turns amber once that is not today.
function renderOverviewMeta(data) {
  if (data.date) document.getElementById('overview-date').textContent = data.date;
  const el = document.getElementById('overview-stamp');
  // Opening Smithers asks Claude Code for a fresh Overview, so say so while the
  // old one is still on screen rather than letting it look current.
  const pending = data.refreshing ? ' — Claude Code is refreshing it now' : '';
  if (!data.generated_at) {
    el.className = 'ov-stamp' + (data.refreshing ? ' refreshing' : '');
    el.textContent = data.refreshing ? 'Claude Code is writing your Overview…'
                                     : 'Never generated';
    return;
  }
  const d = new Date(data.generated_at);
  if (isNaN(d)) { el.className = 'ov-stamp'; el.textContent = ''; return; }
  const stale = d.toDateString() !== new Date().toDateString();
  const when = d.toLocaleString('en-US',
    {weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'});
  el.className = 'ov-stamp' + (data.refreshing ? ' refreshing' : (stale ? ' stale' : ''));
  el.textContent = 'Generated ' + when +
    (pending || (stale ? ' — Overview was not generated today' : ''));
}

async function refreshSection() {
  const active = document.querySelector('.section.active');
  if (!active || !REFRESHABLE.has(active.id)) return;
  const [name, contentId] = SECTION_MAP[active.id];
  loaded[active.id] = false;
  document.getElementById(contentId).innerHTML = '<p class="loading">Refreshing&hellip;</p>';
  loadSection(active.id);
}

async function checkServer() {
  let ok = false;
  try { const r = await fetch(SRV + '/api/ping', {signal: AbortSignal.timeout(1500)}); ok = r.ok; } catch {}
  document.getElementById('server-dot').className = ok ? 'online' : '';
  document.getElementById('server-label').textContent = ok ? 'online' : 'offline';
}

// The briefing is written by Claude Code (POST /api/briefing), not by this app,
// so the Overview polls for a newer one instead of generating it here.
let lastStamp = null;
async function pollBriefing() {
  try {
    const r = await fetch(SRV + '/api/section/overview');
    if (!r.ok) return;
    const d = await r.json();
    if (lastStamp !== null && d.generated_at && d.generated_at !== lastStamp) {
      loaded['section-overview'] = false;
      loadSection('section-overview');
      toast('Overview updated');
    } else {
      renderOverviewMeta(d);   // keeps the "refreshing" note in step
    }
    lastStamp = d.generated_at || '';
  } catch {}
}

// ── Accounts ─────────────────────────────────────────────────────────────────
// Every account selector is built from the configured account list, so a fresh
// install with different accounts (or one account, or four) just works.
function accountLabel(label) {
  return (label || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}
function accountBadgeIndex(label) {
  const i = ACCOUNTS.findIndex(a => a.label === label);
  return i < 0 ? 0 : i % 4;
}
function renderAccountOptions() {
  const opts = ACCOUNTS.map(a =>
    '<option value="' + _escHtml(a.label) + '">' + _escHtml(accountLabel(a.label)) +
    (a.email ? ' — ' + _escHtml(a.email) : '') + '</option>').join('');
  ['cmp-account', 'evt-account'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = opts || '<option value="">(no accounts configured)</option>';
  });
  if (!ACCOUNTS.length) showSetupBanner();
}
function showSetupBanner() {
  const el = document.getElementById('setup-banner');
  if (!el) return;
  el.innerHTML =
    '<strong>Smithers isn\'t connected to an account yet.</strong> ' +
    'Ask Claude Code to set up Smithers and it will walk you through connecting ' +
    'your Google account(s) — it takes a couple of minutes and only happens once.';
  el.style.display = 'block';
}

// ── Proposed calendar changes ────────────────────────────────────────────────
// Smithers can propose edits and deletions but cannot perform them. A proposal
// is inert until you press Apply here; that click is what reaches the calendar.
let proposals = [];
let proposalsSeen = false;

async function refreshProposals() {
  try {
    const r = await fetch(SRV + '/api/calendar/proposals');
    if (!r.ok) return;
    const next = (await r.json()).proposals || [];
    const isNew = proposalsSeen && next.length > proposals.length;
    proposals = next; proposalsSeen = true;
    renderProposals();
    if (isNew && document.querySelector('.section.active')?.id !== 'section-calendar') {
      toast('Smithers proposed a calendar change — see the Calendar tab');
    }
  } catch {}
}

function renderProposals() {
  const panel = document.getElementById('cal-proposals');
  if (!panel) return;
  if (!proposals.length) { panel.innerHTML = ''; return; }
  panel.innerHTML = proposals.map((p, pi) => {
    const verb = p.deletes && p.updates ? 'changing' : (p.deletes ? 'deleting' : 'editing');
    const rows = (p.changes || []).map((c, ci) =>
      '<label class="prop-row">' +
        '<input type="checkbox" class="prop-check" data-p="' + pi + '" data-c="' + ci + '" checked>' +
        '<span class="prop-act ' + _escHtml(c.action) + '">' + (c.action === 'delete' ? 'Delete' : 'Edit') + '</span>' +
        '<span class="prop-title">' + _escHtml(c.title || c.event_id) + '</span>' +
        (c.reason ? '<span class="prop-reason">' + _escHtml(c.reason) + '</span>' : '') +
      '</label>').join('');
    return '<div class="prop-card">' +
availableHeader(p, verb) +
      rows +
      '<div class="prop-btns">' +
        '<button class="action-btn" onclick="discardProposal(' + pi + ')">Discard</button>' +
        '<button class="action-btn primary" onclick="applyProposal(' + pi + ')">Apply selected</button>' +
      '</div></div>';
  }).join('');
}

function availableHeader(p, verb) {
  return '<div class="prop-hdr">⚠ Smithers proposes ' + verb + ' ' + p.count +
    ' event' + (p.count === 1 ? '' : 's') +
    (p.note ? ' — ' + _escHtml(p.note) : '') + '</div>';
}

function _pickedChanges(pi) {
  return [...document.querySelectorAll('.prop-check[data-p="' + pi + '"]')]
    .filter(b => b.checked).map(b => Number(b.dataset.c));
}

async function applyProposal(pi) {
  const p = proposals[pi];
  if (!p) return;
  const idx = _pickedChanges(pi);
  if (!idx.length) return toast('Nothing selected');
  const names = idx.slice(0, 8).map(i => '• ' + (p.changes[i].title || p.changes[i].event_id)).join('\n');
  const more = idx.length > 8 ? '\n• …and ' + (idx.length - 8) + ' more' : '';
  if (!confirm('Apply ' + idx.length + ' change' + (idx.length === 1 ? '' : 's') +
               ' to your calendar?\n\n' + names + more)) return;
  try {
    toast('Applying…', 60000);
    const r = await fetch(SRV + '/api/calendar/proposals/' + encodeURIComponent(p.id) + '/apply', {
      method: 'POST', headers: {'Content-Type': 'application/json', ...ACTION_HEADERS},
      body: JSON.stringify({indexes: idx})
    });
    if (!r.ok) throw new Error(await r.text());
    const d = await r.json();
    toast(d.failed.length
      ? 'Applied ' + d.applied.length + ', ' + d.failed.length + ' failed'
      : 'Applied ' + d.applied.length + ' change' + (d.applied.length === 1 ? '' : 's'));
    await refreshProposals();
    reloadCalendar();
  } catch(e) { toast('Error: ' + e.message); }
}

async function discardProposal(pi) {
  const p = proposals[pi];
  if (!p) return;
  if (!confirm('Discard this proposal? Nothing on your calendar changes.')) return;
  try {
    const r = await fetch(SRV + '/api/calendar/proposals/' + encodeURIComponent(p.id), {method: 'DELETE'});
    if (!r.ok) throw new Error(await r.text());
    await refreshProposals();
    toast('Proposal discarded');
  } catch(e) { toast('Error: ' + e.message); }
}

let _tid;
function toast(msg, ms=3500) {
  const el = document.getElementById('toast');
  el.textContent = msg; el.style.display = 'block';
  clearTimeout(_tid); _tid = setTimeout(() => el.style.display = 'none', ms);
}

function closeModal(id) { document.getElementById(id).style.display = 'none'; }

// Fills the Compose tab and brings it forward. Called with no arguments for a
// blank message, with sender details from a Reply button, or with a full draft
// Smithers wrote (openDraft below).
function openCompose(to='', subject='', account='', threadId='', cc='', body='', draftId='') {
  showSection('section-compose');
  document.getElementById('cmp-to').value = to;
  document.getElementById('cmp-cc').value = cc;
  document.getElementById('cmp-subject').value = subject;
  document.getElementById('cmp-body').value = body;
  document.getElementById('cmp-account').value = account;
  document.getElementById('cmp-thread-id').value = threadId;
  document.getElementById('cmp-draft-id').value = draftId;
  renderDrafts();
  const focusId = body ? 'cmp-body' : 'cmp-to';
  // preventScroll so opening a long draft doesn't jump past the drafts list
  setTimeout(() => { document.getElementById(focusId).focus({preventScroll: true});
                     window.scrollTo(0, 0); }, 50);
}

// ── Drafts Smithers parked in the Compose tab ────────────────────────────────
let drafts = [];
let draftsSeen = false;

async function refreshDrafts() {
  try {
    const r = await fetch(SRV + '/api/drafts');
    if (!r.ok) return;
    const next = (await r.json()).drafts || [];
    const isNew = draftsSeen && next.length > drafts.length;
    drafts = next; draftsSeen = true;
    renderDrafts();
    if (isNew && document.querySelector('.section.active')?.id !== 'section-compose') {
      toast('Smithers drafted an email — see the Compose tab');
    }
  } catch {}
}

function renderDrafts() {
  const badge = document.getElementById('draft-badge');
  badge.textContent = drafts.length;
  badge.style.display = drafts.length ? 'inline-block' : 'none';
  const panel = document.getElementById('drafts-panel');
  if (!drafts.length) { panel.innerHTML = ''; return; }
  const open = document.getElementById('cmp-draft-id').value;
  panel.innerHTML =
    '<div class="card"><h3>Drafts from Smithers</h3>' +
    drafts.map((d, i) => draftRowHtml(d, i, d.id === open)).join('') +
    '</div>';
}

function draftRowHtml(d, i, isOpen) {
  const badgeIdx = accountBadgeIndex(d.account);
  const snip = (d.body || '').replace(/\s+/g, ' ').trim().slice(0, 120);
  return '<div class="draft-row' + (isOpen ? ' current' : '') + '">' +
    '<div class="draft-meta">' +
      '<span class="draft-acct acct-' + badgeIdx + '">' + _escHtml(accountLabel(d.account)) + '</span>' +
      '<strong>' + _escHtml(d.subject || '(no subject)') + '</strong>' +
      '<div class="draft-to">To: ' + _escHtml(d.to || '') + '</div>' +
      '<div class="draft-snip">' + _escHtml(snip) + '</div>' +
    '</div>' +
    '<div class="draft-btns">' +
      '<button class="action-btn" onclick="openDraft(' + i + ')">' + (isOpen ? 'Reload' : 'Open') + '</button>' +
      '<button class="action-btn danger" onclick="discardDraft(' + i + ')">Discard</button>' +
    '</div></div>';
}

function openDraft(i) {
  const d = drafts[i];
  if (!d) return;
  openCompose(d.to || '', d.subject || '', d.account || DEFAULT_ACCOUNT,
              d.thread_id || '', d.cc || '', d.body || '', d.id);
}

async function discardDraft(i) {
  const d = drafts[i];
  if (!d) return;
  if (!confirm('Discard the draft "' + (d.subject || '(no subject)') + '"?')) return;
  try {
    const r = await fetch(SRV + '/api/drafts/' + encodeURIComponent(d.id), {method: 'DELETE'});
    if (!r.ok) throw new Error(await r.text());
    if (document.getElementById('cmp-draft-id').value === d.id) {
      document.getElementById('cmp-draft-id').value = '';
    }
    await refreshDrafts();
    toast('Draft discarded');
  } catch(e) { toast('Error: ' + e.message); }
}

async function openEmailView(messageId, account, subject) {
  if (!messageId) { toast('No message ID available'); return; }
  document.getElementById('view-email-subject').textContent = subject;
  document.getElementById('view-email-body').textContent = 'Loading…';
  document.getElementById('view-email-attachments').innerHTML = '';
  document.getElementById('modal-view-email').style.display = 'flex';
  try {
    const [bodyR, attR] = await Promise.all([
      fetch(SRV + '/api/email/body?account=' + encodeURIComponent(account) + '&message_id=' + encodeURIComponent(messageId)),
      fetch(SRV + '/api/email/attachments?account=' + encodeURIComponent(account) + '&message_id=' + encodeURIComponent(messageId)),
    ]);
    const data = await bodyR.json();
    if (data.error) throw new Error(data.error);
    const el = document.getElementById('view-email-body');
    if (data.html) {
      el.style.whiteSpace = 'normal';
      el.innerHTML = data.html;
    } else {
      el.style.whiteSpace = 'pre-wrap';
      el.textContent = data.text || '(no body)';
    }
    if (attR.ok) {
      const atts = (await attR.json()).attachments || [];
      if (atts.length) {
        const attEl = document.getElementById('view-email-attachments');
        attEl.innerHTML =
          '<div style="border-top:1px solid #e2e8f0;margin-top:.75rem;padding-top:.5rem;' +
          'font-size:.75rem;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.3rem">Attachments</div>' +
          atts.map(a => {
            const url = SRV + '/api/email/attachment?account=' + encodeURIComponent(account) +
              '&message_id=' + encodeURIComponent(messageId) +
              '&attachment_id=' + encodeURIComponent(a.attachment_id) +
              '&filename=' + encodeURIComponent(a.filename);
            return '<a href="' + url + '" download="' + a.filename.replace(/"/g,'') + '" ' +
              'style="display:inline-flex;align-items:center;gap:.3rem;margin:.25rem .4rem .25rem 0;' +
              'padding:.3rem .75rem;background:#f1f5f9;border:1px solid #cbd5e1;border-radius:4px;' +
              'font-size:.83rem;color:#1a2744;text-decoration:none">' +
              '&#128206; ' + _escHtml(a.filename) +
              ' <span style="color:#94a3b8;font-size:.75rem">(' + _fmtSize(a.size) + ')</span></a>';
          }).join('');
      }
    }
  } catch(e) {
    document.getElementById('view-email-body').textContent = 'Error: ' + e.message;
  }
}

function _fmtSize(b) {
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b/1024).toFixed(1) + ' KB';
  return (b/1048576).toFixed(1) + ' MB';
}
function _escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function openEventModal(id='', title='', start='', account='') {
  document.getElementById('evt-modal-title').textContent = id ? 'Edit Event' : 'Add Event';
  document.getElementById('evt-id').value = id;
  document.getElementById('evt-title').value = title;
  document.getElementById('evt-start').value = start.slice(0,16);
  document.getElementById('evt-end').value = start.slice(0,16);
  document.getElementById('evt-account').value = account;
  document.getElementById('evt-desc').value = '';
  document.getElementById('modal-event').style.display = 'flex';
  setTimeout(() => document.getElementById('evt-title').focus(), 50);
}

async function sendEmail() {
  const payload = {
    account:   document.getElementById('cmp-account').value,
    to:        document.getElementById('cmp-to').value.trim(),
    cc:        document.getElementById('cmp-cc').value.trim(),
    subject:   document.getElementById('cmp-subject').value.trim(),
    body:      document.getElementById('cmp-body').value.trim(),
    thread_id: document.getElementById('cmp-thread-id').value,
    draft_id:  document.getElementById('cmp-draft-id').value,
  };
  if (!payload.to || !payload.subject || !payload.body) return toast('Fill in all fields');
  try {
    toast('Sending…');
    const r = await fetch(SRV + '/api/email/send', {method:'POST', headers:{'Content-Type':'application/json', ...ACTION_HEADERS}, body:JSON.stringify(payload)});
    if (!r.ok) throw new Error(await r.text());
    openCompose();            // clear the form, ready for the next message
    await refreshDrafts();    // the sent draft is gone from the list
    toast('Email sent!');
  } catch(e) { toast('Error: ' + e.message); }
}

async function saveEvent() {
  const id  = document.getElementById('evt-id').value;
  const fix = v => v && v.length===16 ? v+':00' : v;
  const payload = {
    account:     document.getElementById('evt-account').value,
    title:       document.getElementById('evt-title').value.trim(),
    start:       fix(document.getElementById('evt-start').value),
    end:         fix(document.getElementById('evt-end').value),
    description: document.getElementById('evt-desc').value,
  };
  if (!payload.title||!payload.start||!payload.end) return toast('Fill in title, start, and end');
  try {
    const url = id ? SRV+'/api/calendar/events/'+encodeURIComponent(id) : SRV+'/api/calendar/events';
    const r = await fetch(url, {
      method: id?'PATCH':'POST',
      headers:{'Content-Type':'application/json', ...ACTION_HEADERS}, body:JSON.stringify(payload)
    });
    if (!r.ok) throw new Error(await r.text());
    closeModal('modal-event'); toast(id?'Event updated!':'Event created!');
    reloadCalendar();
  } catch(e) { toast('Error: ' + e.message); }
}

function reloadCalendar() {
  loaded['section-calendar'] = false;
  if (document.querySelector('.section.active')?.id === 'section-calendar') {
    document.getElementById('calendar-content').innerHTML = '<p class="loading">Refreshing…</p>';
    loadSection('section-calendar');
  }
}

async function loadEventDetails(eventId, account, bodyEl) {
  if (!eventId) { bodyEl.textContent = 'No event ID.'; return; }
  try {
    const r = await fetch(SRV + '/api/calendar/event/' + encodeURIComponent(eventId) + '?account=' + encodeURIComponent(account));
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    const rows = [];
    const fmt = iso => {
      try {
        return new Date(iso).toLocaleString('en-US',{weekday:'short',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});
      } catch { return iso; }
    };
    if (d.start) rows.push(['Time', fmt(d.start) + (d.end ? ' – ' + fmt(d.end) : '')]);
    if (d.location) rows.push(['Location', _escHtml(d.location)]);
    if (d.meeting_url) {
      rows.push(['Meeting', '<a href="' + _escHtml(d.meeting_url) + '" target="_blank" style="color:#2563eb;word-break:break-all">' + _escHtml(d.meeting_url) + '</a>']);
    }
    if (d.description) {
      const urlRe = /https?:\/\/[^\s<>"]+/g;
      const links = [...new Set((d.description.match(urlRe)||[]).filter(u => /zoom\.us|teams\.microsoft|meet\.google|webex|whereby/.test(u)))];
      links.forEach(u => { if (u !== d.meeting_url) rows.push(['Link', '<a href="' + _escHtml(u) + '" target="_blank" style="color:#2563eb;word-break:break-all">' + _escHtml(u) + '</a>']); });
    }
    if (d.organizer) rows.push(['Organizer', _escHtml(d.organizer)]);
    if (d.attendees && d.attendees.length) {
      const statusIcon = s => s==='accepted'?'✓':s==='declined'?'✗':s==='tentative'?'?':'';
      const attHtml = d.attendees.map(a =>
        '<span style="display:inline-block;margin:.1rem .4rem .1rem 0">' +
        (a.name ? _escHtml(a.name) + ' &lt;' + _escHtml(a.email) + '&gt;' : _escHtml(a.email)) +
        (a.status ? ' <span style="color:#94a3b8;font-size:.8em">' + statusIcon(a.status) + '</span>' : '') +
        '</span>'
      ).join('');
      rows.push(['Attendees', attHtml]);
    }
    if (d.description) {
      const plain = d.description.replace(/<br\s*\/?>/gi,'\n').replace(/<[^>]+>/g,'').trim();
      if (plain) rows.push(['Notes', '<pre style="white-space:pre-wrap;font-family:inherit;margin:0">' + _escHtml(plain) + '</pre>']);
    }
    if (!rows.length) { bodyEl.textContent = 'No additional details.'; return; }
    bodyEl.innerHTML = rows.map(([k,v]) =>
      '<div style="display:grid;grid-template-columns:80px 1fr;gap:.25rem .75rem;margin-bottom:.3rem">' +
      '<span style="font-weight:600;color:#64748b;font-size:.8rem;padding-top:.1rem">' + k + '</span>' +
      '<span style="line-height:1.5">' + v + '</span></div>'
    ).join('');
  } catch(e) {
    bodyEl.textContent = 'Error loading details: ' + e.message;
  }
}

async function deleteEvent(eventId, account, title) {
  if (!eventId) return toast('No event ID');
  if (!confirm('Delete "' + title + '" from the ' + account + ' calendar?')) return;
  try {
    const r = await fetch(
      SRV + '/api/calendar/events/' + encodeURIComponent(eventId) + '?account=' + encodeURIComponent(account),
      {method: 'DELETE', headers: ACTION_HEADERS}
    );
    if (!r.ok) throw new Error(await r.text());
    toast('Event deleted');
    reloadCalendar();
  } catch(e) { toast('Error: ' + e.message); }
}

// ── Multi-select delete on the Calendar tab ──────────────────────────────────
// Deleting is a human action, same as sending mail. The delete routes need the
// page's ACTION_TOKEN; the agent is told never to call them and the plugin's
// hook blocks them, but neither is a hard guarantee.

function calCheckboxes() {
  return [...document.querySelectorAll('#calendar-content .evt-check')];
}

function updateEventSelection() {
  const boxes = calCheckboxes();
  const n = boxes.filter(b => b.checked).length;
  document.getElementById('cal-selbar').style.display = boxes.length ? 'flex' : 'none';
  document.getElementById('cal-selcount').textContent =
    n ? n + ' of ' + boxes.length + ' selected' : 'Select events to delete';
  document.getElementById('cal-del-selected').disabled = !n;
  document.getElementById('cal-clear-selected').disabled = !n;
}

function calSelectAll() {
  calCheckboxes().forEach(b => { b.checked = true; });
  updateEventSelection();
}

function calClearSelection() {
  calCheckboxes().forEach(b => { b.checked = false; });
  updateEventSelection();
}

async function deleteSelectedEvents() {
  const picked = calCheckboxes()
    .filter(b => b.checked)
    .map(b => b.closest('.event-item'))
    .filter(el => el && el.dataset.eventId)
    .map(el => ({event_id: el.dataset.eventId, account: el.dataset.account || DEFAULT_ACCOUNT,
                 title: el.dataset.title || '(untitled)'}));
  if (!picked.length) return toast('Nothing selected');
  const shown = picked.slice(0, 8).map(e => '• ' + e.title).join('\n');
  const more  = picked.length > 8 ? '\n• …and ' + (picked.length - 8) + ' more' : '';
  const noun  = picked.length === 1 ? 'event' : 'events';
  if (!confirm('Delete ' + picked.length + ' ' + noun + '?\n\n' + shown + more)) return;
  try {
    toast('Deleting ' + picked.length + ' ' + noun + '…', 60000);
    const r = await fetch(SRV + '/api/calendar/events/delete', {
      method: 'POST', headers: {'Content-Type': 'application/json', ...ACTION_HEADERS},
      body: JSON.stringify({events: picked.map(e => ({event_id: e.event_id, account: e.account}))})
    });
    if (!r.ok) throw new Error(await r.text());
    const d = await r.json();
    toast(d.failed.length
      ? 'Deleted ' + d.deleted.length + ', ' + d.failed.length + ' failed'
      : 'Deleted ' + d.deleted.length + ' ' + (d.deleted.length === 1 ? 'event' : 'events'));
    reloadCalendar();
  } catch(e) { toast('Error: ' + e.message); }
}

function injectActionButtons() {
  document.querySelectorAll('.email-item').forEach(el => {
    if (el.querySelector('.reply-btn')) return;
    const viewBtn = document.createElement('button');
    viewBtn.className = 'action-btn view-btn'; viewBtn.textContent = '👁 View';
    viewBtn.onclick = () => openEmailView(el.dataset.messageId||'', el.dataset.account||DEFAULT_ACCOUNT, el.dataset.subject||'');
    el.appendChild(viewBtn);
    const btn = document.createElement('button');
    btn.className = 'action-btn reply-btn'; btn.textContent = '↩ Reply';
    btn.onclick = () => openCompose(el.dataset.from||'', 'Re: '+(el.dataset.subject||''), el.dataset.account||DEFAULT_ACCOUNT, el.dataset.threadId||'');
    el.appendChild(btn);
    const raBtn = document.createElement('button');
    raBtn.className = 'action-btn reply-all-btn'; raBtn.textContent = '↩ Reply All';
    raBtn.onclick = () => {
      const mine = new Set(MY_EMAILS.map(a => a.toLowerCase()));
      const ccAddrs = [];
      for (const h of [el.dataset.to||'', el.dataset.cc||'']) {
        if (!h) continue;
        h.split(/,\s*/).forEach(addr => {
          const m = addr.match(/[^\s<>]+@[^\s<>]+/);
          if (m && !mine.has(m[0].toLowerCase())) ccAddrs.push(addr.trim());
        });
      }
      openCompose(el.dataset.from||'', 'Re: '+(el.dataset.subject||''), el.dataset.account||DEFAULT_ACCOUNT, el.dataset.threadId||'', ccAddrs.join(', '));
    };
    el.appendChild(raBtn);
  });
  document.querySelectorAll('.event-item').forEach(el => {
    if (el.querySelector('.edit-event-btn')) return;
    const summary = el.querySelector('summary') || el;
    const cb = document.createElement('input');
    cb.type = 'checkbox'; cb.className = 'evt-check';
    cb.title = 'Select for deletion';
    // The checkbox lives inside <summary>, so swallow the click that would
    // otherwise expand/collapse the event.
    cb.onclick = e => e.stopPropagation();
    cb.onchange = updateEventSelection;
    summary.insertBefore(cb, summary.firstChild);
    const editBtn = document.createElement('button');
    editBtn.className = 'action-btn edit-event-btn'; editBtn.textContent = '✏ Edit';
    editBtn.onclick = e => {
      e.preventDefault(); e.stopPropagation();
      openEventModal(el.dataset.eventId||'', el.dataset.title||'', el.dataset.start||'', el.dataset.account||DEFAULT_ACCOUNT);
    };
    summary.appendChild(editBtn);
    const delBtn = document.createElement('button');
    delBtn.className = 'action-btn danger delete-event-btn'; delBtn.textContent = '🗑 Delete';
    delBtn.onclick = e => {
      e.preventDefault(); e.stopPropagation();
      deleteEvent(el.dataset.eventId||'', el.dataset.account||DEFAULT_ACCOUNT, el.dataset.title||'');
    };
    summary.appendChild(delBtn);
    el.addEventListener('toggle', function onToggle() {
      if (!el.open) return;
      const body = el.querySelector('.event-detail-body');
      if (!body || body.dataset.loaded) return;
      body.dataset.loaded = '1';
      loadEventDetails(el.dataset.eventId||'', el.dataset.account||DEFAULT_ACCOUNT, body);
    });
  });
  updateEventSelection();
}

const TM_API = SRV + '/api/tasks';
const CATS = ['teaching','research','admin','personal'];
const CAT_LABELS = {teaching:'Teaching',research:'Research',admin:'Admin',personal:'Personal'};
let tmFilter_ = 'all', tmShowDone = false, tmTasks = [];

function tmSave(t) {
  tmTasks = t;
  fetch(TM_API,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(t)}).catch(()=>{});
}
async function tmInitLoad() {
  try { const r=await fetch(TM_API,{signal:AbortSignal.timeout(3000)}); if(r.ok)tmTasks=await r.json(); } catch{}
  tmRender();
}
function tmAdd() {
  const v=document.getElementById('tm-input').value.trim(); if(!v)return;
  const c=tmFilter_==='all' ? 'teaching' : tmFilter_;
  tmTasks.push({id:Date.now().toString(),title:v,category:c,completed:false});
  tmSave(tmTasks); document.getElementById('tm-input').value=''; tmRender();
}
function tmToggle(id){const t=tmTasks.find(x=>x.id===id);if(t){t.completed=!t.completed;tmSave(tmTasks);tmRender();}}
function tmDelete(id){tmSave(tmTasks.filter(x=>x.id!==id));tmRender();}
function tmEditTitle(id,v){const t=tmTasks.find(x=>x.id===id);if(t){t.title=v;tmSave(tmTasks);}}
function tmEditCat(id,v){const t=tmTasks.find(x=>x.id===id);if(t){t.category=v;tmSave(tmTasks);tmRender();}}
function tmFilter(cat) {
  tmFilter_=cat;
  document.querySelectorAll('.tm-tab').forEach(b=>
    b.classList.toggle('active', b.textContent.toLowerCase()===cat||(cat==='all'&&b.textContent==='All')));
  tmRender();
}
function tmRender() {
  const vis = tmFilter_==='all' ? tmTasks : tmTasks.filter(t=>t.category===tmFilter_);
  const active=vis.filter(t=>!t.completed), done=vis.filter(t=>t.completed);
  const cats = tmFilter_==='all' ? CATS : [tmFilter_];
  let h='';
  for(const cat of cats){
    const items=active.filter(t=>t.category===cat);
    if(tmFilter_!=='all'||items.length){
      h+=`<div class="tm-category"><span class="tm-cat-label cat-${cat}">${CAT_LABELS[cat]}</span>`;
      if(!items.length) h+=`<div style="color:#94a3b8;font-size:.85rem;padding:.3rem .75rem">No tasks</div>`;
      items.forEach(t=>h+=tmTaskHtml(t));
      h+='</div>';
    }
  }
  if(done.length){
    h+=`<button class="tm-completed-toggle" onclick="tmShowDone=!tmShowDone;tmRender()">${tmShowDone?'▾':'▸'} ${done.length} completed</button>`;
    if(tmShowDone){h+='<div style="margin-top:.5rem">';done.forEach(t=>h+=tmTaskHtml(t));h+='</div>';}
  }
  document.getElementById('tm-list').innerHTML=h;
}
function tmTaskHtml(t){
  const opts=CATS.map(c=>`<option value="${c}"${c===t.category?' selected':''}>${CAT_LABELS[c]}</option>`).join('');
  return `<div class="tm-task${t.completed?' done':''}" id="tm-${t.id}">
    <input type="checkbox" ${t.completed?'checked':''} onchange="tmToggle('${t.id}')">
    <input class="tm-title" value="${t.title.replace(/"/g,'&quot;')}"
      onblur="tmEditTitle('${t.id}',this.value)" onkeydown="if(event.key==='Enter')this.blur()">
    <select class="tm-edit-cat" onchange="tmEditCat('${t.id}',this.value)">${opts}</select>
    <button class="tm-del" onclick="tmDelete('${t.id}')" title="Delete">✕</button>
  </div>`;
}

// --- Chat tab: each message starts a Claude Code run on this computer --------
// POST /api/chat carries the page token, like Send and Apply, so no other web
// page and no agent can start a run. The reply streams back as NDJSON lines:
// {"t":"text"|"tool"|"error"|"done", "v": ...}.
let chatBusy = false;

function chatEsc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// A small Markdown renderer. Everything is escaped first, so a reply that
// quotes an email cannot inject markup into the page.
function chatMarkdown(src) {
  const blocks = [];
  let s = chatEsc(src).replace(/```[\w-]*\n?([\s\S]*?)```/g, (_, code) => {
    blocks.push('<pre><code>' + code.replace(/\n$/, '') + '</code></pre>');
    return '\u0000' + (blocks.length - 1) + '\u0000';
  });
  const inline = t => t
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, '$1<em>$2</em>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  const out = [];
  let list = null, para = [];
  const flushPara = () => { if (para.length) { out.push('<p>' + inline(para.join('<br>')) + '</p>'); para = []; } };
  const flushList = () => { if (list) { out.push('<' + list.tag + '>' + list.items.map(i => '<li>' + inline(i) + '</li>').join('') + '</' + list.tag + '>'); list = null; } };
  for (const line of s.split('\n')) {
    let m;
    if (/^\u0000\d+\u0000$/.test(line.trim())) { flushPara(); flushList(); out.push(line.trim()); }
    else if ((m = line.match(/^\s*[-*]\s+(.*)$/))) { flushPara(); if (!list || list.tag !== 'ul') { flushList(); list = {tag: 'ul', items: []}; } list.items.push(m[1]); }
    else if ((m = line.match(/^\s*\d+[.)]\s+(.*)$/))) { flushPara(); if (!list || list.tag !== 'ol') { flushList(); list = {tag: 'ol', items: []}; } list.items.push(m[1]); }
    else if ((m = line.match(/^(#{1,4})\s+(.*)$/))) { flushPara(); flushList(); out.push('<h4>' + inline(m[2]) + '</h4>'); }
    else if (!line.trim()) { flushPara(); flushList(); }
    else { flushList(); para.push(line); }
  }
  flushPara(); flushList();
  return out.join('').replace(/\u0000(\d+)\u0000/g, (_, i) => blocks[+i]);
}

function chatBubble(role) {
  const log = document.getElementById('chat-log');
  const empty = log.querySelector('.chat-empty');
  if (empty) empty.remove();
  const el = document.createElement('div');
  el.className = 'chat-msg ' + role;
  if (role === 'assistant') el.innerHTML = '<div class="chat-tools"></div><div class="chat-body"></div>';
  log.appendChild(el);
  return el;
}

function chatFill(el, msg) {
  el.querySelector('.chat-tools').innerHTML = (msg.tools || []).map(t => '<div>' + chatEsc(t) + '</div>').join('');
  el.querySelector('.chat-body').innerHTML = msg.text ? chatMarkdown(msg.text) : '';
  if (msg.error) el.insertAdjacentHTML('beforeend', '<div class="chat-err">' + chatEsc(msg.error) + '</div>');
}

function chatScroll() { window.scrollTo(0, document.body.scrollHeight); }

function chatSetBusy(b) {
  chatBusy = b;
  document.getElementById('chat-send').disabled = b;
  document.getElementById('chat-new').disabled = b;
}

async function chatLoad() {
  try {
    const r = await fetch('/api/chat');
    const data = await r.json();
    const log = document.getElementById('chat-log');
    if (data.messages && data.messages.length) {
      log.innerHTML = '';
      for (const m of data.messages) {
        const el = chatBubble(m.role);
        if (m.role === 'user') el.textContent = m.text; else chatFill(el, m);
      }
    }
  } catch (e) { /* the empty-state note stays */ }
}

async function chatSend() {
  const box = document.getElementById('chat-text');
  const text = box.value.trim();
  if (!text || chatBusy) return;
  box.value = '';
  chatSetBusy(true);
  chatBubble('user').textContent = text;
  const el = chatBubble('assistant');
  const msg = {text: '', tools: [], error: ''};
  el.querySelector('.chat-body').innerHTML = '<span class="chat-wait">Claude is thinking&hellip;</span>';
  chatScroll();
  try {
    const r = await fetch('/api/chat', {method: 'POST',
      headers: {'Content-Type': 'application/json', ...ACTION_HEADERS},
      body: JSON.stringify({message: text})});
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || ('HTTP ' + r.status));
    }
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    for (;;) {
      const {value, done} = await reader.read();
      if (done) break;
      buf += dec.decode(value, {stream: true});
      let nl;
      while ((nl = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, nl); buf = buf.slice(nl + 1);
        if (!line.trim()) continue;
        const ev = JSON.parse(line);
        if (ev.t === 'text') msg.text += ev.v;
        else if (ev.t === 'tool') msg.tools.push(ev.v);
        else if (ev.t === 'error') msg.error = ev.v;
        chatFill(el, msg);
        if (!msg.text && !msg.error) el.querySelector('.chat-body').innerHTML = '<span class="chat-wait">Working&hellip;</span>';
        chatScroll();
      }
    }
  } catch (e) {
    msg.error = String(e.message || e);
    chatFill(el, msg);
  }
  chatSetBusy(false);
  // Claude may have parked a draft, added an event, or posted a proposal.
  refreshDrafts(); refreshProposals();
  box.focus();
}

async function chatReset() {
  if (chatBusy) return;
  const r = await fetch('/api/chat', {method: 'DELETE', headers: ACTION_HEADERS});
  if (!r.ok) { toast('Could not start a new chat'); return; }
  document.getElementById('chat-log').innerHTML = '<p class="chat-empty">New conversation. Ask Claude about your mail, calendar, or tasks.</p>';
  document.getElementById('chat-text').focus();
}

renderAccountOptions();
chatLoad();
checkServer();
setInterval(checkServer, 30000);
refreshDrafts();
setInterval(refreshDrafts, 15000);
pollBriefing();
setInterval(pollBriefing, 15000);
refreshProposals();
setInterval(refreshProposals, 15000);
loadSection('section-overview');
tmInitLoad();
</script>
</body>
</html>"""
