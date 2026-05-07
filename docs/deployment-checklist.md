# Pre-deployment checklist

Use this only when Arbiter is stable enough for remote access. Deployment is optional.

## Before any deployment

1. Run `npm test`, `npm run lint`, and `npm run build`.
2. Confirm no real credentials, `.env`, private keys, or secret logs are tracked in Git.
3. Verify any required environment variables are configured only in the deployment platform, not in the repo.

## Operational guardrails

1. Keep cron optional until the local daily runner has been manually reviewed end-to-end.
2. Do not add automatic trading or any order-placement path in deployment.
3. Treat portfolio access as read-only and confirm failures degrade cleanly when secrets are missing.

## Hosting notes

1. Vercel is optional and reasonable for private access because the dashboard already builds as a static App Router page.
2. If Vercel is used, configure secrets in project settings and keep scheduled jobs disabled until Carlos explicitly wants them.
3. Prefer a private project with authenticated access over any public deployment.
