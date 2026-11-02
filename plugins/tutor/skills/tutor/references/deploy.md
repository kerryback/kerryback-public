# Deploy

Ask for the go-ahead first, every time. Say what will happen and what it
costs: each tutor is a Koyeb medium instance (about $21 a month) with a 5 GB
volume, and the model calls are billed to the user's Anthropic key.

## Before the first deploy of any tutor

The site needs three things, once.

1. A domain in `site.toml`, such as `tutors.school.edu`, with the user's rule
   for who can make accounts in `email_domain`. The scripts refuse the example
   value.
2. An SMTP service for the sign-in emails, set in `site.toml`.
3. These Koyeb secrets. The user creates them, because the values are theirs:
   `tutors-session-secret` and `tutors-pepper` (long random strings),
   `tutors-anthropic-key`, `tutors-smtp-password`, and `elevenlabs-api-key` if
   `elevenlabs = true`. Use `koyeb secrets create <name> --value-from-stdin`.

Then deploy the home app, which holds the accounts and the sign-in pages:

1. `scripts/deploy-home.sh`.
2. Add the site's domain to its Koyeb app (`koyeb domains create <domain>
   --attach-to tutors-home`).
3. Have the user add the CNAME record at their DNS provider, pointing where
   Koyeb says. If the provider has an API and the user gives a token, you can
   add it.
4. Add the tutor to `home/tutors.toml`, so the landing page lists it, and deploy
   the home app again whenever that file changes.

## Before each tutor's first deploy

- `scripts/test.sh <tutor>` passes, and the user has tried it locally.
- A tutor with a live-data module: check that the live source answers from
  Koyeb, not only from this computer (for example, deploy and call the live
  tool once from the running service). If it does not, tell the user before
  going further.

## The first deploy

1. `scripts/deploy.sh <tutor>`. It reads `[deploy]` in `tutor.toml` and
   `site.toml`, creates the volume, and deploys with the shared secrets.
2. Add the domain `<tutor>.<domain>` to the Koyeb app, and the CNAME record for it.
3. Wait until the deployment is healthy, then open the live site and check
   that `/api/config` reports `voice_ready: true`.

Tell the user the address.

## Later deploys

Only step 1. After a change to `engine/` or `instructions/`, use
`scripts/deploy-all.sh` instead (see references/later-visits.md).
