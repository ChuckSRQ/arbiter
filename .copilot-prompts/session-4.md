You are working in /Users/carlosmac/users/carlosmac/arbiter on branch feat/roadmap-sessions.

You have 10 minutes. Be pragmatic and ship a working increment. Do NOT commit, push, create PRs, place trades, or print/touch real Kalshi credential values.

Project: Arbiter — private Kalshi intelligence dashboard. Next.js 16, React 19, TypeScript, Tailwind CSS 4.

Read first:
- AGENTS.md
- README.md
- docs/roadmap.md
- scripts/collect_kalshi_public_snapshot.py
- src/app/report-schema.ts
- src/app/page.tsx
- .env.example

Session 4 goal: Portfolio Reader + Risk View.

Add authenticated Kalshi portfolio reading with safe missing-credential behavior. No order placement.

Required work:
1. Add script:
   - scripts/collect_kalshi_portfolio.py
2. Read credentials only from environment variables / .env-compatible local values:
   - KALSHI_BASE_URL default https://api.elections.kalshi.com/trade-api/v2
   - KALSHI_API_KEY_ID
   - KALSHI_PRIVATE_KEY_PATH
   Do not read or print private key contents. Do not commit .env.
3. Implement Kalshi RSA-PSS signing correctly:
   - timestamp in milliseconds
   - signed message = timestamp + method + full API path, including /trade-api/v2 prefix
   - strip query params from signed path
4. Portfolio calls should be read-only only:
   - GET /portfolio/balance
   - GET /portfolio/positions if credentials exist
   No POST/DELETE order endpoints.
5. Missing credentials should produce clean JSON fallback and exit 0 or a clearly documented non-crashing result, suitable for dashboard fallback.
6. Save sanitized output to data/portfolio/YYYY-MM-DD.json by default unless --output is provided.
7. Add --fixture support for tests, using sanitized fixture data only.
8. Normalize output into stable JSON shape:
   - collected_at
   - source/base_url
   - available true/false
   - balance if available
   - positions[] with ticker, market_title, side, count, avg_price/current_price if available, market_value, unrealized_pnl, exposure, recommendation placeholder if applicable
   - warnings[] for missing credentials or unavailable portfolio
9. Add/update dashboard Portfolio tab to show portfolio unavailable cleanly and show mock/fixture reduce/exit recommendations.
10. Add tests for:
   - signed path includes /trade-api/v2
   - missing credentials fallback
   - fixture normalization
   - no order endpoints are referenced/called
11. Update .env.example and README with portfolio collector command.

Constraints:
- No trading endpoints.
- No secrets in code, logs, README, fixtures, or tests.
- No real credential values.
- Keep existing tests passing.

Acceptance criteria:
- npm test passes.
- npm run lint passes.
- npm run build passes.
- Portfolio collector works in fixture mode.
- Missing credentials produce clean fallback.

At the end, print changed files and verification results.