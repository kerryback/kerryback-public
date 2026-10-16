# Add a note

Read and follow this when the user wants to capture a thought or note, optionally
tied to specific papers. `LITDB_PY` is resolved in SKILL.md.

The user writes the note in whatever form they like and hands it to you: a sentence
in chat, several paragraphs pasted in, a Markdown or text file on disk, a voice
transcript, scattered remarks over the course of a conversation. There is no format
to conform to and no form to fill in. Your job is to take that raw text and file it
--- the fields below are yours to infer, not theirs to supply. Never answer a note
with a list of questions about its metadata.

## Steps

1. Take the note as given. Preserve the user's own words for the body --- edit only
   to fix obvious dictation or typing slips, never to summarize, restructure, or
   improve their prose. If they pointed at a file, read it and use its contents. If
   the note is long, pass `--body -` and pipe it on stdin rather than trimming it.
   Give it a short title if it has none.

2. Infer the `kind` from what the note is doing: `idea`, `summary`, `critique`,
   `question`, `todo`, or `quote`. If it genuinely doesn't fit one, leave it off ---
   an untyped note is better than a wrong type.

3. Links. Work out which papers the note is about from its text --- the author name,
   the result, the method it argues with --- and find them yourself (see
   `search.md`). Attach a relation label: `about`, `supports`, `contradicts`,
   `extends`, `uses-method`, `uses-data`. On a confident single match, link it and
   say which paper you linked in one line. When several papers are plausible, or the
   note would take more than a couple of links, name your best guess and let the user
   correct it --- a wrong link is worse than no link, because it corrupts what
   retrieval returns later. Don't link speculatively. If the note quotes a paper or
   points at a specific page, add `--page N` and/or `--quote "verbatim passage"`
   (these attach to the linked paper).

4. Confidential. If the note contains unpublished ideas, private critiques, or
   referee-confidential material, add `--confidential`. Confidential notes are
   only ever embedded with a local model, never a hosted API. When unsure, ask.

5. Project tag. By default the note is tagged with the current working directory's
   name. Infer that name and state it in one line — e.g. "Tagging this note to
   project _momentum-crashes_ (from your working folder); tell me if it belongs
   somewhere else." Proceed with the default unless the user redirects; when the
   inferred name is clearly right, don't block on a reply. If they name a different
   project (or several), pass `--project "<name>"` (repeatable, which overrides the
   default); if they want it untagged, pass `--no-project`.

6. Create it:
   ```
   "$LITDB_PY" -m litdb add-note --title "T" --body "…" [--kind summary] \
       [--link PAPER_ID ...] [--relation about] [--page N] [--quote "…"] \
       [--confidential] [--project "<name>" ... | --no-project]
   ```
   For a long body, pass `--body -` and pipe the text on stdin. The result echoes
   the `kind` and the `projects` the note was tagged with.

7. Embed so the note is searchable: `"$LITDB_PY" -m litdb embed`. Then confirm in one
   line what you filed --- the kind, the linked paper, the project tag --- so the
   user can correct an inference without having had to make it.

To link an existing note to another paper later:
`"$LITDB_PY" -m litdb link --note NOTE_ID --paper PAPER_ID [--relation R] [--page N] [--quote "…"]`.

## Reading notes back
- `"$LITDB_PY" -m litdb notes [--paper ID] [--kind K] [--project NAME] [--since DATE]`
  lists notes (newest first, full bodies). `notes --search "QUERY"` searches notes
  only (hybrid) and returns full notes. `note ID` shows one. Notes are read whole and
  come first when answering topic questions — see `search.md` step 0.
