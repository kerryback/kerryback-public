# smithers

A personal email and calendar desk.

Your inbox split into what actually needs a reply, a seven-day calendar, a task
list, and a Compose tab. Claude reads your Gmail and Calendar through a local
connector, writes an overview of what's ahead, and parks drafted replies in
Compose for you to review.

## Install

```
/plugin marketplace add kerryback/kerryback-public
/plugin install smithers@kerryback-public
```

Then ask what's on your plate, or invoke `/smithers`.

## Requirements

Python, and a Google account. First run walks through connecting Gmail and
Calendar; tokens are stored in `~/.smithers` on your own machine.

## What Claude can and can't do

This is the part worth reading before you use it.

| Claude can | Claude cannot |
| --- | --- |
| read your mail and calendar | send mail |
| draft a reply into Compose | delete a calendar event |
| propose a calendar change | act on either without you |

Sending and deleting stay your actions, in the app, by your click. Not because
the API won't allow it — because a mistaken send can't be recalled and a deleted
event takes someone else's time with it. Claude gets everything ready; you press
the button.

## Using it

The app runs at <http://127.0.0.1:8020>. Opening Smithers is itself the request
for a briefing: Claude reads the last few days of mail and the coming week and
publishes a fresh overview — what needs a reply, what's scheduled, what's
outstanding — without being asked. While it is writing, the Overview tab says so,
so yesterday's briefing is never mistaken for today's. Asking for a briefing at
any other time does the same thing.

"Draft a reply to Dana" writes into Compose. You open it, change what you want,
and send it yourself. "What am I walking into with the 2pm" reads the thread
history behind a meeting and tells you.

## Where things live

Everything is local: `~/.smithers` holds the state and the Google tokens. Nothing
is uploaded anywhere beyond the Google APIs your own account already talks to.
