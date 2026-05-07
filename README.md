# Arbiter

A private Kalshi intelligence dashboard that judges market prices against evidence, portfolio exposure, and disciplined fair-value estimates.

**Type:** Web app / personal trading research dashboard
**Stack:** Next.js 16, React 19, TypeScript, Tailwind CSS 4
**License:** MIT
**Created:** 2026-05-06

---

## What Arbiter Does

Arbiter is not a broad market screener. It is an edge filter.

The daily workflow should:

1. Scan Kalshi markets expiring in the next 30 days.
2. Review Carlos's current Kalshi portfolio.
3. Produce a financial-report-style daily brief.
4. Focus on the 3-5 best opportunities only.
5. Recommend “No trade today” when nothing clears the bar.
6. Recommend hold/reduce/exit decisions for existing positions.
7. Show current Kalshi price, Marcus fair value, edge, confidence, evidence links, and the reason behind the recommendation.

No automatic trade execution belongs in V1.

---

## Product Principles

- Kalshi-first. Other prediction markets are context only unless explicitly requested.
- Polling-first for political markets: RealClearPolling/RCP averages and individual poll tables before narrative coverage.
- F1 uses the existing specialized F1 pace workflow; do not reinvent it here.
- Most markets should be passed. The absence of a good trade is a valid report.
- Use executable prices when thinking about trades: buy at ask, sell/exit at bid.
- Every recommendation needs a fair-value estimate, confidence level, evidence links, and a “what would change the view” note.
- Never expose credentials in logs, reports, the UI, or Git.

---

## Design Direction

Base design:
`/Users/carlosmac/Marcus/Workspace/design-library/designs/67-professional-virtual-cfo.md`

Adapted palette:

- Deep indigo shell: `#1B1B4A`
- Electric blue accent: `#3B82C4`
- Dark indigo dashboard canvas, not black and not grey
- Warm off-white/sand body text
- Green for favorable edge/profit
- Red for exit/risk
- Amber only for caution
- No AgentZeroth orange branding

---

## Setup

```bash
cd /Users/carlosmac/users/carlosmac/arbiter
npm install
cp .env.example .env
npm run dev
```

Then open:

```text
http://localhost:3000
```

## Development Commands

```bash
npm run dev      # local dev server
npm run build    # production build check
npm run lint     # ESLint
npm test         # TypeScript + Python tests
```

---

## Public Kalshi Scanner

The Session 3 scanner is public-only. It calls `GET /markets` with `status=open`, never uses credentials, filters to markets closing within the next 30 days by default, and writes a normalized snapshot to `data/kalshi_snapshot/YYYY-MM-DD.json`.

```bash
npm run collect:kalshi-public
```

Useful options:

```bash
python3 scripts/collect_kalshi_public_snapshot.py --window-days 14 --max-pages 2
python3 scripts/collect_kalshi_public_snapshot.py --fixture tests/fixtures/kalshi_public_markets_pages.json --output data/kalshi_snapshot/fixture.json
```

---

## Portfolio Reader

The Session 4 portfolio collector is read-only. It only calls `GET /portfolio/balance` and
`GET /portfolio/positions`, signs requests with RSA-PSS using the full `/trade-api/v2/...` path,
never prints credentials or private key contents, and falls back to clean JSON when local
credentials are missing.

```bash
npm run collect:kalshi-portfolio
```

Useful options:

```bash
python3 scripts/collect_kalshi_portfolio.py --fixture tests/fixtures/kalshi_portfolio_fixture.json --output data/portfolio/fixture.json
python3 scripts/collect_kalshi_portfolio.py --output data/portfolio/$(date +%F).json
```

Local-only environment variables:

```bash
KALSHI_BASE_URL=https://api.elections.kalshi.com/trade-api/v2
KALSHI_API_KEY_ID=
KALSHI_PRIVATE_KEY_PATH=
```

If `KALSHI_API_KEY_ID` or `KALSHI_PRIVATE_KEY_PATH` is missing, the collector still exits cleanly
with `available: false`, an empty positions list, and warnings the dashboard can render safely.

---

