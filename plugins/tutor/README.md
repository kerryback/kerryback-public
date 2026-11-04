# tutor

Builds voice whiteboard tutors for a topic you teach.

```
/plugin marketplace add kerryback/kerryback-public
/plugin install tutor@kerryback-public
```

Start a new session, and say "make a tutor for <topic>", pointing at your slides,
notebooks, or code. The skill clones [tutor-starter](https://github.com/kerryback/tutor-starter)
to `~/repos/tutors`, builds the tutor, and stops for your approval at a review page,
a local try, evals, and the deploy.

Running a tutor needs `ANTHROPIC_API_KEY`. Deploying needs a Railway account (Hobby plan), a domain,
and a mail service. See the tutor-starter README.
