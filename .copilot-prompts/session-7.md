You are working in /Users/carlosmac/users/carlosmac/arbiter on branch feat/roadmap-sessions.

You have 10 minutes. Be pragmatic and ship a working increment. Do NOT commit, push, create PRs, place trades, schedule Hermes cron jobs, or touch/print real Kalshi credentials.

Project: Arbiter — private Kalshi intelligence dashboard. Next.js 16, React 19, TypeScript, Tailwind CSS 4.

Read first:
- AGENTS.md
- README.md
- docs/roadmap.md
- scripts/collect_kalshi_public_snapshot.py
- scripts/collect_kalshi_portfolio.py
- scripts/generate_daily_report.ts
- src/analysis/engine.ts
- src/app/report-schema.ts
- data/polling_evidence/sample.json

Session 7 goal: Daily Cron + Archive + Notification foundation.

Implement the daily runner and archive flow. Do not schedule the actual Hermes cron job; leave clear instructions/output for Marcus/Carlos to schedule after manual verification.

Required work:
1. Add a daily runner script, e.g. scripts/run_daily_report.py or scripts/run_daily_report.ts.
2. Runner steps:
   - collect public Kalshi snapshot
   - collect portfolio snapshot if credentials exist; missing credentials must not crash
   - include polling evidence if provided or if default sample/path exists
   - generate daily report JSON
   - generate daily report markdown
   - update a current report pointer/file for dashboard use if helpful
   - archive outputs under reports/ and/or data/reports/generated
3. Markdown report should be financial-report style:
   - date/time
   - executive summary
   - top opportunities or “No trade today”
   - portfolio actions: hold/reduce/exit
   - evidence links
   - caveats/no-auto-trading reminder
4. Add npm script, e.g. run:daily-report.
5. Add Archive tab/dashboard wiring if not already enough: it should show archived report cards or latest archive status.
6. Add tests for:
   - markdown rendering for no-trade day
   - markdown rendering with opportunities/portfolio actions/evidence links
   - runner can execute in fixture/offline mode without credentials
   - current/latest pointer is updated or archived file exists
7. Update README with:
   - manual run command
   - what files it writes
   - suggested Hermes cron command/prompt, but do NOT schedule it yourself.

Constraints:
- No automatic trading.
- No Hermes cron scheduling from Copilot.
- No secrets.
- Offline/fixture path must pass tests.
- Existing tests/build must keep passing.

Acceptance criteria:
- Manual daily runner completes in fixture/offline mode.
- Writes JSON + Markdown report.
- Dashboard can show latest generated report/archive status.
- npm test passes.
- npm run lint passes.
- npm run build passes.

At the end, print changed files, manual runner command, and verification results.