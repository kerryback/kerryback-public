"""
Background meeting reminder process.
Sends a Pushover push notification + audio alert before each calendar event.

Reads the calendar through the Gmail/Calendar MCP connector
(mcp-servers/gmail_mcp.py), which must be running --- this process never talks
to Google directly.

Add to ~/.env:
    PUSHOVER_USER_KEY=...      # from pushover.net -> Your User Key
    PUSHOVER_APP_TOKEN=...     # from pushover.net -> Create an Application

Pushover is optional --- set only the keys you have.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

load_dotenv(Path.home() / ".env")
load_dotenv(Path(os.environ.get("SMITHERS_HOME", Path.home() / ".smithers")).expanduser() / ".env")

# --- Configuration ------------------------------------------------------------

CONNECTOR_URL = os.environ.get("CONNECTOR_URL", "http://127.0.0.1:8800/mcp")
CONNECTOR_TOKEN = os.environ.get("CONNECTOR_TOKEN", "")

REMINDER_MINUTES = 10         # standard reminder --- Pushover + audio
REMINDER_URGENT_MINUTES = 1   # urgent reminder  --- Pushover high priority only

CHECK_INTERVAL = 60  # seconds between calendar checks

PUSHOVER_USER_KEY = os.getenv("PUSHOVER_USER_KEY", "")
PUSHOVER_APP_TOKEN = os.getenv("PUSHOVER_APP_TOKEN", "")


# --- Calendar via the connector -----------------------------------------------

async def _list_calendar() -> list:
    headers = {"Authorization": f"Bearer {CONNECTOR_TOKEN}"} if CONNECTOR_TOKEN else None
    async with streamablehttp_client(CONNECTOR_URL, headers=headers) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            res = await s.call_tool("list_calendar", {})
            return json.loads(res.content[0].text if res.content else "[]")


# --- Notification senders -----------------------------------------------------

def _pushover(title: str, message: str, priority: int = 0) -> None:
    if not PUSHOVER_USER_KEY or not PUSHOVER_APP_TOKEN:
        return
    try:
        requests.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token":    PUSHOVER_APP_TOKEN,
                "user":     PUSHOVER_USER_KEY,
                "title":    title,
                "message":  message,
                "priority": priority,  # 0 = normal, 1 = high
            },
            timeout=5,
        )
    except Exception as ex:
        print(f"Pushover error: {ex}")


def _audio(message: str) -> None:
    if sys.platform != "darwin":
        return
    try:
        subprocess.Popen(["say", message])
    except Exception as ex:
        print(f"Audio error: {ex}")


# --- Reminder logic -------------------------------------------------------------

_fired: set[tuple[str, int]] = set()


def _parse_start(start_str: str) -> datetime | None:
    if not start_str or "T" not in start_str:
        return None  # all-day event
    try:
        dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _check() -> None:
    try:
        events = asyncio.run(_list_calendar())
    except Exception as ex:
        print(f"Calendar fetch error: {ex}")
        return

    now = datetime.now(timezone.utc)

    for event in events:
        if "error" in event:
            continue
        event_id = event.get("event_id", "")
        if not event_id:
            continue

        start = _parse_start(event.get("start", ""))
        if start is None:
            continue

        minutes_away = (start - now).total_seconds() / 60
        title = event.get("title", "(no title)")
        attendees = event.get("attendees", [])

        for lead, urgent in [(REMINDER_MINUTES, False), (REMINDER_URGENT_MINUTES, True)]:
            key = (event_id, lead)
            if key in _fired:
                continue
            if abs(minutes_away - lead) <= 1.0:
                mins = max(0, round(minutes_away))
                label = f"in {mins} min" if mins > 0 else "starting now"
                suffix = ""
                if attendees:
                    suffix = " · " + ", ".join(attendees[:2])
                    if len(attendees) > 2:
                        suffix += f" +{len(attendees)-2}"

                print(f"Reminder ({lead}m): {title} {label}")
                _pushover(title=title, message=label + suffix,
                          priority=1 if urgent else 0)
                _audio(f"Meeting {'starting now' if mins == 0 else f'in {mins} minutes'}: {title}")

                _fired.add(key)


def run() -> None:
    services = []
    if PUSHOVER_USER_KEY:
        services.append("Pushover")
    print(f"Reminders running ({', '.join(services) or 'no services configured'}). "
          f"Checking every {CHECK_INTERVAL}s via connector at {CONNECTOR_URL}.")
    while True:
        _check()
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run()
