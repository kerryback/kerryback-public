"""Central configuration.

The ElevenLabs key a user pastes in the app is stored in ~/.voiceover/.env, NOT
inside the skill directory. The skill directory is package content: installing or
updating the plugin replaces it, and a key kept there would silently vanish on
every update — leaving the person who used the paste-in-app path (rather than
exporting a shell variable) staring at the key banner again with no explanation.
Everything else durable already lives in ~/.voiceover for the same reason.

Resolution order, strongest first: a real environment variable, then
~/.voiceover/.env, then a legacy backend/.env — which is still read so an
existing install keeps working, and whose key is migrated out on first run.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Durable, user-owned state. Mirrors skill_launch.py's VOICEOVER_HOME.
HOME_DIR = Path(os.environ.get("VOICEOVER_HOME", Path.home() / ".voiceover"))
ENV_FILE = HOME_DIR / ".env"
LEGACY_ENV_FILE = BACKEND_DIR / ".env"


def _read_env_file(path: Path) -> dict:
    values = {}
    if not path.exists():
        return values
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            values[name.strip()] = value.strip()
    except OSError:
        pass
    return values


def _migrate_legacy_key() -> None:
    """Move a key left in the skill directory by an older version into the home
    file, once. The old file is left alone: the skill directory may be read-only,
    and a stale copy is harmless now that the home file is read first."""
    if _read_env_file(ENV_FILE).get("ELEVENLABS_API_KEY"):
        return
    legacy = _read_env_file(LEGACY_ENV_FILE).get("ELEVENLABS_API_KEY")
    if legacy:
        _upsert_env("ELEVENLABS_API_KEY", legacy)


# load_dotenv never overwrites an existing environment variable, so loading the
# home file first gives it precedence over the legacy one.
HOME_DIR.mkdir(parents=True, exist_ok=True)
load_dotenv(ENV_FILE)
load_dotenv(LEGACY_ENV_FILE)

# DATA_DIR is the app's home (the launcher points it at ~/.voiceover). Each deck
# lives in its own folder under DATA_DIR/decks, named after the deck, so relaunching
# the same deck reopens it with its narration and video intact.
DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
if not DATA_DIR.is_absolute():
    DATA_DIR = (BACKEND_DIR / DATA_DIR).resolve()
PROJECTS_DIR = DATA_DIR / "decks"

# Narration is written and revised by the Claude Code agent that launches this
# skill (it edits via the narration API), so the app itself makes no LLM calls
# and needs no Anthropic key. Only ElevenLabs (TTS) is required.
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")

# When set (by the skill launcher = the author's working directory), each
# finished build copies <name>.mp4 and <name>.txt there.
OUTPUT_DIR = os.environ.get("VOICEOVER_OUTPUT_DIR", "")

# Parallel ElevenLabs TTS requests during a build. ElevenLabs caps concurrent
# requests per account tier -- Free allows 2, and the cap climbs with the plan.
# Exceeding it returns 429 and, because a failed clip aborts the whole build,
# loses the run. So the default is the value every tier can serve, and the
# author raises it on the Voice screen once they know their plan. An
# exported TTS_CONCURRENCY still wins, since load_dotenv never overwrites a real
# environment variable.
TTS_CONCURRENCY = int(os.environ.get("TTS_CONCURRENCY", "2"))
# Parallel ffmpeg slide-segment encodes during video render (CPU-bound).
VIDEO_CONCURRENCY = int(os.environ.get("VIDEO_CONCURRENCY", "4"))

# React SPA build output (optional; served at / when present).
FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"

DATA_DIR.mkdir(parents=True, exist_ok=True)
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


def project_dir(project_id: str) -> Path:
    return PROJECTS_DIR / project_id


def _upsert_env(name: str, value: str) -> None:
    """Set (or replace) `name=value` in ~/.voiceover/.env, preserving other lines."""
    line = f"{name}={value}"
    lines = []
    found = False
    if ENV_FILE.exists():
        for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
            stripped = raw.lstrip()
            if stripped.startswith(f"{name}=") or stripped.startswith(f"{name} ="):
                lines.append(line)
                found = True
            else:
                lines.append(raw)
    if not found:
        lines.append(line)
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def set_tts_concurrency(n: int) -> None:
    """Persist the TTS concurrency to ~/.voiceover/.env and update the live value.

    Account-wide, like the key, and deliberately NOT part of a deck's config:
    build_signature covers the deck's audio settings, so putting it there would
    make changing it re-synthesize every clip. It only governs how fast requests
    are issued, never how they sound, so cached audio stays valid.
    """
    global TTS_CONCURRENCY
    n = max(1, min(int(n), 15))
    TTS_CONCURRENCY = n
    os.environ["TTS_CONCURRENCY"] = str(n)
    _upsert_env("TTS_CONCURRENCY", str(n))


def set_elevenlabs_key(key: str) -> None:
    """Persist the ElevenLabs key to ~/.voiceover/.env and update the live value,
    so a key pasted in the app takes effect immediately with no server restart —
    and survives a skill update, which replaces the skill directory."""
    global ELEVENLABS_API_KEY
    key = (key or "").strip()
    ELEVENLABS_API_KEY = key
    os.environ["ELEVENLABS_API_KEY"] = key
    _upsert_env("ELEVENLABS_API_KEY", key)


# Runs last: the migration writes through _upsert_env, defined above. A key found
# only in the old location is copied to the home file and loaded live, so an
# upgrade from 1.x doesn't send the user back to the key banner.
_migrate_legacy_key()
if not ELEVENLABS_API_KEY:
    ELEVENLABS_API_KEY = _read_env_file(ENV_FILE).get("ELEVENLABS_API_KEY", "")
    if ELEVENLABS_API_KEY:
        os.environ["ELEVENLABS_API_KEY"] = ELEVENLABS_API_KEY
