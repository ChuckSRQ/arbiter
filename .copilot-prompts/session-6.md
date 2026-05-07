You are working in /Users/carlosmac/users/carlosmac/arbiter on branch feat/roadmap-sessions.

You have 10 minutes. Be pragmatic and ship a working increment. Do NOT commit, push, create PRs, place trades, or touch/print real Kalshi credentials.

Project: Arbiter — private Kalshi intelligence dashboard. Next.js 16, React 19, TypeScript, Tailwind CSS 4.

Read first:
- AGENTS.md
- README.md
- docs/roadmap.md
- src/analysis/engine.ts
- src/app/report-schema.ts
- scripts/generate_daily_report.ts
- data/reports/sample/political-edge-day.json

Session 6 goal: Political Polling Evidence Layer.

Wire the polling-first workflow into Arbiter enough that political recommendations can cite evidence or explicitly pass because polling is missing/stale.

Required work:
1. Add polling evidence module(s), either TypeScript or Python, whichever fits the existing analysis engine fastest.
2. Define a stable polling evidence JSON shape with fields like:
   - collected_at
   - source_url
   - race/market_key
   - market_type: binary-general, multi-candidate-primary, top-two, chamber-control, unknown
   - polling_average
   - latest_polls[] with pollster, dates, sample, toplines, spread
   - trend_summary
   - evidence_links[]
3. Add sanitized fixture evidence for at least two markets:
   - Ohio Senate general / Husted vs Brown style market
   - Louisiana Senate GOP primary / Fleming-Letlow-Cassidy style market
   Use RCP/RealClearPolling links as evidence URLs. Do not scrape live if time is short; fixture-backed evidence is acceptable for this session.
4. Update analysis engine so political markets:
   - look for matching polling evidence by ticker/title/race key
   - cite polling evidence links in recommendations
   - use polling trend/fair-value estimate when available
   - pass with reason "missing-or-stale-polling" when no useful polling exists
   - do NOT compare primary raw vote share directly to probability; include note about plurality/fragmentation
5. Add or update report generation to accept optional polling evidence input, e.g. --polling-evidence data/polling_evidence/sample.json.
6. Update Evidence tab/dashboard to show polling evidence summaries and links from the generated report.
7. Add tests for:
   - political market with polling evidence cites links and gets a fair value/rationale
   - political market missing polling passes with missing-or-stale-polling
   - primary evidence includes fragmentation/plurality warning
   - generated report includes evidence links
8. Update README with polling evidence command/example.

Constraints:
- Polling first. News narrative should not drive recommendations.
- Kalshi-first. Other markets optional context only.
- No live API required for this session.
- No secrets.
- Existing generated report flow must keep working.

Acceptance criteria:
- One or two political markets can be analyzed end-to-end with evidence links.
- Political recommendations cite polling or pass due to missing/stale polling.
- Primary raw vote share is not treated as direct market probability.
- npm test passes.
- npm run lint passes.
- npm run build passes.

At the end, print changed files and verification results.