
---

## The debate team

A proposer and adversaries, each a different model family, called through
OpenRouter. They are stateless: one call each, charter plus brief in, JSON out.
The brief you write IS their context.

```bash
OPENROUTER_API_KEY=$OPENROUTER_API_KEY python3 -m tools.debate.debate \
    --seats proposer --brief-file <path> --project .

OPENROUTER_API_KEY=$OPENROUTER_API_KEY python3 -m tools.debate.debate \
    --seats adversary,adversary_2 --brief-file <path> --project .   # concurrent
```

Each coauthor needs their own key; calls are billed to whoever runs them. The
roster is `project/global/config.toml`, shared and committed so everyone debates
against the same panel. A seat that errors returns `{"error": ...}` — note it and
carry on; one bad voice never sinks a round.

### Record the question, the decision, and the reason — not the briefs

Write every brief you send a seat to
`project/<author>/logs/brief-<seat>-<stamp>.md`, never a temp file. Stamp it with
`python3 -m tools.runid --stamp`, since briefs are rewritten each pass of the
loop and would otherwise overwrite each other. They stay local and gitignored:
they are the input to a decision, not the decision.

**What gets committed is the outcome, as a state entry:**

- the question actually put to the panel, in one line;
- what was decided;
- why — which objection carried, or what the panel failed to break.

Write it when the debate resolves, not at the end of the round. A coauthor
asking whether the team ever looked at X wants that entry; handed a folder of
briefs they would have to reconstruct the answer from the prompts, and nobody
does. If the panel killed a direction, it also goes in the killed-ideas section
with the reason — that is the same record viewed from the other end.

Every call — the messages sent and the response, with its model, usage and
latency — is appended to `logs/debate-<run>.jsonl`. That file stays local: it
carries full model responses and gets bulky. If a voice says something that
changes the project's direction, that belongs in the state with the reason, not
left in a log on one machine.
