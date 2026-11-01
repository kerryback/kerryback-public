---
name: research
description: Set up a research repository that several people and their Claudes can work in without tripping over each other — per-author folders, portable paths, a single canonical dataset, provenance, a state directory several people can write to at once with no locking, a vendored writing guide, and a generated CLAUDE.md. Use when starting a new empirical or theoretical research project, when a solo project is about to gain coauthors, or when an existing project's files have grown organically and need structure. Also use when asked to "set up a research project", "add coauthors to this project". Covers wiring a paper directory to an Overleaf project through its git bridge, for teams where only some coauthors use Overleaf.
---

You are setting up a research repository. The output is a working structure plus
a `CLAUDE.md` that makes it self-explaining, so the next session — anyone's —
knows the rules without being told.

Do not scaffold first and ask later. Interview, then build, then verify, then
explain what you did.

## What this is for

Research projects rot in predictable ways. Paths hardcode one person's home
directory. The dataset everyone depends on lives in whoever happened to build
it's folder. Two people rewrite the same prose file and git cannot merge it.
Nobody can say which script produced a number, or what breaks if a script
changes. This scaffolds the structure that prevents each of those.

It also settles what the project remembers. Two committed records carry it, and
the generated `CLAUDE.md` names both so the next session knows where to write:

- `project/global/state/` — a DIRECTORY, one file per entry, so several people
  can write at once without git having to merge anything. One entry per stretch
  of work saying what it took up and what came of it, written even when nothing
  settled, plus any substantive change as it happens. Killed ideas go into
  `core.md` with why. This is what makes "did we ever explore X" answerable:
  work that chased something and dropped it leaves no diff and no artifact,
  only its entry.
- `project/<author>/logs/runs.jsonl` — one line per script execution, tying a
  number to the run that produced it.

Debate briefs and full model responses stay local and gitignored. They are the
input to a decision, not the decision, and a coauthor asking "did we ever
explore X" wants the answer, not the prompts that produced it.

There is deliberately no session-wide activity log. Recording every prompt and
tool call reaches tens of megabytes a project, will not go in git, and answers
none of the questions coauthors actually ask — "what did they do last week",
"why did we change that", "did we ever explore X" are questions about decisions,
and only a written decision answers them. Bulk capture is not memory; a
changelog line is.

## 1. Interview

Ask these before touching the filesystem. Use `AskUserQuestion` where the options
are closed; ask in prose where they are not.

1. **Project name.** Becomes the folder name, the env var prefix, and the title
   of the generated docs. Derive a slug (lowercase, hyphens) and an ENV PREFIX
   (uppercase, underscores) and show both back. `Housing Supply` →
   `housing-supply`, `HOUSING_SUPPLY_DATA`.
2. **One line on what the project is.** Goes at the top of `CLAUDE.md` and
   `protocols.html`. Not a paragraph.
3. **Who is working on it?** Full names. Their slugs come from
   `git config user.name` on their own machines, so tell them what slug each name
   will produce and confirm it now — it is the single most common thing to get
   wrong, and it fails silently.
4. **Is there an empirical component?** If yes, scaffold `analyst/` and
   `replicator/` and include the two-build protocol. If it is theory or a
   literature project, skip both — a theory paper with two empty directories and
   a protocol that does not apply to it is worse than neither.
5. **Where does the data live?** A path outside the repo — a shared Dropbox or
   Box folder, a group drive. Data is not committed. If there is no data at all,
   say so and skip the data sections entirely.
6. **A debate panel?** Independent model voices that propose and attack ideas,
   through OpenRouter. Explain the cost honestly: each coauthor needs their own
   key and pays for their own calls. Default to no unless they want it.
7. **Does anyone write in Overleaf?** Only worth asking if there is a paper. If
   yes, `draft/` gets mirrored to an Overleaf project through its git bridge and
   the rest of the repo stays out of it; coauthors who do not use Overleaf are
   unaffected. Read `references/overleaf.md` before wiring it — the bootstrap is
   not what you would guess, because Overleaf prohibits force pushes and
   `git subtree add` refuses a prefix that already exists. Default to no; it is
   easy to add later, and easier before anyone has started commenting.
8. **Existing files?** If the repo already has work in it, ask what is live and
   what is superseded. Do not move anything until they have answered.

## 2. Build

Create only what the interview asked for.

```
project/global/state/{core.md,entries/,blocks/}
project/global/{method_spec.md,data_manifest.md}
project/<author>/{session.md,logs/}
workspaces/global/params.py            (empirical only)
workspaces/<author>/{analyst,replicator}/   (empirical only)
draft/{figures,tables}/
tools/                                 copied from this plugin
.claude/commands/{handover.md,report.md,style-learn.md}
.claude/settings.json                  the style-capture hooks
CLAUDE.md  protocols.html  requirements.txt  .gitignore
writing-guide.md                       copied from templates/, then grows
```

