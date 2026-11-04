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

| Claude can | Left to you |
| --- | --- |
| read your mail and calendar | send mail |
| draft a reply into Compose | edit or delete a calendar event |
| add an event, propose a calendar change | apply a proposal |

Sending, editing, deleting, and applying stay your actions, in the app, by your
click, because a mistaken send can't be recalled and a deleted event takes
someone else's time with it. Claude gets everything ready; you press the button.

The app runs on your machine, where Claude's shell can reach it, so this rests on
three layers, and none of them is airtight:

1. The skill's instructions list the routes behind those buttons and tell Claude
   never to call them.
2. A PreToolUse hook in this plugin denies tool calls aimed at those routes. It
   matches the text of the call, so a request built to hide the path can get
   past it.
3. The app answers those routes with 403 unless the request carries a token that
   is made fresh at each launch and placed in the page your browser loads. That
   stops a stray request; it does not stop a caller that reads the page first.

If you restart the app while the page is open, reload the page before you press
Send, Apply, Edit, or Delete.

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
