#!/usr/bin/env python3
"""First-run setup for Smithers, driven by Claude Code.

Everything personal lives in ~/.smithers (override with SMITHERS_HOME): the
account list, the Google OAuth client, and the per-account tokens. Nothing about
a particular mailbox is baked into the package, so a second person installs the
plugin, runs this, and is on their own accounts.

  python scripts/setup.py --status
      What's done and what's left, as JSON. Safe to run any time.

  python scripts/setup.py --add-account work me@university.edu
      Record an account. Repeat for as many as you have. The first one added is
      the default (the one new messages are sent from unless told otherwise).

  python scripts/setup.py --remove-account work

  python scripts/setup.py --authorize work
      Open Google's consent screen for that account and save its token. Needs
      ~/.smithers/credentials.json to exist first. Omit the label to do every
      account that still needs one.

The one manual step is the OAuth client, because only the account owner can
create it: Google Cloud Console -> APIs & Services -> Credentials -> Create
credentials -> OAuth client ID -> Desktop app -> download the JSON and save it
as ~/.smithers/credentials.json. Enable the Gmail API and the Calendar API for
that project. --status reports whether this is done.
"""
import argparse
import json
import os
import pickle
import sys
from pathlib import Path

HOME_DIR = Path(os.environ.get("SMITHERS_HOME", Path.home() / ".smithers")).expanduser()
CONFIG_FILE = HOME_DIR / "config.json"
CREDS_FILE = HOME_DIR / "credentials.json"

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

CREDS_HELP = (
    "Create a Google OAuth client and save it as ~/.smithers/credentials.json: "
    "console.cloud.google.com -> create or pick a project -> enable the Gmail API "
    "and the Google Calendar API -> APIs & Services -> Credentials -> Create "
    "credentials -> OAuth client ID -> Application type: Desktop app -> Create -> "
    "Download JSON. Only you can do this step; it is per-Google-account."
)


def _load_config() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_config(cfg: dict) -> None:
    HOME_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def _accounts() -> dict:
    accts = _load_config().get("accounts")
    return accts if isinstance(accts, dict) else {}


def status() -> dict:
    accts = _accounts()
    tokens = {a: (HOME_DIR / f"token_{a}.pickle").exists() for a in accts}
    have_creds = CREDS_FILE.exists()
    needs_auth = [a for a, ok in tokens.items() if not ok]
    if not accts:
        step = ("add-account", "No accounts recorded yet. Ask the user which Google "
                "address(es) to use, then run --add-account <label> <email> for each.")
    elif not have_creds:
        step = ("credentials", CREDS_HELP)
    elif needs_auth:
        step = ("authorize", f"Sign in to: {', '.join(needs_auth)}. Run --authorize "
                             "(a browser window opens per account).")
    else:
        step = ("ready", "Setup is complete. Launch Smithers.")
    return {
        "home": str(HOME_DIR),
        "home_exists": HOME_DIR.is_dir(),
        "config_file": str(CONFIG_FILE),
        "accounts": accts,
        "credentials_file": str(CREDS_FILE),
        "have_credentials": have_creds,
        "tokens": tokens,
        "needs_authorization": needs_auth,
        "ready": bool(accts) and have_creds and not needs_auth,
        "next_step": step[0],
        "next_step_help": step[1],
    }


def add_account(label: str, email: str) -> dict:
    label = label.strip().lower().replace(" ", "_")
    if not label or not email.strip():
        raise SystemExit("Both a label and an email address are required.")
    cfg = _load_config()
    cfg.setdefault("accounts", {})[label] = email.strip()
    _save_config(cfg)
    return status()


def remove_account(label: str) -> dict:
    cfg = _load_config()
    cfg.get("accounts", {}).pop(label, None)
    _save_config(cfg)
    token = HOME_DIR / f"token_{label}.pickle"
    if token.exists():
        token.unlink()
    return status()


def authorize(label: str | None) -> dict:
    from google_auth_oauthlib.flow import InstalledAppFlow

    accts = _accounts()
    if not accts:
        raise SystemExit("No accounts recorded. Run --add-account first.")
    if not CREDS_FILE.exists():
        raise SystemExit(CREDS_HELP)
    targets = [label] if label else [
        a for a in accts if not (HOME_DIR / f"token_{a}.pickle").exists()]
    if label and label not in accts:
        raise SystemExit(f"Unknown account '{label}'. Known: {', '.join(accts)}")
    for acct in targets:
        print(f"\nAuthorizing '{acct}' ({accts[acct]}).")
        print("A browser window will open — sign in with THAT account.")
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
        creds = flow.run_local_server(port=0)
        token_file = HOME_DIR / f"token_{acct}.pickle"
        with open(token_file, "wb") as f:
            pickle.dump(creds, f)
        token_file.chmod(0o600)
        print(f"  Saved {token_file}")
    return status()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--add-account", nargs=2, metavar=("LABEL", "EMAIL"))
    ap.add_argument("--remove-account", metavar="LABEL")
    ap.add_argument("--authorize", nargs="?", const="", metavar="LABEL")
    args = ap.parse_args()

    HOME_DIR.mkdir(parents=True, exist_ok=True)
    if args.add_account:
        out = add_account(*args.add_account)
    elif args.remove_account:
        out = remove_account(args.remove_account)
    elif args.authorize is not None:
        out = authorize(args.authorize or None)
    else:
        out = status()
    json.dump(out, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