`/report` builds an HTML report — executive summary, what is settled, open
issues, chronology — from the committed records, using `tools/chronology.py` to
merge the state entries, git log, and run records into one timeline. It
needs no accumulation step: the entries are the incremental artifact and
`/handover` keeps them current.

Write `protocols.html` LAST, after the repo is built and verified, following
`templates/protocols.md` — that file is the spec, not the content, so write the
page for this project rather than copying it. It is the human counterpart to
`CLAUDE.md` and the one document a coauthor actually reads; that everyone works
at once has to be said there explicitly, because a newcomer who has used a
locked repository before will go looking for the lock, and
it governs when they may touch shared state.

Copy `templates/writing-guide.md` to the repo root, on every project. It is the
standard for everything that goes into `draft/`, and it is vendored so a
coauthor who has installed nothing still gets it. There is no project without
writing, so this one is not conditional on any interview answer.

It is copied unchanged but it does not stay that way: it is the project's single
writing standard, and `/style-learn` writes rules into it as the project's own
editing produces them. Copy `templates/style-learn.md` to `.claude/commands/`
for the same reason, unconditionally.

Do not create a second file of writing conventions, and do not put prose rules
in the generated `CLAUDE.md`. One standard, in the guide, in the section each
rule bears on. Two homes for style rules is the failure this is arranged to
avoid — it is how a project ends up with two rules that disagree and no way to
say which is live.

