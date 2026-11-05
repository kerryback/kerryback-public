"""The fixed module intros and learning objectives, from content/module-intros.md.

Each module there has a "## Module N — Title" heading and three parts:
"Spoken:" (a paragraph read aloud), "Board:" (list items for the intro page)
and "Objectives:" (list items).  The app plays an intro the same way every
time; the tutor never writes one.
"""

import re

import tutor_config as cfg

FILE = cfg.CONTENT / "module-intros.md"


def load(path=FILE):
    """{n: {"n", "title", "spoken", "board": [...], "objectives": [...]}}."""
    modules = {}
    for block in re.split(r"^## ", path.read_text(), flags=re.M)[1:]:
        head, _, body = block.partition("\n")
        m = re.match(r"Module\s+(\d+)\s*[—–-]\s*(.+)", head)
        if not m:
            continue
        parts = dict(re.findall(r"^(Spoken|Board|Objectives):\n(.*?)(?=^\w+:\n|\Z)", body, re.M | re.S))
        items = lambda s: [ln[2:].strip() for ln in s.splitlines() if ln.startswith("- ")]
        n = int(m.group(1))
        modules[n] = {"n": n, "title": m.group(2).strip(),
                      "spoken": " ".join(parts.get("Spoken", "").split()),
                      "board": items(parts.get("Board", "")),
                      "objectives": items(parts.get("Objectives", ""))}
    return modules


MODULES = load()


def load_course(path=FILE):
    """The course Introduction: {"spoken", "board": [...]}, or None."""
    m = re.search(r"^## Introduction\n(.*?)(?=^## |\Z)", path.read_text(), re.M | re.S)
    if not m:
        return None
    parts = dict(re.findall(r"^(Spoken|Board):\n(.*?)(?=^\w+:\n|\Z)", m.group(1), re.M | re.S))
    return {"spoken": " ".join(parts.get("Spoken", "").split()),
            "board": [ln[2:].strip() for ln in parts.get("Board", "").splitlines() if ln.startswith("- ")]}


COURSE = load_course()


# Every tutor's Introduction ends with these, spoken (engine/intro_notes.py).
from intro_notes import ARITHMETIC_NOTE, MIC_NOTE  # noqa: E402,F401


def course_markdown():
    """The Introduction as a tutor reply: its own section, the spoken paragraph
    (ending with ARITHMETIC_NOTE and MIC_NOTE), the board."""
    spoken = " ".join([COURSE["spoken"], ARITHMETIC_NOTE, MIC_NOTE])
    lines = ["## Introduction", "", spoken, ""] + [f"- {b}" for b in COURSE["board"]]
    return "\n".join(lines) + "\n"


COURSE_NOTE = ("The app has just shown and spoken the course Introduction: the modules, "
               "the length of the course, how to answer, type, pause and use the module menu, "
               "and that the student never needs to do arithmetic. "
               "Do not repeat any of it: do not welcome the student and do not mention how long "
               "the course takes. This overrides the protocol's instructions for the opening. "
               "Just ask your two opening questions, in a new section.")


def markdown(n):
    """The intro as a tutor reply: a section heading, the spoken paragraph, and
    the board.  On the whiteboard the paragraph is spoken and the rest shown;
    in the text version all of it is shown."""
    mod = MODULES[n]
    lines = [f"## Module {n}: {mod['title']}", "", mod["spoken"], ""]
    lines += [f"- {b}" for b in mod["board"]]
    lines += ["", "### What you will learn", ""]
    lines += [f"- {o}" for o in mod["objectives"]]
    return "\n".join(lines) + "\n"


def objective_ids(n):
    return [(f"{n}.{k}", o) for k, o in enumerate(MODULES[n]["objectives"], 1)]


def note(n):
    """What the tutor is told after the app plays an intro."""
    mod = MODULES[n]
    objs = "\n".join(f"{i} {o}" for i, o in objective_ids(n))
    return (f"The app has just shown and spoken the intro to Module {n} ({mod['title']}). "
            f"Do not give an overview of the module yourself. Begin teaching Module {n} now. "
            f"Its objectives:\n{objs}")


def prompt_text():
    """The objectives of every module, with ids, for the system prompt."""
    out = ["<reference file=\"module-objectives\">",
           "Learning objectives by module. Record the ones a student has met with "
           "save_progress (objectives_met), by id."]
    for n in sorted(MODULES):
        out.append(f"\nModule {n} — {MODULES[n]['title']}")
        out += [f"{i} {o}" for i, o in objective_ids(n)]
    out.append("</reference>")
    return "\n".join(out)
