#!/usr/bin/env python3
"""A voice whiteboard tutor run by Claude Code: an MCP server (stdio) for
Claude and a local web page (the whiteboard) for the student.

Claude Code is the tutor. There is no API key and no model call here: Claude
calls this server's tools. The tutor's own tools (from its topic.py) and the
ones every tutor has (calculate, save_progress, start_module, show_plot) run
the same code as the live tutors. Three tools are new:

  open_whiteboard    start the page on 127.0.0.1 and open it in the browser
  say                put a reply on the board; the browser speaks its prose
  wait_for_student   end the turn and wait for the student's next message

Speech runs in the browser (Kokoro and Whisper, in static/speech-worker.js), so
this file needs only the Python standard library (3.9 or later).

The student record (progress, past sessions) is kept in
$CLAUDE_PLUGIN_DATA/record.json, or ~/.claude/tutors/<name>/record.json.
"""

import json
import os
import queue
import secrets
import sys
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "tutor"))

import tutor_config as cfg  # noqa: E402
import intros  # noqa: E402
from speech_text import SpeechStream  # noqa: E402
from tools import TOOLS as TUTOR_TOOLS, ToolError, run_tool  # noqa: E402

PORT = int(os.environ.get("TUTOR_PORT", "8030"))
WAIT_SECONDS = int(os.environ.get("TUTOR_WAIT_SECONDS", "300"))
IDLE_SECONDS = int(os.environ.get("VOICE_IDLE_SECONDS", "45"))
DATA = Path(os.environ.get("CLAUDE_PLUGIN_DATA") or Path.home() / ".claude" / "tutors" / cfg.NAME)
RECORD = DATA / "record.json"
IDLE_TEXT = "Press the button when you are ready to continue."
SESSION_START = ("[Session start. This note is from the app, not the student. "
                 "Open the session as the protocol says.]")


def log(*args):
    print(*args, file=sys.stderr, flush=True)


def record_text(progress):
    """The student record, as the live tutors put it in the system prompt."""
    if not progress:
        return "Student record: none. This is the student's first session."
    lines = ["Student record from earlier sessions:"]
    if progress.get("modules_done"):
        lines.append("Modules done: " + ", ".join(str(m) for m in progress["modules_done"]))
    if progress.get("now_in"):
        lines.append("Now in: " + progress["now_in"])
    if progress.get("objectives_met"):
        lines.append("Objectives met: " + ", ".join(str(o) for o in progress["objectives_met"]))
    if progress.get("mistakes_seen"):
        lines.append("Mistakes seen: " + "; ".join(progress["mistakes_seen"]))
    if progress.get("notes"):
        lines.append("Notes: " + progress["notes"])
    return "\n".join(lines)


# --- the session -------------------------------------------------------------