## Daily report generator

The analysis engine reads the saved public market snapshot plus optional portfolio and polling
evidence inputs, applies conservative pass-first ranking rules, and writes a schema-valid daily
report to `data/reports/generated/YYYY-MM-DD.json`. Political markets are polling-first: if
matching RCP-style evidence is missing or stale, Arbiter passes them instead of inventing a view.

```bash
npm run generate:report
```

Useful options:

```bash
node --import tsx scripts/generate_daily_report.ts --market-snapshot data/kalshi_snapshot/2026-05-06.json --portfolio-snapshot data/portfolio/2026-05-06.json
node --import tsx scripts/generate_daily_report.ts --market-snapshot data/kalshi_snapshot/2026-05-06.json --portfolio-snapshot data/portfolio/2026-05-06.json --polling-evidence data/polling_evidence/sample.json
node --import tsx scripts/generate_daily_report.ts --output data/reports/generated/manual.json --report-date 2026-05-06
```

## Daily runner + archive

The daily runner orchestrates the public snapshot, safe portfolio snapshot, optional polling
evidence, JSON report generation, markdown rendering, the latest dashboard pointer, and the local
archive. If portfolio credentials are missing, the run still completes with a clean
`available: false` portfolio snapshot instead of crashing.

```bash
npm run run:daily-report
```

Useful offline/manual verification command:

```bash
npm run run:daily-report -- --public-fixture tests/fixtures/kalshi_public_markets_pages.json --polling-evidence data/polling_evidence/sample.json --report-date 2026-05-06
```

Optional inputs:

```bash
npm run run:daily-report -- --public-fixture tests/fixtures/kalshi_public_markets_pages.json --portfolio-fixture tests/fixtures/kalshi_portfolio_fixture.json
npm run run:daily-report -- --polling-evidence data/polling_evidence/sample.json
```

Files written by the runner:

- `data/kalshi_snapshot/YYYY-MM-DD.json`
- `data/portfolio/YYYY-MM-DD.json`
- `data/reports/generated/YYYY-MM-DD.json`
- `data/reports/generated/YYYY-MM-DD.md`
- `data/reports/generated/latest.json`
- `data/reports/generated/latest.md`
- `reports/YYYY-MM-DD.json`
- `reports/YYYY-MM-DD.md`

The dashboard now prefers `data/reports/generated/latest.json` and uses `reports/*.json` to
populate the Archive tab with real archived report cards when they exist.

Suggested Hermes handoff after manual verification only:

```text
Prompt Hermes to schedule a weekday morning job that runs: cd /Users/carlosmac/users/carlosmac/arbiter && npm run run:daily-report
```

Do not schedule the cron job until Carlos/Marcus confirm that one manual run produced the expected
JSON, markdown, and archive files.

---

## Roadmap — 7 Sessions

### Session 1 — Project Scaffold + Static Dashboard Shell

Goal: Create the local project and make the dashboard feel real before wiring live data.

Scope:
- Scaffold Arbiter as a local web app.
- Create README, AGENTS.md, `.env.example`, docs, and initial git commit.
- Build the first static dashboard shell using mocked report JSON.
- Tabs: Today, Opportunities, Portfolio, Evidence, Archive.
- Use Virtual CFO-inspired indigo/electric-blue styling.
- No Kalshi auth yet.
- No cron yet.

Deliverables:
- Running local dashboard.
- Mock report rendered in the UI.
- Top 3-5 opportunities visible on Today tab.
- Empty/no-trade state exists.
- Project plan copied into project docs.

Acceptance criteria:
- `npm run dev` works.
- `npm run build` passes.
- Dashboard opens in Chrome.
- No AgentZeroth orange.
- No grey body text.
- UI makes it obvious that this is an edge filter, not a market screener.

Stop point: stop after the visual/dashboard shell is good enough to react to. Do not wire Kalshi yet.

---

### Session 2 — Report Schema + Mock Data Discipline

Goal: Define the data contract before live data gets messy.

