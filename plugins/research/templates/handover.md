---
description: Checkpoint the durable record and hand off to a fresh context window — write state, then you run /clear and resume with nothing lost.
argument-hint: ""
---

Your context window is getting long; hand off. You CANNOT clear your own
context — this command runs inside the current session — so do the half you can
(write the durable record cleanly), then hand off to the human to run `/clear`.
On resume, `CLAUDE.md` and the state files bring the next session up to speed.

Read `CLAUDE.md` if you have not already. Everything below assumes it.

Nothing here blocks a collaborator. There is no lock to release and no round to
close — the state is a directory of small files precisely so that everyone can
write at once (see `tools/state.py`).

## 1. Check whether the record has fallen behind

```bash
python3 -m tools.chronology --gap --human
```

That lists commits with no state entry dated at or after them — work whose
reason was never written down, usually from a session that ended without anyone
saying so. Walk it. Write the entry now, while you can still reconstruct why;
name the ones you cannot, so the gap is known rather than invisible.

Never invent a reason. A wrong entry is worse than a missing one, because it
will be believed.

## 2. Write an entry for what this session took up

```bash
python3 -m tools.state new "what this session took up"
```

That creates `project/global/state/entries/<date>-<author>-<slug>.md` with its
front matter filled in. Write into it: what was taken up, then what came of it
and why.

**Write one even when nothing settled.** That is not a formality. "We took up X
and dropped it, because Y" is the answer to *did we ever explore X*, and it is
the only place that answer exists — work that changed nothing leaves no diff, no
promoted file and no trace anybody can find later. An attempt that failed is a
result, and it is the easiest one to lose.

## 3. Promote what has actually settled

- Into `project/global/state/core.md` — confirmed thesis changes, newly settled
  facts, killed ideas WITH the reason, replicated results. This is the one
  shared file; keep it short and rewrite it freely.
- Into `project/global/state/blocks/` (`python3 -m tools.state new --block "…"`)
  — a decision recorded, a status frozen, a program written down. Append; never
  rewrite someone else's block.

Only promote what is ACTUALLY settled. Do not launder an in-flight guess into
truth: the value of the state is that a claim in it has been through the gate.
Anything still in flight belongs in `session.md`, not the state.

## 4. Rewrite your handoff, compact

Rewrite `project/<author>/session.md` so a cold-start session could resume from
it alone:

- **Where we are** — one paragraph of status.
- **In flight** — work started but unfinished: which seat or subagent, what state
  it is in, what it was waiting on.
- **Next actions** — immediate steps, most important first.
- **Open threads** — active but unsettled questions.
- **Last session** — today's date and the run id.

Drop anything you promoted in step 3 — it lives in the state now. Keep this
SHORT. A long handoff defeats the purpose; it is a pointer, not a transcript.

## 5. Freshen the subagent memories if they ran

If a subagent did work this session, make sure its memory file under
`project/<author>/` reflects it. They normally self-update on return, but an
interrupted run leaves them stale — capture what is known so the next fresh
spawn resumes correctly rather than redoing work.

Rewrite these compactly. A file that accumulates superseded blocks under a
"this is all stale now" banner is worse than useless: it reads as current.

## 6. Commit, then hand off

Commit the entry with the session's work, so the two land together. Then tell
the user plainly:

> Checkpointed. Run `/clear` (or start a new session), then say `resume`.
> I will re-read `CLAUDE.md`, the state, and my `session.md` and continue with a
> fresh context window — nothing is lost.

Do NOT try to clear context yourself, and do not keep working after this. Stop,
so the human can `/clear`.
