"""Configuration and cross-platform paths.

Phase 1 needs almost no configuration; sensible defaults let the tool run with
zero setup. A ``config.toml`` (searched in the data dir, then the LITDB_CONFIG
path) can override the database location and, in later phases, the embedding
provider. Everything here is standard library so the core has no dependencies.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

try:  # Python 3.11+
    import tomllib  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for 3.10
    tomllib = None  # type: ignore


APP_NAME = "litdb"


def data_dir() -> Path:
    """Return litdb's per-user home directory.

    Everything litdb owns lives here: the managed virtualenv (``.venv``), the
    database, ``preferences.json``, and the ``.onboarded`` marker. A single fixed
    home (``~/.litdb``) means the runtime does not depend on any project/repo
    folder that a user might delete. Override with LITDB_HOME (used by tests).
    Cross-platform: ``~/.litdb`` works on macOS, Linux, and Windows alike.
    """
    override = os.environ.get("LITDB_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".litdb"


def db_path() -> Path:
    override = os.environ.get("LITDB_DB")
    if override:
        return Path(override).expanduser()
    return data_dir() / "litdb.db"


_DEFAULTS: dict = {
    "embedding": {
        "provider": "ollama",          # ollama | fastembed | voyage | openai
        "model": "nomic-embed-text",
        "dim": 768,
    },
    "policy": {
        "confidential_stay_local": True,
        "local_provider": "ollama:nomic-embed-text",
    },
    "zotero": {
        # Zotero local API (Zotero 7+); used with --local when BBT is absent.
        "local_api": "http://localhost:23119/api/users/0/items",
        # Better BibTeX JSON-RPC; preferred automatically when reachable (adds
        # citation keys). Requires Zotero running with the Better BibTeX add-on.
        "bbt_rpc": "http://localhost:23119/better-bibtex/json-rpc",
        # Zotero connector server base (the endpoint the browser connector uses);
        # `push-zotero` POSTs items to <connector>/connector/saveItems.
        "connector": "http://localhost:23119",
    },
    "external": {
        # OpenAlex asks for an email in the "polite pool"; recommended, optional.
        "openalex_mailto": "",
        # Semantic Scholar works without a key; a key raises rate limits.
        "s2_api_key_env": "S2_API_KEY",
        "default_source": "openalex",   # openalex | s2
        "timeout": 20,
    },
}


def _config_file() -> Path | None:
    override = os.environ.get("LITDB_CONFIG")
    if override and Path(override).expanduser().is_file():
        return Path(override).expanduser()
    candidate = data_dir() / "config.toml"
    return candidate if candidate.is_file() else None


def load_config() -> dict:
    """Return defaults deep-merged with any user config.toml, plus preferences.

    config.toml holds technical settings the app needs to run (embedding
    provider, endpoints). Preferences hold the user's behavioral/workflow choices
    (uses_tex, use_better_bibtex, …) and are managed by `litdb prefs`, never
    hand-edited. Both are surfaced here so callers read one config object;
    ``cfg["preferences"]`` is the behavioral layer.
    """
    cfg = {k: dict(v) for k, v in _DEFAULTS.items()}
    path = _config_file()
    if path and tomllib is not None:
        with path.open("rb") as fh:
            user = tomllib.load(fh)
        for section, values in user.items():
            if isinstance(values, dict):
                cfg.setdefault(section, {}).update(values)
            else:
                cfg[section] = values
    cfg["preferences"] = load_prefs()
    return cfg


# --------------------------------------------------------------------------- #
# preferences (per-user behavioral settings) and the onboarding marker
# --------------------------------------------------------------------------- #

def prefs_path() -> Path:
    return data_dir() / "preferences.json"


def load_prefs() -> dict:
    p = prefs_path()
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return {}
    return {}


def save_prefs(prefs: dict) -> None:
    p = prefs_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(prefs, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def get_pref(key: str, default=None):
    return load_prefs().get(key, default)


def set_pref(key: str, value) -> dict:
    prefs = load_prefs()
    prefs[key] = value
    save_prefs(prefs)
    return prefs


# --------------------------------------------------------------------------- #
# Semantic Scholar API key
#
# The key is resolved from (1) the configured environment variable
# (``s2_api_key_env``, default ``S2_API_KEY``) so power users can inject it,
# then (2) a litdb-owned file in the home. The file makes storage independent
# of shell-profile inheritance, so the key set during onboarding is picked up by
# every ``litdb`` subprocess without the user editing ``~/.zshrc``. It is a
# local plaintext secret (0600), on the same footing as the local DB and PDFs.
# --------------------------------------------------------------------------- #

def s2_key_path() -> Path:
    return data_dir() / "s2_api_key"


def _s2_env_name() -> str:
    return load_config()["external"].get("s2_api_key_env", "S2_API_KEY")


def get_s2_api_key() -> str | None:
    val = os.environ.get(_s2_env_name())
    if val and val.strip():
        return val.strip()
    p = s2_key_path()
    if p.is_file():
        try:
            txt = p.read_text(encoding="utf-8").strip()
            if txt:
                return txt
        except OSError:
            pass
    return None


def s2_api_key_source() -> str | None:
    """Where the active key comes from: 'env', 'file', or None."""
    val = os.environ.get(_s2_env_name())
    if val and val.strip():
        return "env"
    p = s2_key_path()
    if p.is_file() and p.read_text(encoding="utf-8").strip():
        return "file"
    return None


def has_s2_api_key() -> bool:
    return get_s2_api_key() is not None


def set_s2_api_key(key: str) -> Path:
    p = s2_key_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(key.strip() + "\n", encoding="utf-8")
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return p


def clear_s2_api_key() -> bool:
    p = s2_key_path()
    if p.is_file():
        p.unlink()
        return True
    return False


def onboarded_marker() -> Path:
    return data_dir() / ".onboarded"


def is_onboarded() -> bool:
    return onboarded_marker().exists()


def mark_onboarded() -> None:
    p = onboarded_marker()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("", encoding="utf-8")


def reset_onboarded() -> bool:
    p = onboarded_marker()
    if p.exists():
        p.unlink()
        return True
    return False