Scope:
- Create TypeScript/Python schema for daily report JSON.
- Define entities: DailyReport, Opportunity, PositionReview, EvidenceLink, MarketSnapshot, PortfolioSnapshot, RecommendationAction.
- Add validation tests.
- Replace ad-hoc mock data with schema-valid examples.
- Add sample reports: `no-trade-day.json`, `political-edge-day.json`, `portfolio-exit-day.json`.

Deliverables:
- `data/reports/sample/*.json`
- Schema validation utilities.
- Tests proving valid and invalid reports are handled correctly.
- Dashboard consumes schema-valid report files.

Acceptance criteria:
- Invalid report fails validation with a useful message.
- Dashboard handles missing evidence, no-trade days, and portfolio exits gracefully.
- `npm test` or equivalent passes.
- `npm run build` passes.

Stop point: stop once the UI and report contract are stable. No live API calls yet.

---

### Session 3 — Kalshi Public Market Scanner

Goal: Collect open Kalshi markets expiring in the next 30 days without touching credentials.

Scope:
- Build public Kalshi scanner script.
- Use Kalshi public API only.
- Fetch open markets with close/expiration dates.
- Normalize prices to cents/probabilities.
- Capture ticker, title, event/series, category, close time, yes/no bid/ask, midpoint, volume/liquidity/open interest if available, and resolution text/rules where available.
- Filter markets expiring in next 30 days.
- Save snapshots to `data/kalshi_snapshot/YYYY-MM-DD.json`.

Deliverables:
- `scripts/collect_kalshi_public_snapshot.py` or equivalent.
- Snapshot JSON file.
- Unit tests for price parsing and expiration filtering.
- Small CLI command in README.

Acceptance criteria:
- Scanner runs without Kalshi credentials.
- Uses `status=open`, not `status=active`.
- Does not mistake dollar strings for cents.
- Expiration filter verified against sample fixtures.
- No credentials or secrets in logs.

Stop point: stop when public market snapshot works and is displayable in dashboard as raw scan data.

---

### Session 4 — Portfolio Reader + Risk View

Goal: Add authenticated portfolio analysis without trade execution.

Scope:
- Read credentials only from `.env` or existing secure local convention.
- Implement authenticated Kalshi portfolio calls.
- Pull positions, current mark, cost basis if available, P/L, and exposure.
- Build portfolio risk view: current positions, exposure by event/category, unrealized P/L, stale/thesis-review alerts, reduce/exit candidate placeholders.
- No order placement.

Deliverables:
- `scripts/collect_kalshi_portfolio.py` or equivalent.
- `data/portfolio/YYYY-MM-DD.json` output.
- Portfolio tab connected to real/sanitized portfolio data.
- `.env.example` with variable names only, no values.

Acceptance criteria:
- Auth signing includes full `/trade-api/v2/...` path.
- Credentials are never printed.
- Missing credentials produce a clean error and dashboard fallback.
- Portfolio tab works with both real data and fixture data.
- No trading endpoint is called.

Stop point: stop once dashboard can show the real portfolio snapshot or a clean “portfolio unavailable” state.

---

### Session 5 — First Analysis Engine: Rules, Ranking, and Pass Logic

Goal: Create the first useful recommendation engine, even if domain models are simple.

Scope:
- Implement market classification: politics, F1, economics, weather, other/no-model.
- Build a ranking engine that aggressively passes markets without a model.
- Add edge thresholds: high confidence 5+ points after spread; medium confidence 8-10+ points after spread; low confidence passes unless edge is very large.
- Implement recommendation actions: Buy YES, Buy NO, Hold, Reduce, Exit, Watch, Pass.
- Add reason codes for passed markets.
- For V1, most markets should become `Pass: no reliable model`.

Deliverables:
- `src/analysis/*` or equivalent.
- Ranked daily report JSON generated from market + portfolio snapshots.
- Tests for ranking, thresholds, no-trade day, and portfolio exit logic.
- Dashboard Today tab reads generated report.

Acceptance criteria:
- Produces a daily report without manual editing.
- Top view never shows more than 5 opportunities unless explicitly configured.
- Can produce “No trade today.”
- Can recommend exiting/reducing a held position if fair value is below executable exit price.
- Every recommendation has a reason and confidence.

