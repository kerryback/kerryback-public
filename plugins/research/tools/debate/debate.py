"""Debate client: call one OpenRouter voice with (charter + brief) -> JSON.

Stateless by design. The Coordinator invokes this once per debate seat per round,
passing a curated brief; there is no per-agent conversation history (that is the
whole point — see the plugin README). Every call is logged to the project's
canonical JSONL sink, redacted.

Usage (the Coordinator runs this via Bash):
    python -m tools.debate.debate --role proposer --brief-file brief.md \
        --project /path/to/project --round 3

Prints the voice's JSON response to stdout for the Coordinator to read.
Requires OPENROUTER_API_KEY in the environment.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from . import config
from ..logging_ import append_event

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _loads_lenient(content: str) -> dict:
    """Parse a voice's JSON, tolerating what real models actually emit.

    Some models (e.g. DeepSeek) wrap JSON in a ```json ... ``` markdown fence
    despite response_format=json_object; others add a stray prose preamble. Try
    strict first, then a fenced/embedded-object fallback, before giving up to
    `_unparsed` so the Coordinator at least still sees the text.
    """
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        pass
    text = content.strip()
    if text.startswith("```"):
        # drop the opening fence line (``` or ```json) and the closing fence
        text = text.split("\n", 1)[-1] if "\n" in text else text
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # last resort: grab the outermost {...} span
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return {"_unparsed": content}


def call_voice(role: str, brief: str, roster: dict) -> dict:
    seat = roster.get("seats", {}).get(role)
    if not seat:
        raise SystemExit(f"No roster entry for seat '{role}' in config.toml/[seats].")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY is not set.")

    # A seat may reuse another seat's charter (e.g. adversary_2 -> adversary) via
    # a `charter` key; default to a charter named after the seat itself.
    charter_role = seat.get("charter", role)

    body = {
        "model": seat["model"],
        "messages": [
            {"role": "system", "content": config.charter_text(charter_role)},
            {"role": "user", "content": brief},
        ],
        "temperature": seat.get("temperature", 0.7),
        # Ask for JSON; charters also instruct "JSON only" for models that ignore this.
        "response_format": {"type": "json_object"},
    }
    # Pin the provider route for reproducibility (esp. open models).
    if seat.get("provider_order"):
        body["provider"] = {"order": seat["provider_order"], "allow_fallbacks": False}

    req = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/kerryback/coauthor",
            "X-Title": "coauthor",
        },
        method="POST",
    )
    t0 = datetime.now(timezone.utc)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise SystemExit(f"OpenRouter HTTP {e.code}: {detail}")
    latency = (datetime.now(timezone.utc) - t0).total_seconds()

    content = payload["choices"][0]["message"]["content"]
    parsed = _loads_lenient(content)

    return {
        "seat": role,
        "model": seat["model"],
        "request_messages": body["messages"],
        "response_text": content,
        "response_parsed": parsed,
        "usage": payload.get("usage", {}),
        "latency_s": latency,
        "openrouter_id": payload.get("id"),
    }


def _event(project_root, round_id, result) -> dict:
    return {
        "ts": _now(),
        "project_id": project_root.name,
        "round_id": round_id,
        "request_id": str(uuid.uuid4()),
        "kind": "debate_call",
        **result,
    }


def run_seats(seats: list[str], brief: str, roster: dict) -> dict:
    """Call several voices CONCURRENTLY (debate is I/O-bound HTTP) and return
    {seat: result}. One slow voice (e.g. Kimi) no longer serializes the rest —
    the stage takes as long as the slowest seat, not their sum. A seat that
    errors is captured as {"error": ...} so one bad voice never sinks the round.
    """
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max(1, len(seats))) as ex:
        futs = {ex.submit(call_voice, s, brief, roster): s for s in seats}
        for fut in as_completed(futs):
            seat = futs[fut]
            try:
                results[seat] = fut.result()
            except SystemExit as e:  # call_voice raises SystemExit on API/config errors
                results[seat] = {"seat": seat, "error": str(e)}
            except Exception as e:
                results[seat] = {"seat": seat, "error": repr(e)}
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", help="a single debate seat, e.g. proposer")
    ap.add_argument("--seats", help="comma-separated seats to run CONCURRENTLY, "
                                    "e.g. adversary,adversary_2")
    ap.add_argument("--brief-file", help="path to the brief (else read stdin)")
    ap.add_argument("--project", help="project root (default: discover from cwd)")
    ap.add_argument("--round", type=int, default=0)
    args = ap.parse_args()
    if not (args.role or args.seats):
        ap.error("pass --role <seat> or --seats a,b,c")

    project_root = config.find_project_root(args.project)
    roster = config.load_roster(project_root)
    brief = (
        open(args.brief_file, encoding="utf-8").read()
        if args.brief_file
        else sys.stdin.read()
    )

    if args.seats:
        seats = [s.strip() for s in args.seats.split(",") if s.strip()]
        results = run_seats(seats, brief, roster)
        # Log sequentially in the main thread (avoids interleaved JSONL writes).
        for seat in seats:
            r = results.get(seat, {})
            if "error" not in r:
                append_event(project_root, _event(project_root, args.round, r))
        out = {seat: results[seat].get("response_parsed", results[seat])
               for seat in seats}
        json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return

    result = call_voice(args.role, brief, roster)
    append_event(project_root, _event(project_root, args.round, result))
    # Hand the parsed JSON back to the Coordinator.
    json.dump(result["response_parsed"], sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
