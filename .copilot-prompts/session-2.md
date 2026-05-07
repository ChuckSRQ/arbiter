You are working in /Users/carlosmac/users/carlosmac/arbiter on branch feat/roadmap-sessions.

You have 10 minutes. Be pragmatic and ship a working increment. Do NOT commit, push, create PRs, place trades, or touch real Kalshi credentials.

Project: Arbiter — private Kalshi intelligence dashboard. Next.js 16, React 19, TypeScript, Tailwind CSS 4.

Read first:
- AGENTS.md
- README.md
- docs/roadmap.md
- src/app/page.tsx
- src/app/dashboard-data.ts
- src/app/page.test.tsx
- package.json

Session 2 goal: Report Schema + Mock Data Discipline.

Implement a stable daily report data contract before live data gets messy.

Required work:
1. Define TypeScript report schema/types for:
   - DailyReport
   - Opportunity
   - PositionReview
   - EvidenceLink
   - MarketSnapshot
   - PortfolioSnapshot
   - RecommendationAction
2. Add runtime validation utilities without heavy dependencies if possible. If you add a dependency, keep it justified and minimal.
3. Add sample schema-valid reports:
   - data/reports/sample/no-trade-day.json
   - data/reports/sample/political-edge-day.json
   - data/reports/sample/portfolio-exit-day.json
4. Update the dashboard mock data to consume schema-valid report data rather than ad-hoc objects.
5. Dashboard must handle:
   - no-trade day
   - missing evidence
   - portfolio exit/reduce recommendations
6. Add or update tests proving:
   - valid reports pass validation
   - invalid reports fail with useful messages
   - top opportunities are capped to 3-5
   - no-trade report renders/works logically

Constraints:
- No live API calls.
- No Kalshi auth.
- No cron.
- No automatic trading.
- No secrets.
- Keep UI behavior from Session 1 intact.

Acceptance criteria:
- npm test passes.
- npm run lint passes.
- npm run build passes.
- Invalid report fails validation with useful message.
- Dashboard consumes schema-valid report data.

At the end, print changed files and verification results.