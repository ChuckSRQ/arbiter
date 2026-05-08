<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# AGENTS.md — Arbiter

Operating rules for any agent working in this project.

## Project Context

Name: Arbiter
Overview: Personal Kalshi election intelligence dashboard
Stack: Python collector + TypeScript engine + Next.js site
License: MIT
Created: 2026-05-06

## Pipeline

Primary flow:

1. `scripts/collect_kalshi_public_snapshot.py`
2. `scripts/run_daily_report.ts`
3. `scripts/generate_daily_report.ts`
4. report JSON in `data/reports/generated/*.json`
5. site rendering in `src/app/page.tsx`

## Key files

- `scripts/collect_kalshi_public_snapshot.py` — curated Kalshi election/tracker collection (60-day default window).
- `scripts/run_daily_report.ts` — daily orchestration and report/archive outputs.
- `scripts/generate_daily_report.ts` — report generation from snapshot + polling evidence.
- `src/analysis/engine.ts` — market classification, pass/opportunity logic, priority scoring.
- `src/app/report-schema.ts` — report contract for `opportunities`, `onWatch`, `trackers`, `passes`.
- `src/app/page.tsx` — site sections: Opportunities, On Watch, Pulse Check.

## Design system

- Dark blue: `#0D0F1A`, `#141828`
- Amber: `#FCD34D`
- Blue: `#60A5FA`

## Skills

- **`kalshi-integration`** — Kalshi API integration: authentication, market data, order placement, F1 trading workflows. Base URL: `https://api.elections.kalshi.com/trade-api/v2`. Public market data requires no API key. Authenticated endpoints (portfolio, orders) need RSA-PSS signed requests via `kalshi_python_sync` SDK.
- **`prediction-market-trading`** — Prediction market analysis, trading strategy, and data queries. Kalshi-first for politics and F1. Polymarket as optional cross-market context only. Polling-first for political markets. F1 markets require F1ReplayTiming pace data — never driver reputation.

## Product Rule

Arbiter is an edge filter, not a market screener. The daily report should focus on the 3-5 best opportunities or explicitly say “No trade today.” Do not force a position on every market.

## Guardrails

1. Plan before implementing substantive changes.
2. No hardcoded secrets, API keys, private keys, tokens, or credentials.
3. No automatic trading in V1.
4. Use Kalshi as the primary venue. Other markets are context only unless Carlos asks.
5. Political markets are polling-first: RCP/polling averages and individual poll tables before narrative coverage.
6. F1 markets use the specialized F1 workflow and F1ReplayTiming pace data.
7. Prefer TDD for behavior changes and utility code.
8. Keep reports honest: “pass” and “no trade” are valid outputs.

## Dev commands

```bash
npm run build
npm start -- --port 4000
python3 scripts/collect_kalshi_public_snapshot.py
```

## GitHub Workflow

Never push directly to `main`. Always create a branch and open a PR.

## Off-Limits

- No code that places orders without explicit future approval.
- No committed `.env` file.
- No committed PEM/private key files.
- No logs containing secrets.
- No AgentZeroth orange branding; this is a separate project.