class Session:
    """The board, the student record and the two queues between them: events
    to the page (one queue per open page) and messages to Claude (inbox)."""

    def __init__(self):
        self.lock = threading.RLock()
        self.record = self._load()
        self.display = []          # what the board shows, for a page that (re)loads
        self.trees = {}            # what the tutor's tools keep between calls
        self.inbox = queue.Queue() # the student's messages and the app's notes, for Claude
        self.pages = []            # one event queue per open page
        self.turn = False          # a student message is out; Claude has not finished its reply
        self.waiter = None         # the request id of the current wait_for_student

    def _load(self):
        try:
            return json.loads(RECORD.read_text())
        except (OSError, ValueError):
            return {"progress": None, "past_sessions": 0}

    def save(self):
        DATA.mkdir(parents=True, exist_ok=True)
        tmp = RECORD.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.record, indent=1))
        tmp.replace(RECORD)

    def new(self):
        """A new board for a new Claude Code session. The record carries over."""
        with self.lock:
            if self.display:
                self.record["past_sessions"] = self.record.get("past_sessions", 0) + 1
                self.save()
            self.display, self.trees, self.turn = [], {}, False
            while not self.inbox.empty():
                self.inbox.get_nowait()
            self.emit({"type": "reset"})

    def emit(self, ev):
        with self.lock:
            for q in self.pages:
                q.put(ev)

    def first_session(self):
        return not self.record.get("progress") and not self.record.get("past_sessions")

    # What the page shows and speaks.

    def tutor_text(self, md, intro=False):
        """A reply (or an intro) on the board; its prose is spoken."""
        entry = {"role": "tutor", "text": md}
        if intro:
            entry["intro"] = True
        self.display.append(entry)
        speech = SpeechStream()
        self.emit({"type": "text", "text": md if intro else md.rstrip("\n") + "\n\n"})
        for sentence in speech.feed(md) + speech.flush():
            self.emit({"type": "say", "text": sentence})

    def play_intro(self, md):
        self.emit({"type": "break"})
        self.tutor_text(md, intro=True)
        self.emit({"type": "break"})

    # Messages from the page.

    def from_page(self, message="", start=False, module=None):
        with self.lock:
            self.turn = True
            if module is not None:
                if module not in intros.MODULES:
                    raise ValueError("There is no such module.")
                self.display.append({"role": "student",
                                     "text": f"Take me to Module {module}: {intros.MODULES[module]['title']}."})
                self.play_intro(intros.markdown(module))
                self.inbox.put("[This note is from the app, not the student. The student picked Module "
                               f"{module} from the menu.] " + intros.note(module))
            elif start:
                note = SESSION_START
                if intros.COURSE and self.first_session() and not self.display:
                    self.play_intro(intros.course_markdown())
                    note = SESSION_START[:-1] + " " + intros.COURSE_NOTE + "]"
                self.inbox.put(note + "\n\n" + record_text(self.record.get("progress")))
            else:
                self.display.append({"role": "student", "text": message})
                self.inbox.put(message)

    # Tools.

    def call(self, name, args, req_id):
        if name == "open_whiteboard":
            return open_whiteboard()
        if name == "say":
            text = str(args.get("text", "")).strip()
            if not text:
                raise ToolError("Nothing to say.")
            with self.lock:
                self.tutor_text(text)
            return "Shown on the board; the prose is being spoken."
        if name == "wait_for_student":
            return self.wait(req_id)
        with self.lock:
            state = {"trees": self.trees, "progress": self.record.get("progress")}
            text, payload = run_tool(name, args, state)
            if name == "save_progress":
                self.record["progress"] = state["progress"]
                self.save()
            if payload:
                if "intro" in payload:
                    self.play_intro(intros.markdown(payload["intro"]))
                elif "plot" in payload:
                    self.display.append({"role": "plot", "plot": payload["plot"]})
                    self.emit({"type": "plot", "plot": payload["plot"]})
                else:
                    self.display.append({"role": "tree", "tree": payload})
                    self.emit({"type": "tree", "tree": payload})
            return text

    def wait(self, req_id):
        """End the turn and wait for the student. A newer wait (or a cancelled
        request) takes over without losing a message."""
        with self.lock:
            self.waiter = req_id
            if self.turn:
                self.turn = False
                self.emit({"type": "done"})
            pages = len(self.pages)
        end = time.monotonic() + WAIT_SECONDS
        while time.monotonic() < end:
            if self.waiter != req_id:
                return "This wait was replaced by a newer one."
            try:
                msg = self.inbox.get(timeout=1)
            except queue.Empty:
                continue
            if self.waiter != req_id:          # superseded while getting: hand it on
                self.inbox.put(msg)
                return "This wait was replaced by a newer one."
            return "The student: " + msg if not msg.startswith("[") else msg
        hint = "" if pages or self.pages else (
            f" The whiteboard page is not open: ask the student to open {url()}.")
        return ("No message from the student yet. The board is waiting. "
                "Call wait_for_student again." + hint)


S = Session()


# --- the whiteboard page -------------------------------------------------------

TOKEN = secrets.token_urlsafe(16)
_server = None
_port = None


def url():
    return f"http://127.0.0.1:{_port}/?t={TOKEN}" if _port else "(not started)"


def page_config():
    return {"voice": True, "voice_ready": True, "idle_seconds": IDLE_SECONDS, "idle_text": IDLE_TEXT,
            "modules": [{"n": m["n"], "title": m["title"]} for m in intros.MODULES.values()],
            "kokoro_voice": os.environ.get("KOKORO_VOICE", "af_heart"),
            "kokoro_speed": float(os.environ.get("KOKORO_SPEED", "0.9"))}


TYPES = {".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css",
         ".jpg": "image/jpeg", ".png": "image/png", ".html": "text/html; charset=utf-8"}