Stop point: stop when the dashboard shows a generated report from real Kalshi public data plus portfolio fixture/real data.

---

### Session 6 — Political Polling Evidence Layer

Goal: Make political-market recommendations useful by wiring the polling-first workflow.

Scope:
- Implement RealClearPolling/RCP evidence collection helpers.
- Prefer extractable `preview.realclearpolling.com` pages where needed.
- Store evidence links and extracted poll summaries.
- For political markets, require market type classification, RCP average or individual poll table when available, latest poll dates, trend direction, and fair-value estimate rationale.
- Add specific logic for binary general elections, multi-candidate primaries, top-two primaries, and chamber-control markets.
- News is context only, not primary evidence.

Deliverables:
- Polling evidence module.
- Evidence tab connected to real polling links/summaries.
- Political opportunity cards showing Kalshi current price, Marcus fair value, polling average/trend, evidence links, and what would change the view.

Acceptance criteria:
- Political recommendations cite polling or explicitly pass due to missing/stale polling.
- Raw primary vote share is not compared directly to market probability.
- Evidence links open to RCP/pollster pages.
- Report can explain “poll-market mismatch” in plain English.

Stop point: stop once one or two political markets can be analyzed end-to-end with real evidence links.

---

### Session 7 — Daily Cron + Archive + Notification

Goal: Turn the system into a daily habit.

Scope:
- Create a daily runner script:
  1. collect public Kalshi snapshot
  2. collect portfolio snapshot if credentials exist
  3. collect domain evidence where possible
  4. generate daily report JSON + markdown
  5. update dashboard current report pointer
  6. archive report
- Add Hermes cron job after one successful manual run.
- Decide delivery target: dashboard only, Obsidian archive, current chat notification, or all three.
- Recommended: dashboard + Obsidian + brief chat summary.

Deliverables:
- `scripts/run_daily_report.py` or equivalent.
- `reports/YYYY-MM-DD.json`
- `reports/YYYY-MM-DD.md`
- Dashboard archive tab wired to reports.
- Hermes cron job scheduled.

Acceptance criteria:
- Manual run completes successfully.
- Cron test run completes successfully.
- Empty stdout/silent-failure behavior is intentional.
- Dashboard updates to latest report.
- Obsidian or local archive contains the daily markdown report.
- No automatic trades.

Stop point: stop after one manual run and one cron test run work.

---

### Optional Session 8 — Polish, Review, and Deployment

Goal: Make it reliable and pleasant enough to use daily.

Scope:
- Visual polish after seeing real reports.
- Add loading/empty/error states everywhere.
- Add trend mini-charts if useful.
- Add report outcome tracking: recommendation date, recommended price, eventual result, and whether the thesis was right.
- Add deployment only if remote access is useful.
- Add GitHub repo/PR workflow if the project should be versioned remotely.

Deliverables:
- Final UI polish pass.
- Outcome-tracking scaffold.
- Optional Vercel deployment.
- Optional GitHub repo.

Acceptance criteria:
- Dashboard feels like a finished private research tool.
- Mobile/tablet is usable, even if desktop is primary.
- Report history is navigable.
- No obvious visual regressions.
- Build/test pass cleanly.

Stop point: stop when Carlos says it feels good enough for daily use.


---

## Project Log

| Date | What happened |
|------|---------------|
| 2026-05-06 | Project scaffolded as Arbiter; roadmap added to README; GitHub repo created. |

## Skills Used

| Skill | First Used | Last Used | Use Count | Notes |
|-------|------------|-----------|-----------|-------|
| project-creation | 2026-05-06 | 2026-05-06 | 1 | Scaffolded local project + Obsidian notes. |
| github | 2026-05-06 | 2026-05-06 | 1 | Created GitHub repository and pushed initial commit. |
| prediction-market-trading | 2026-05-06 | 2026-05-06 | 1 | Kalshi-first market and reporting discipline. |
| kalshi-integration | 2026-05-06 | 2026-05-06 | 1 | Kalshi API/auth constraints for future sessions. |
