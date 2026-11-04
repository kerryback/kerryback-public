# Deploy

The tutors run on Railway. Ask for the go-ahead first, every time. Say what
will happen and what it costs. Railway's Hobby plan is $5 a month and
includes $5 of usage. After that, Railway bills what a service uses: $10 per
GB of RAM per month, $20 per vCPU per month, and $0.15 per GB of volume per
month (railway.com/pricing). A tutor holds its speech models in memory (about
0.9 GB) and keeps about 0.5 GB on its volume, so each tutor uses about $10 to
$12 a month, and the home app about $1. One tutor and the home app come to
about $11 to $13 a month in all. The model calls are billed to the user's
Anthropic key.

Each tutor is its own Railway project (the `project` in `[deploy]` in its
`tutor.toml`), built from the shared `Dockerfile`, with one service, `web`, on
port 8000: one instance in the region in `[deploy]` (`europe-west4-drams3a`,
Amsterdam), and a volume at `/data` for the student records and the speech
models. The home app is the project `tutors-home`. The scripts create all of
this on the first deploy.

## Before the first deploy of any tutor

The site needs four things, once.

1. The Railway CLI, version 5 or later, signed in (references/first-use.md).
   The user runs `railway login`, because it opens their browser. Never run it
   yourself. If the account has more than one workspace, set
   `railway_workspace` in `site.toml` to the one to use.
2. A domain in `site.toml`, such as `tutors.school.edu`, with the user's rule
   for who can make accounts in `email_domain`. The scripts refuse the example
   value.
3. An SMTP service for the sign-in emails, set in `site.toml`.
4. The secrets, in `~/repos/tutors/deploy.env` (Git ignores it). The user
   writes the values, because they are theirs: `ANTHROPIC_API_KEY`,
   `TUTORS_SECRET` and `TUTORS_PEPPER` (long random strings; `python3 -c
   "import secrets; print(secrets.token_urlsafe(48))"` makes one),
   `SMTP_PASSWORD`, and `ELEVENLABS_API_KEY` if `voice = "elevenlabs"`. A
   deploy sends each secret to a project the first time that project lacks it,
   and never changes it after that. To change one, the user runs
   `railway variable set <NAME> --stdin` in that project. Never print a secret.

Then deploy the home app, which holds the accounts and the sign-in pages:

1. `scripts/deploy-home.sh`. It creates the project, the service, the region
   and the volume, sets the variables, builds, waits for the deploy, and adds
   the site's domain.
2. The first time, it prints two DNS records for the domain: a CNAME and a
   TXT. The user adds both at their DNS provider; Railway verifies the domain
   only with both. If the provider has an API and the user gives a token, you
   can add them. With Cloudflare's proxy on, its SSL/TLS mode must be Full.
3. `railway domain status <domain>`, run in a folder linked to the project,
   shows when the domain is verified.
4. Add the tutor to `home/tutors.toml`, so the landing page lists it, and deploy
   the home app again whenever that file changes.

## Before each tutor's first deploy

- `scripts/test.sh <tutor>` passes, and the user has tried it locally.
- A tutor with a live-data module: check that the live source answers from
  Railway, not only from this computer. `scripts/deploy.sh <tutor> --trial`
  deploys a separate project at a Railway address; call the live tool once
  from it, then delete it with `railway delete --project <project>-trial
  --yes`. If the source does not answer, tell the user before going further.

## The first deploy

1. `scripts/deploy.sh <tutor>`. It reads `[deploy]` in `tutor.toml` and
   `site.toml`, creates the project, the service, the region and the volume,
   sets the variables and the secrets, uploads and builds, and waits until the
   deploy succeeds or fails. Then it adds the domain `<tutor>.<domain>` and
   prints its CNAME and TXT records.
2. The user adds the two records at their DNS provider.
3. When the domain is verified, open `https://<tutor>.<domain>/api/config` and
   check that it reports `voice_ready: true`. The first start downloads the
   speech models to the volume, so this can take a few minutes.

Tell the user the address.

## Later deploys

Only step 1. The domain and the secrets are already in place. After a change
to `engine/` or `instructions/`, use `scripts/deploy-all.sh` instead (see
references/later-visits.md).

## When a deploy fails

`railway logs --build --lines 100` and `railway logs --deployment --lines
100`, run in a folder linked to the project (`railway link --project
<project> --service web`), show what went wrong. Show the user the error in
plain words before trying again.
