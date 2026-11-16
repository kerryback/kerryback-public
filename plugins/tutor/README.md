# tutor

Builds voice whiteboard tutors for a topic you teach.

```
/plugin marketplace add kerryback/kerryback-public
/plugin install tutor@kerryback-public
```

Start a new session, and run `/tutor:create` (or say "make a tutor for <topic>"),
pointing at your slides, notebooks, or code. The skill clones [tutor-starter](https://github.com/kerryback/tutor-starter)
to `~/repos/tutors`, builds the tutor, and stops for your approval at a review page,
a local try, evals, and the deploy.

To change a tutor, run `/tutor:edit <tutor>`. It opens a preview of the tutor
with a Note button. Play the tutor as a student; when something should change
(an analogy to add, an example, how explanations are given), press Note, type
or say it, and save. Claude applies each note to the tutor's files, and the
tutor uses the change from its next reply. General rules go in
`<tutor>/content/teacher.md`; notes about one step go into that module's script.

Running a tutor needs `ANTHROPIC_API_KEY`. Deploying needs a Railway account (Hobby plan), a domain,
and a mail service. See the tutor-starter README.
