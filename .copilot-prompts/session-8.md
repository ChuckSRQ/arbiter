You are working in /Users/carlosmac/users/carlosmac/arbiter on branch feat/roadmap-sessions.

You have 10 minutes. Be pragmatic and ship a working polish increment. Do NOT commit, push, create PRs, deploy, place trades, schedule cron jobs, or touch/print real Kalshi credentials.

Project: Arbiter — private Kalshi intelligence dashboard. Next.js 16, React 19, TypeScript, Tailwind CSS 4.

Read first:
- AGENTS.md
- README.md
- docs/roadmap.md
- src/app/page.tsx
- src/app/page.test.tsx
- src/app/report-storage.ts
- src/app/report-schema.ts
- reports/2026-05-06.md

Optional Session 8 goal: Polish, Review, and Deployment prep — but no actual deployment.

Do a focused polish/reliability pass after the real generated reports exist.

Required work:
1. Improve visual polish where it matters most:
   - latest report status
   - archive cards
   - no-trade state
   - portfolio action cards
   - evidence links
   Keep the indigo/electric-blue palette. No AgentZeroth orange. No grey body text.
2. Add loading/empty/error style states only where they are static/server-rendered and useful.
3. Add outcome-tracking scaffold only, not full feature:
   - e.g. docs/outcome-tracking.md or data/outcomes/.gitkeep + schema notes
   - fields: recommendation date, ticker, side/action, recommended price, fair value, eventual result, thesis outcome, notes
4. Add a short pre-deployment checklist in docs/deployment-checklist.md covering build, secrets, cron, no automatic trading, and Vercel optionality.
5. Add or update tests for any UI/state changes.
6. Do not deploy.
7. Do not schedule cron.

Acceptance criteria:
- Dashboard feels more finished but remains private/research-oriented.
- Outcome-tracking scaffold exists.
- Deployment checklist exists.
- npm test passes.
- npm run lint passes.
- npm run build passes.

At the end, print changed files and verification results.