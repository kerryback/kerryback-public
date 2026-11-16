---
name: edit
description: Use when the user wants to change a voice whiteboard tutor that already exists in ~/repos/tutors — play it and give notes ("open the capm tutor so I can edit it", "preview the binomial tutor", "add an analogy to module 2", "make the tutor explain more slowly"), or change, test, evaluate, review or redeploy it. To build a new tutor, use the create skill instead.
---

# Editing a tutor

The teacher plays their tutor on their own computer, as a student would, and
gives notes as they go: an analogy to add, an example to change, how
explanations should be given. You apply each note to the tutor's files. The
tutor uses the change from its next reply, so the teacher hears it at once.

Every tutor lives in ~/repos/tutors and runs the same engine. The teacher
decides the content; you do the editing.

## The preview loop

1. Name the tutor. If the user did not, list the folders with a `tutor.toml`
   and ask which one. Run `scripts/test.sh <tutor>`, so you know the state
   before you change anything.
2. Start the preview in the background: `scripts/preview.sh <tutor>`. It runs
   the tutor at http://localhost:8010 and opens it in the browser. Only the
   preview has the Note button; students never see it.
3. Tell the teacher, in a few short lines:
   - Press Start and play the tutor as a student.
   - Press Note at any moment, type or say the note, and press Save note.
     While the note box is open, what they say goes into the note, not to the
     tutor.
   - The note list shows each note's status and your reply.
   - Say "done" here when they have finished.
4. Wait for notes: run `scripts/notes.py wait <tutor>` in the background. It
   exits as soon as the teacher saves a note and prints every new note, with
   the module, the board section and the tutor's last words when the note was
   written.
5. Apply each note (below). Then start `scripts/notes.py wait <tutor>` again.
6. When the teacher says done, stop the preview and say what changed, file by
   file (`git diff --stat` helps). Then offer the evals (say the cost first)
   and the deploy (references/later-visits.md). Commit only when asked.

## Applying a note

Sort the note by kind, and put it where it works best:

| The note is about | Put it in |
|---|---|
| How the tutor teaches in general: tone, pacing, how explanations are given, using analogies, how much to say before asking | `content/teacher.md`, under `## General` |
| How one module is taught, as a whole ("go slower in Module 3") | `content/teacher.md`, under `## Module <n>` |
| One step: an analogy for this idea, a different example, explain X before Y | The module script (`content/0<n>-*.md`), in the part the note's module and section point to |
| The words of a module intro | `content/module-intros.md` (the fixed intro every student hears) |

`content/teacher.md` holds the teacher's own rules. It goes into the prompt
after the scripts and takes precedence over them. Create it when the first
general note arrives:

```
# Teacher's instructions

## General

- Before each formula, explain the idea with an everyday analogy.
```

Write each note as a short instruction to the tutor, in the teacher's terms.
Keep the teacher's examples and analogies as they gave them.

Then, for every note:

- Numbers: a new example's numbers come from the tutor's tools, never from
  your head. If the tutor has a content test that checks quoted numbers
  (`<tutor>/tests/test_content.py`), add the new ones to it.
- Run `scripts/test.sh <tutor>`. A change to the prompt fails the pinned
  prompt test (`<tutor>/tests/test_prompt.py`): update its hash.
- Mark the note: `scripts/notes.py set <tutor> <id> applied "<what changed, in
  one line>"`. The teacher sees this line on the board.
- Tell the teacher here, in one line per note, what changed and how to hear
  it: the tutor uses it from its next reply; to hear a step again, they pick
  the module from the menu or press New session.

Ask instead of guessing. If a note is unclear, or would need something more
than an edit to the tutor's text (a new tool, plot, data or module), mark it
`question` with your question as the reply, ask the same question here, and
apply it when they answer. A new tool or module follows references/later-visits.md.

Never put a teacher's note in `engine/` or `instructions/`. Those are shared
by every tutor. If a note seems right for every tutor, ask the teacher whether
to make it a shared change (references/later-visits.md).

## Other changes

For changes made without the preview (a new tool, new modules, the review
page, evals, a redeploy), read references/later-visits.md.

## Talking to the user

- Say what each step does, why, and what the user does next. Short, direct
  sentences in active voice. No bold.
- When you stop, end with the one thing you need from the user.