Then install the style-capture hooks in `.claude/settings.json`, creating the
file if it does not exist and merging into the `hooks` key if it does:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {"hooks": [{"type": "command",
        "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/style_capture.py\""}]}
    ],
    "PostToolUse": [
      {"matcher": "Edit|MultiEdit", "hooks": [{"type": "command",
        "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/style_capture.py\""}]}
    ],
    "SessionStart": [
      {"hooks": [{"type": "command",
        "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/style_capture.py\""}]}
    ]
  }
}
```

Do not install a session-wide activity-logging hook, and do not offer to. An
exhaustive record of every prompt and every tool call reaches tens of megabytes
a project, cannot go in git, and answers none of the questions coauthors ask —
those are about decisions, and the state entries are what record decisions. `templates/project-gitignore` commits the run records for exactly
this reason; the briefs and the bulky debate responses stay local.

The style hooks above are not that, and the difference is worth being precise
about, because the next session will read the paragraph above and reach for the
delete key. They fire on one tool, filtered to prose files in `draft/`; what
they write is a staging buffer that stays local and gitignored; and the artifact
that survives is a capped rule file a human accepted line by line. Bulk capture
is not memory — but a correction the author had to give twice is not bulk, and
losing it is why they have to give it a third time. If a project has no `draft/`
at all, skip the hooks; otherwise install them.

Assemble `CLAUDE.md` from `templates/CLAUDE.md.tmpl`, substituting:

| Placeholder | With |
|---|---|
| `@@PROJECT@@` | the project name |
| `@@ONE_LINE@@` | their one-line description |
| `@@DATA_ENV@@` | `<PREFIX>_DATA` |
| `@@DATA_LOCATION@@` | the shared data location from question 5, written out plainly — e.g. `~/Dropbox/housing-supply-data/`. Name the service (Dropbox, Box, a group drive) so a new coauthor knows what they are looking for, not just a path that exists on one machine. If there is no data at all, drop the whole block. |
| `@@PREFIX@@` | the env prefix |
| `@@EMPIRICAL_SECTIONS@@` | `templates/fragments/empirical.md`, or empty |
| `@@DEBATE_SECTION@@` | `templates/fragments/debate.md`, or empty |
| `@@WRITING_SECTION@@` | `templates/fragments/writing.md` — always, never empty |
| `@@OVERLEAF_SECTION@@` | `templates/fragments/overleaf.md`, or empty |
| `@@OVERLEAF_PROJECT@@` | the Overleaf project id, once the bridge is wired |
| `@@ROLES@@`, `@@AUTHOR_MEMORY@@`, `@@WORKSPACE_TREE@@`, `@@INDEPENDENCE_NOTE@@`, `@@ONBOARD_EXTRA@@` | see the fragments; write the empirical or the plain variant |

Substitute the same `@@DATA_ENV@@` into the copied `tools/*.py`. Leave no `@@`
marker anywhere — grep for them before you finish.

Then, in the repo:

- `git init` if needed, and `git config core.hooksPath tools/githooks`.
- Create the venv and install `requirements.txt`.
- Add the data root and any keys to the user's shell profile — **ask first**, and
  back the file up before you edit it.
- Make the author's data folder and the `global/` sibling.
- If they want Overleaf, wire it last, after the repo is otherwise settled, and
  follow `references/overleaf.md` rather than improvising. Do the file hygiene it
  lists — naming the paper `main.tex`, untracking build noise, moving heavy
  non-source material out of `draft/` — BEFORE the first push, because renames
  destroy Overleaf comment anchors and every one of those decisions is cheaper
  than it will ever be again. Have the user authenticate themselves; never ask
  for their token.

## 3. Verify — do not skip this

A scaffold that has not been exercised is a guess. Before you report success:

```bash
python3 tools/onboard.py                      # must print ready
python3 -m tools.provenance --authors         # must list the author trees
python3 -m tools.state check                  # must parse the seeded state
grep -rn "@@" CLAUDE.md tools/ protocols.html  # must find nothing
test -s writing-guide.md                       # must exist and be non-empty
ls .claude/commands/{handover,report,style-learn}.md   # all three
```

Then exercise the style hooks, because a hook that fails is silent by design —
`style_capture.py` swallows every exception rather than breaking the tool loop,
so "no error" tells you nothing:

```bash
echo '{"hook_event_name":"SessionStart"}' | python3 tools/style_capture.py
# prints nothing on a fresh project — correct, there are no learned rules yet.
# Add a marked line to writing-guide.md by hand and re-run: it must appear.

printf '{"hook_event_name":"UserPromptSubmit","prompt_id":"t1","user_input":"stop hedging"}' \
  | python3 tools/style_capture.py
printf '{"hook_event_name":"PostToolUse","prompt_id":"t1","tool_name":"Edit","tool_input":
  {"file_path":"draft/main.tex","old_string":"The effect is arguably somewhat large.",
   "new_string":"The effect is large."}}' | tr -d '\n' | python3 tools/style_capture.py
python3 tools/style.py pending    # must show that one observation, with "stop hedging"
python3 tools/style.py accept     # clear the test out of the backlog
```

If `pending` is empty, the usual cause is the path filter: `is_prose()` requires
the file to be under `draft/`, so a project whose paper lives somewhere else
needs `PROSE_DIRS` in `style_capture.py` changed to match.

If there is data and any script, run one through `tools/runlog.py` and confirm a
line lands in `runs.jsonl`.

Then confirm the gitignore rules do what they claim, because a negation under an
ignored directory is easy to get subtly wrong and fails silently:

```bash
A=$(python3 -m tools.runid --author)
touch project/$A/logs/runs.jsonl
git check-ignore -v project/*/logs/runs.jsonl        # must find NOTHING (exit 1)
git check-ignore    project/*/logs/brief-x-0.md      # must match — stays local
git check-ignore    project/*/logs/debate-x.jsonl    # must match — stays local
```

If `runs.jsonl` comes back ignored, the rule shape is wrong: git cannot
re-include a file whose parent directory is ignored, so it must be `*/logs/*`
plus the negation, never `*/logs/`. If a brief comes back un-ignored, the
negation is too broad — briefs are working material and do not belong in git.

Then confirm the timeline assembler runs against the repo as it actually is —
it parses four sources and a wrong path fails quietly as an empty list:

```bash
python3 -m tools.chronology --human | head       # must show the setup commits
```

If Overleaf is wired, `git fetch overleaf` and list the remote tree — it must be
the draft and nothing else — and test the pull direction, not only the push. A
bridge that has only ever been pushed to is half verified.

If a check fails, fix it and say what was wrong — never report a setup as working
on the strength of having written the files.

## 4. Explain, briefly

Two minutes, in your own words: where their folders are, what is shared and what
is theirs, that `protocols.html` covers day-to-day use, and the one rule that
bites — their `git config user.name` names everything they own.

Do not read the generated `CLAUDE.md` at them. It is for you.

## Adapting an existing project

The same structure, applied to a repo that already has work, in this order:

1. **Paths first.** Find hardcoded absolute paths (`grep -rn "/Users/\|/home/"`).
   Rewrite them to the four roots. This is mechanical but it is where the risk
   is: verify by re-running something whose answer is already known, not by
   reading the diff.
2. **Then data out of the repo**, into the data root, with the canonical
   subset promoted to `global/`.
3. **Then the per-author split**, moving existing work into one author's tree.
4. **Then archive**: superseded subprojects into `archive/`, so what is live is
   legible. Ask which are which; do not infer it from timestamps, which a
   mechanical rewrite will have destroyed.

Commit between steps, not at the end. If step 1 breaks something, you want to
find it before three more moves are stacked on top.
