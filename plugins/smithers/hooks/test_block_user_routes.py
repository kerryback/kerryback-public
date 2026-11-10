"""Unit tests for the Smithers PreToolUse hook's matcher.

Run:  python3 -m unittest plugins/smithers/hooks/test_block_user_routes.py -v
(or `python3 test_block_user_routes.py` from this directory). Standard library
only, so it runs under the same python3 the hook uses.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import block_user_routes as hook  # noqa: E402

BASE = "http://127.0.0.1:8020"

BLOCKED_BASH = [
    # send
    f"curl -s -X POST {BASE}/api/email/send -H 'Content-Type: application/json' -d '{{}}'",
    "curl -s -X POST http://localhost:8020/api/email/send -d '{}'",
    "curl -X POST localhost:8021/api/email/send",
    "curl -s --data '{\"to\":\"a@b.c\"}' http://[::1]:8020/api/email/send",
    "wget --post-data='{}' http://127.0.0.1:8020/api/email/send",
    "http POST :8020/api/email/send to=a@b.c",
    # URL in a variable
    "U=http://127.0.0.1:8020/api/email/send; curl -s -X POST \"$U\" -d '{}'",
    "BASE=http://127.0.0.1:8020\ncurl -s -X POST \"$BASE/api/email/send\" -d @body.json",
    "curl -s -X POST \"${SMITHERS}/api/email/send\"",
    # cheap disguises a server would undo
    "curl -X POST http://127.0.0.1:8020/api//email/send",
    "curl -X POST http://127.0.0.1:8020/api/./email/send",
    "curl -X POST http://127.0.0.1:8020/api/email/sen%64",
    "curl -X POST http://127.0.0.1:8020/api/email/send/",
    # apply
    f"curl -s -X POST {BASE}/api/calendar/proposals/abc123/apply -d '{{}}'",
    f"curl -s -X POST {BASE}/api/calendar/proposals/$PID/apply",
    # the Chat tab: an agent must not start another agent
    f"curl -s -X POST {BASE}/api/chat -H 'Content-Type: application/json' -d '{{\"message\":\"hi\"}}'",
    f"curl -s -X DELETE {BASE}/api/chat",
    f"curl -s {BASE}/api/chat",
    # bulk delete
    f"curl -s -X POST {BASE}/api/calendar/events/delete -d '{{\"events\":[]}}'",
    # PATCH / DELETE on one event
    f"curl -s -X PATCH {BASE}/api/calendar/events/evt123 -d '{{}}'",
    f"curl -s -XPATCH {BASE}/api/calendar/events/evt123",
    f"curl -s --request DELETE '{BASE}/api/calendar/events/evt123?account=work'",
    f"curl -s --request=DELETE {BASE}/api/calendar/events/evt123",
    f"curl -s -X delete {BASE}/api/calendar/events/evt123",
    "E=http://localhost:8020/api/calendar/events/evt123; curl -X PATCH \"$E\"",
    "python3 -c \"import requests; requests.delete('http://127.0.0.1:8020/api/calendar/events/x?account=a')\"",
    "python3 -c \"import requests; requests.patch('http://127.0.0.1:8020/api/calendar/events/x', json={})\"",
]

ALLOWED_BASH = [
    # the agent's own routes
    f"curl -s {BASE}/api/inbox",
    f"curl -s {BASE}/api/ping",
    f"curl -s '{BASE}/api/message/abc?account=work'",
    f"curl -s '{BASE}/api/calendar?start_date=2026-11-04&end_date=2026-11-10'",
    f"curl -s '{BASE}/api/calendar/event/evt123?account=work'",
    f"curl -s {BASE}/api/calendar/proposals",
    f"curl -s {BASE}/api/drafts",
    f"curl -s {BASE}/api/briefing/status",
    f"curl -s -X POST {BASE}/api/drafts -H 'Content-Type: application/json' "
    "-d '{\"to\":\"a@b.c\",\"subject\":\"Re: send me the deck\",\"body\":\"Will send it Monday.\"}'",
    f"curl -s -X POST {BASE}/api/briefing -d '{{\"html\":\"<p>Delete nothing; patch notes due</p>\"}}'",
    f"curl -s -X POST {BASE}/api/briefing/refresh-request",
    f"curl -s -X POST {BASE}/api/calendar/events -H 'Content-Type: application/json' "
    "-d '{\"title\":\"Delete old slides\",\"start\":\"2026-11-12T14:00:00+01:00\",\"end\":\"2026-11-12T15:00:00+01:00\"}'",
    f"curl -s -X POST {BASE}/api/calendar/proposals -d "
    "'{\"changes\":[{\"action\":\"delete\",\"event_id\":\"e1\",\"title\":\"x\",\"reason\":\"dup\"}]}'",
    # mentioning a path without making a request
    "grep -n '/api/email/send' backend/app.py",
    "sed -n '700,760p' backend/app.py | grep -n 'calendar/events/delete'",
    "git log --oneline -5",
    "git diff -- plugins/smithers",
    # unrelated commands
    "ls -la ~/.smithers",
    "curl -s https://example.com/api/emails/sender",
    "curl -s -X DELETE https://api.github.com/repos/o/r/git/refs/heads/x",
    "curl -X PATCH http://127.0.0.1:9000/api/calendars/events-x",
    "python3 -m pytest -q",
    "date",
    f"curl -s {BASE}/api/chatter",
]


class MatcherTests(unittest.TestCase):
    def test_blocked_bash(self):
        for cmd in BLOCKED_BASH:
            with self.subTest(cmd=cmd):
                self.assertIsNotNone(hook.check({"tool_name": "Bash",
                                                 "tool_input": {"command": cmd}}))

    def test_allowed_bash(self):
        for cmd in ALLOWED_BASH:
            with self.subTest(cmd=cmd):
                self.assertIsNone(hook.check({"tool_name": "Bash",
                                              "tool_input": {"command": cmd}}))

    def test_webfetch(self):
        self.assertIsNotNone(hook.check({"tool_name": "WebFetch", "tool_input": {
            "url": "http://localhost:8020/api/email/send", "prompt": "x"}}))
        self.assertIsNotNone(hook.check({"tool_name": "WebFetch", "tool_input": {
            "url": "http://127.0.0.1:8020/api/calendar/proposals/p1/apply", "prompt": "x"}}))
        self.assertIsNone(hook.check({"tool_name": "WebFetch", "tool_input": {
            "url": "http://127.0.0.1:8020/api/inbox", "prompt": "x"}}))

    def test_other_tools(self):
        # e.g. a browser-automation tool running fetch() in the page
        js = ("() => fetch('/api/calendar/events/e1?account=a', "
              "{method: 'DELETE', headers: {'X-Smithers-Action': t}})")
        self.assertIsNotNone(hook.check({"tool_name": "mcp__playwright__browser_evaluate",
                                         "tool_input": {"function": js}}))
        self.assertIsNotNone(hook.check({"tool_name": "mcp__playwright__browser_navigate",
                                         "tool_input": {"url": "http://localhost:8020/api/email/send"}}))
        self.assertIsNone(hook.check({"tool_name": "mcp__playwright__browser_navigate",
                                      "tool_input": {"url": "http://localhost:8020/"}}))

    def test_file_tools_not_checked(self):
        src = "fetch(SRV + '/api/email/send', {method:'POST'})"
        for tool, inp in [("Edit", {"file_path": "app.py", "old_string": src, "new_string": src}),
                          ("Grep", {"pattern": "/api/email/send"}),
                          ("Write", {"file_path": "x.sh", "content": f"curl -X POST {BASE}/api/email/send"})]:
            with self.subTest(tool=tool):
                self.assertIsNone(hook.check({"tool_name": tool, "tool_input": inp}))

    def test_deny_output_shape(self):
        """Run the script as Claude Code does: JSON on stdin, decision on stdout."""
        def run(cmd):
            p = subprocess.run([sys.executable, str(HERE / "block_user_routes.py")],
                               input=json.dumps({"hook_event_name": "PreToolUse",
                                                 "tool_name": "Bash",
                                                 "tool_input": {"command": cmd}}),
                               capture_output=True, text=True, timeout=10)
            self.assertEqual(p.returncode, 0, p.stderr)
            return p.stdout
        out = json.loads(run(f"curl -X POST {BASE}/api/email/send"))
        hso = out["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], "PreToolUse")
        self.assertEqual(hso["permissionDecision"], "deny")
        self.assertIn("user's own action", hso["permissionDecisionReason"])
        self.assertEqual(run(f"curl -s {BASE}/api/inbox"), "")

    def test_bad_input_fails_open(self):
        p = subprocess.run([sys.executable, str(HERE / "block_user_routes.py")],
                           input="not json", capture_output=True, text=True, timeout=10)
        self.assertEqual((p.returncode, p.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
