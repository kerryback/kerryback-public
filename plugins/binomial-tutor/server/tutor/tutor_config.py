"""Which tutor this plugin serves: the plugin's stand-in for engine/tutor_config.py.

scripts/build_plugin.py writes tutor.json from the tutor's tutor.toml (so
Python 3.9, which has no tomllib, can read it) and copies the tutor's
topic.py, its modules and content/module-intros.md beside this file.
"""

import json
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent
CONTENT = DIR / "content"

CONFIG = json.loads((DIR / "tutor.json").read_text())
NAME = CONFIG["name"]
TITLE = CONFIG["title"]
SUBTITLE = CONFIG.get("subtitle", TITLE)
WHISPER_PROMPT = CONFIG.get("whisper_prompt", "")
REFERENCES = CONFIG.get("references", [])

sys.path.insert(0, str(DIR))
import topic  # noqa: E402  the tutor's own tools: TOOLS, run, PLOTS, PLOT_PARAMS, make_plot
