## Writing

`writing-guide.md` in the repo root is the standard for everything that goes
into `draft/` — the paper, the abstract, the slides, the referee response, the
cover letter, the grant proposal. **Read it before you write, not after.** Prose
composed flat and sanded down later never fully recovers.

It is binding, and it applies to drafting fresh as much as to revising. It does
not apply to the state files, `session.md`, commit messages, or notes between
coauthors — only to what an editor, a referee, or a reader will see.

The guide is vendored, so it works for a coauthor who has installed nothing.
Do not substitute your own writing habits for it, and do not skip it because a
passage is short.

For a full referee-grade pass when a draft is close to circulating, use the
`econ-review` skill if it is installed. That is a separate, heavier step —
`writing-guide.md` governs the prose either way.

### The guide learns

`writing-guide.md` is the only writing standard this project has. Never start a
second file of conventions beside it, and never put a prose rule anywhere else —
not in `CLAUDE.md`, not in a section of the state. A rule about writing goes
into the guide, in the section it bears on. Two places to look means neither is
definitive.

It grows from this project's own editing. When the author tells you to change
how a passage reads, or rewrites your prose themselves, `tools/style_capture.py`
records the passage and the instruction to a local buffer. `/style-learn`
reviews that backlog, proposes rules, and writes the accepted ones into the
guide with a `<!-- learned: ... -->` marker.

The guide is too long to put in context whole — it is a manual you consult for
the task in front of you. So a hook extracts the marked lines and puts those in
context at the start of every session. You have therefore already read this
project's own rules; the rest of the guide you read before writing, as it says.
That excerpt is generated, never edited: fix a rule in the guide, not in the
extract.

Two things about it that are load-bearing:

- **Suggest `/style-learn` when the backlog is worth curating** — after a
  session with several prose corrections, or before a drafting push where the
  rules would pay off. `python3 tools/style.py stats` says how much is waiting.
  Do not run it unprompted; it ends in the author accepting rules one by one.
- **The buffer is private, the guide is shared.** Captures live in
  `project/<author>/logs/` and are gitignored. Only a rule someone accepted
  reaches the committed guide. Coauthors do not have identical taste, and this
  is what lets one standard hold anyway — a rule becomes the project's when a
  person says it should, not when someone was corrected once.

Do not add a marked rule to the guide as a side effect of anything else. It
happens through `/style-learn`, or by the author's own hand.

---