class Page(BaseHTTPRequestHandler):
    def log_message(self, *a):   # stdout carries MCP; keep the access log off it
        pass

    def _host_ok(self):   # refuse DNS-rebinding requests
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def _token_ok(self, query=False):
        """The token from the link Claude opened: a header, or (for EventSource,
        which cannot send headers) ?t= on a GET."""
        given = self.headers.get("X-Tutor-Token", "")
        if not given and query:
            given = parse_qs(urlparse(self.path).query).get("t", [""])[0]
        return secrets.compare_digest(given, TOKEN)

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"detail": "Forbidden."})
        path = self.path.split("?")[0]
        if path == "/":
            html = (HERE / "board.html").read_text()
            for key in ("TITLE", "SUBTITLE", "NAME"):
                html = html.replace("{{" + key + "}}", getattr(cfg, key))
            return self._send(200, html, TYPES[".html"])
        if path.startswith("/static/"):
            f = (HERE / "static" / path[len("/static/"):]).resolve()
            if f.parent != (HERE / "static").resolve() or not f.is_file():
                return self._send(404, {"detail": "Not found."})
            return self._send(200, f.read_bytes(), TYPES.get(f.suffix, "application/octet-stream"))
        if not self._token_ok(query=True):
            return self._send(401, {"detail": "Open the link Claude gave you."})
        if path == "/api/config":
            return self._send(200, page_config())
        if path == "/api/me":
            with S.lock:
                return self._send(200, {"name": "", "display": S.display, "fresh": not S.display,
                                        "busy": S.turn})
        if path == "/api/events":
            return self._events()
        return self._send(404, {"detail": "Not found."})

    def _events(self):
        q = queue.Queue()
        with S.lock:
            S.pages.append(q)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            while True:
                try:
                    ev = q.get(timeout=15)
                    self.wfile.write(f"data: {json.dumps(ev)}\n\n".encode())
                except queue.Empty:
                    self.wfile.write(b": keep-alive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with S.lock:
                if q in S.pages:
                    S.pages.remove(q)

    def do_POST(self):
        if not self._host_ok() or not self._token_ok():
            return self._send(403, {"detail": "Forbidden."})
        if self.path != "/api/message":
            return self._send(404, {"detail": "Not found."})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n > 20000:
                return self._send(413, {"detail": "Message too long."})
            body = json.loads(self.rfile.read(n) or b"{}")
            message = str(body.get("message") or "").strip()
            start, module = bool(body.get("start")), body.get("module")
            if module is not None:
                module = int(module)
            if not (start or module is not None or message):
                return self._send(400, {"detail": "Empty message."})
            with S.lock:
                if S.turn:
                    return self._send(409, {"detail": "The tutor is still answering your last message."})
                S.from_page(message, start, module)
        except ValueError as e:
            return self._send(400, {"detail": str(e)})
        return self._send(200, {"ok": True})


def open_whiteboard():
    global _server, _port
    if _server is None:
        for port in [PORT] + list(range(PORT + 1, PORT + 20)) + [0]:
            try:
                _server = ThreadingHTTPServer(("127.0.0.1", port), Page)
                break
            except OSError:
                continue
        _server.daemon_threads = True
        _port = _server.server_address[1]
        threading.Thread(target=_server.serve_forever, daemon=True).start()
    S.new()
    opened = False
    try:
        opened = webbrowser.open(url())
    except Exception:
        pass
    where = ("The whiteboard is open in the student's browser at " if opened
             else "Could not open a browser. Ask the student to open ") + url() + "."
    return (where + " The student presses Start there. Now call wait_for_student: its first "
            "message is the session-start note.\n\n" + record_text(S.record.get("progress")))


# --- MCP over stdio -------------------------------------------------------------

NEW_TOOLS = [
    {"name": "open_whiteboard",
     "description": ("Start the tutoring session: opens the whiteboard page in the student's browser "
                     "and returns its address and the student record. Call once, first."),
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "say",
     "description": ("Your reply to the student. The student never sees anything else you write. "
                     "Markdown, following the Voice mode rules: plain paragraphs are spoken and not "
                     "shown; '## Title' headings, list items, tables and $$ display math are shown "
                     "on the board and not spoken. Call it once per turn, or once before and once "
                     "after a tree or plot. Then call wait_for_student."),
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}},
                     "required": ["text"]}},
    {"name": "wait_for_student",
     "description": ("End your turn and wait for the student's next message (spoken or typed), or a "
                     "note from the app in square brackets (session start, a module picked from the "
                     "menu). Returns after a few minutes with no message; then call it again."),
     "inputSchema": {"type": "object", "properties": {}}},
]
TOOLS = NEW_TOOLS + [{"name": t["name"], "description": t["description"],
                      "inputSchema": t["input_schema"]} for t in TUTOR_TOOLS]

_out = threading.Lock()


def send(obj):
    with _out:
        sys.stdout.write(json.dumps(obj) + "\n")
        sys.stdout.flush()


def handle(msg):
    method, req_id, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if req_id is None:   # a notification
        if method == "notifications/cancelled":
            rid = params.get("requestId")
            if rid is not None and S.waiter == rid:
                S.waiter = None
        return
    if method == "initialize":
        result = {"protocolVersion": params.get("protocolVersion", "2025-06-18"),
                  "capabilities": {"tools": {}},
                  "serverInfo": {"name": f"{cfg.NAME}-tutor", "version": "1.0.0"},
                  "instructions": (f"The {cfg.TITLE}. Use these tools only while running the tutor "
                                   "skill, which says how.")}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        try:
            text, err = S.call(name, args, req_id), False
        except (ToolError, KeyError, TypeError, ValueError) as e:
            text, err = f"Error: {e}", True
        except Exception as e:
            log(traceback.format_exc())
            text, err = f"Error: {e}", True
        result = {"content": [{"type": "text", "text": text}], "isError": err}
    else:
        send({"jsonrpc": "2.0", "id": req_id,
              "error": {"code": -32601, "message": f"Unknown method {method!r}."}})
        return
    send({"jsonrpc": "2.0", "id": req_id, "result": result})


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        # Each request on its own thread: wait_for_student blocks for minutes.
        threading.Thread(target=handle, args=(msg,), daemon=True).start()


if __name__ == "__main__":
    main()
