You are working in /Users/carlosmac/users/carlosmac/arbiter on branch feat/roadmap-sessions.

You have 10 minutes. Be pragmatic and ship a working increment. Do NOT commit, push, create PRs, place trades, or touch/print real Kalshi credentials.

Project: Arbiter — private Kalshi intelligence dashboard. Next.js 16, React 19, TypeScript, Tailwind CSS 4.

Read first:
- AGENTS.md
- README.md
- docs/roadmap.md
- src/app/report-schema.ts
- scripts/collect_kalshi_public_snapshot.py
- scripts/collect_kalshi_portfolio.py
- data/reports/sample/*.json
- data/kalshi_snapshot/2026-05-06.json
- data/portfolio/2026-05-06.json

Session 5 goal: First Analysis Engine — Rules, Ranking, and Pass Logic.

Create the first useful recommendation engine. It should be conservative and pass most markets without a reliable model.

Required work:
1. Add analysis module(s), likely TypeScript under src/analysis/ or Python under scripts/analysis. Choose the quickest clean path.
2. Implement market classification:
   - politics
   - F1
   - economics
   - weather
   - other/no-model
3. Implement recommendation actions:
   - Buy YES
   - Buy NO
   - Hold
   - Reduce
   - Exit
   - Watch
   - Pass
4. Implement ranking/pass logic:
   - Calculate current executable price from yes_ask/no_ask or reasonable fallback.
   - Compare to Marcus fair value when available from simple model/evidence stub.
   - High confidence: 5+ points after spread may qualify.
   - Medium confidence: 8-10+ points after spread may qualify.
   - Low confidence: pass unless very large edge.
   - Other/no-model markets should usually Pass: no reliable model.
   - Cap recommendations shown as opportunities to 5 by default.
5. Implement portfolio exit/reduce logic using portfolio snapshot + current market snapshot where possible.
6. Generate daily report JSON from market + portfolio snapshots, e.g. scripts/generate_daily_report.py or npm script:
   - input market snapshot
   - input optional portfolio snapshot
   - output reports/YYYY-MM-DD.json and/or data/reports/generated/YYYY-MM-DD.json
7. Make generated report conform to src/app/report-schema.ts or update schema if needed.
8. Update dashboard Today tab to be able to read generated report if present, fallback to samples.
9. Add tests for:
   - classification
   - ranking thresholds
   - no-trade day generation
   - pass reason codes
   - portfolio exit/reduce logic
   - top opportunities cap
10. Update README with command to generate a report.

Constraints:
- No live polling yet.
- No trading endpoints.
- No secrets.
- It is acceptable for this engine to produce mostly Pass/Watch from generic snapshots.
- Do not invent fake confidence for markets without data.

Acceptance criteria:
- Generated daily report works from existing fixture/snapshot data.
- Can produce “No trade today.”
- Can recommend reducing/exiting held position when fair value is below executable exit price.
- Every non-pass recommendation has reason and confidence.
- npm test passes.
- npm run lint passes.
- npm run build passes.

At the end, print changed files and verification results.