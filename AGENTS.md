<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# AGENTS.md — Arbiter

Operating rules for any agent working in this project.

## Project Context

Name: Arbiter
Type: Personal Kalshi intelligence dashboard
Stack: Next.js 16, React 19, TypeScript, Tailwind CSS 4
License: MIT
Created: 2026-05-06

## Skills

- **`kalshi-integration`** — Kalshi API integration: authentication, market data, order placement, F1 trading workflows. Base URL: `https://api.elections.kalshi.com/trade-api/v2`. Public market data requires no API key. Authenticated endpoints (portfolio, orders) need RSA-PSS signed requests via `kalshi_python_sync` SDK.
- **`prediction-market-trading`** — Prediction market analysis, trading strategy, and data queries. Kalshi-first for politics and F1. Polymarket as optional cross-market context only. Polling-first for political markets. F1 markets require F1ReplayTiming pace data — never driver reputation.

## Product Rule

Arbiter is an edge filter, not a market screener. The daily report should focus on the 3-5 best opportunities or explicitly say “No trade today.” Do not force a position on every market.

## Guardrails

1. Plan before implementing substantive changes.
2. No hardcoded secrets, API keys, private keys, tokens, or credentials.
3. No automatic trading in V1. Portfolio reading is allowed only through properly configured authenticated Kalshi access.
4. Use Kalshi as the primary venue. Other markets are context only unless Carlos asks.
5. Political markets are polling-first: RCP/polling averages and individual poll tables before narrative coverage.
6. F1 markets use the specialized F1 workflow and F1ReplayTiming pace data.
7. Prefer TDD for behavior changes and utility code.
8. Keep reports honest: “pass” and “no trade” are valid outputs.

## GitHub Workflow

For future changes after the initial scaffold:

```bash
git checkout main
git pull origin main
git checkout -b feat/description
# make changes
git add .
git diff --cached --check
npm run build
npm run lint
git commit -m "feat: description"
git push -u origin HEAD
```

Carlos merges PRs through GitHub UI. Do not merge PRs automatically.

## Off-Limits

- No code that places orders without explicit future approval.
- No committed `.env` file.
- No committed PEM/private key files.
- No logs containing secrets.
- No AgentZeroth orange branding; this is a separate project.
