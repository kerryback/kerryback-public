#!/usr/bin/env python3
"""PreToolUse hook: deny tool calls aimed at Smithers' user-only routes.

Smithers keeps a few actions for the user's own clicks in the browser:

    POST   /api/email/send                          (Send)
    PATCH  /api/calendar/events/{event_id}           (Save an edited event)
    DELETE /api/calendar/events/{event_id}           (Delete one event)
    POST   /api/calendar/events/delete               (Delete selected events)
    POST   /api/calendar/proposals/{id}/apply        (Apply a proposal)
    POST   /api/chat, DELETE /api/chat               (Send and New chat, in Chat)

The app listens on 127.0.0.1, so anything Claude Code runs through Bash can
reach it. This hook reads each tool call before it runs and denies it when the
call names one of those paths and looks like a network request. It matches on the
URL path, so the host form (127.0.0.1, localhost, a port, a variable holding the
base URL) does not matter.

What it is and is not
---------------------
It raises the bar; it is not a security boundary. It matches text. An agent that
means to get round it can: split the path across shell variables, encode it in
a way this file does not decode, write a script to a file and run it in a later
call, and so on. It also fails open: if python3 is missing or the input cannot
be parsed, the call goes ahead. The app's per-launch page token (see
backend/app.py) is a second, equally partial check. Neither replaces the rule
in SKILL.md that the agent never calls these routes.

What it leaves alone
--------------------
Every other route, including the agent's own: the GET routes, POST /api/drafts,
POST /api/briefing, POST /api/calendar/events (add), and
POST /api/calendar/proposals (propose). Commands that only mention a user-only
path without making a request (grep, sed, git) are let through, and the file
tools (Read, Edit, Write, Grep, ...) are not checked, so the app's own source can
still be read and edited.
"""
from __future__ import annotations

import json
import re
import sys
from urllib.parse import unquote

# Paths that are user-only whatever the method.
_SEG = r"[^/\s'\"?#&;|)<>`]+"           # one path segment, e.g. an id
_ALWAYS = [
    (re.compile(r"/api/email/send(?![\w-])"), "send mail (POST /api/email/send)"),
    (re.compile(r"/api/calendar/proposals/" + _SEG + r"/apply(?![\w-])"),
     "apply a calendar proposal (POST /api/calendar/proposals/{id}/apply)"),
    (re.compile(r"/api/calendar/events/delete(?![\w-])"),
     "delete calendar events (POST /api/calendar/events/delete)"),
    # The Chat tab starts a Claude Code run. An agent must not start another.
    (re.compile(r"/api/chat(?![\w-])"),
     "use the Chat tab (/api/chat), which starts a new Claude Code run"),
]
# /api/calendar/events/{id} is user-only for PATCH and DELETE. (Adding an event,
# POST /api/calendar/events, has no id segment and is allowed.)
_EVENT_ID = re.compile(r"/api/calendar/events/(?!delete(?![\w-]))" + _SEG)
_EDIT_METHOD = re.compile(r"(?:(?<![A-Za-z])|(?<=-X))(PATCH|DELETE)(?![A-Za-z])",
                          re.IGNORECASE)   # also curl's -XPATCH

# Signs that the call makes a request, as opposed to mentioning a path.
_HOST = re.compile(
    r"127\.0\.0\.1|localhost|0\.0\.0\.0|\[::1\]|::1|:\d{2,5}/api/", re.IGNORECASE)
_CLIENT = re.compile(
    r"(?<![\w-])(curl|wget|https?|httpie|xh|python[0-9.]*|node|deno|bun|perl|ruby|"
    r"php|nc|ncat|socat|telnet|requests|urllib[0-9]*|httpx|aiohttp|fetch|"
    r"XMLHttpRequest|osascript|open|Invoke-WebRequest|Invoke-RestMethod|iwr|irm)"
    r"(?![\w-])", re.IGNORECASE)

# Local file tools never make a request; checking them would block editing the
# app's own source. hooks.json skips them too; this list is the backstop.
_FILE_TOOLS = {"Read", "Write", "Edit", "MultiEdit", "NotebookEdit", "Grep",
               "Glob", "LS", "TodoWrite"}


def _normalize(text: str) -> str:
    """Undo the cheap disguises a server would undo too: percent-encoding,
    doubled slashes, and /./ segments (curl and uvicorn both resolve these)."""
    out = text
    for _ in range(3):                     # %2525 -> %25 -> %
        decoded = unquote(out)
        if decoded == out:
            break
        out = decoded
    out = out.replace("\\/", "/")          # JSON-escaped slashes
    out = re.sub(r"/(?:\./)+", "/", out)
    out = re.sub(r"/{2,}api/", "/api/", out)
    out = re.sub(r"(?<=/api)/{2,}", "/", out)
    return out


def blocked_reason(text: str) -> str | None:
    """Return a description of the user-only action `text` targets, or None.

    `text` is a Bash command, or the JSON of any other tool's input.
    """
    if not text or "api" not in text.lower() and "%" not in text:
        return None
    norm = _normalize(text)
    if not (_HOST.search(norm) or _CLIENT.search(norm)):
        return None
    for pattern, what in _ALWAYS:
        if pattern.search(norm):
            return what
    if _EVENT_ID.search(norm):
        m = _EDIT_METHOD.search(norm)
        if m:
            verb = m.group(1).upper()
            noun = "edit" if verb == "PATCH" else "delete"
            return f"{noun} a calendar event ({verb} /api/calendar/events/{{id}})"
    return None


def check(payload: dict) -> str | None:
    tool = payload.get("tool_name", "")
    if tool in _FILE_TOOLS:
        return None
    tool_input = payload.get("tool_input") or {}
    if tool == "Bash" and isinstance(tool_input, dict):
        text = str(tool_input.get("command", ""))
    else:
        text = json.dumps(tool_input, ensure_ascii=False)
    return blocked_reason(text)


def deny_message(what: str) -> str:
    return (
        f"Blocked by the Smithers plugin: this call would {what}. That route is "
        "the user's own action, from the button in the Smithers page in the "
        "browser. Do not call it, and do not try another way to reach it. Park a "
        "draft (POST /api/drafts) or post a proposal (POST /api/calendar/proposals) "
        "instead, and tell the user it is waiting for them.")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0                          # fail open; see the module docstring
    what = check(payload) if isinstance(payload, dict) else None
    if what:
        json.dump({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": deny_message(what),
        }}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
