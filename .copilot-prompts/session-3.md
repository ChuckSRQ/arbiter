You are working in /Users/carlosmac/users/carlosmac/arbiter on branch feat/roadmap-sessions.

You have 10 minutes. Be pragmatic and ship a working increment. Do NOT commit, push, create PRs, place trades, or touch real Kalshi credentials.

Project: Arbiter — private Kalshi intelligence dashboard. Next.js 16, React 19, TypeScript, Tailwind CSS 4.

Read first:
- AGENTS.md
- README.md
- docs/roadmap.md
- src/app/report-schema.ts
- src/app/dashboard-data.ts
- package.json

Session 3 goal: Kalshi Public Market Scanner.

Build a public-only Kalshi scanner that collects open markets expiring in the next 30 days. No authentication and no portfolio access.

Required work:
1. Add a scanner script, preferably Python for API/data collection:
   - scripts/collect_kalshi_public_snapshot.py
2. Use public Kalshi API only:
   - Base default: https://api.elections.kalshi.com/trade-api/v2
   - Endpoint: /markets
   - status=open, never status=active
3. Handle pagination/cursor if present.
4. Normalize market data into a stable JSON shape with:
   - collected_at
   - source/base_url
   - filters/window_days/status
   - markets[] including ticker, title, event_ticker, series_ticker, category if available, close_time/expiration, yes_bid/yes_ask/no_bid/no_ask in cents, midpoints, volume/open_interest/liquidity if available, rules/resolution text if available
5. Correctly parse Kalshi dollar strings like "0.4200" as 42 cents. Do not mistake them for cents already.
6. Filter to markets closing/expiring within next 30 days by default.
7. Save output to data/kalshi_snapshot/YYYY-MM-DD.json unless --output is provided.
8. Add CLI options:
   - --window-days
   - --limit-pages or --max-pages
   - --output
   - --base-url
   - --fixture maybe if helpful for tests
9. Add tests for:
   - price parsing
   - expiration filtering
   - normalizing sample market objects
10. Add npm script(s) if useful, e.g. collect:kalshi-public and test including Python tests if simple.
11. Add README/docs snippet for running the scanner.

Constraints:
- No credentials.
- No order placement.
- No secret logging.
- Keep output reasonably small by default.
- Do not break existing dashboard/tests.

Acceptance criteria:
- Scanner can run without Kalshi credentials.
- Uses status=open.
- Price parsing is tested.
- Expiration filter is tested.
- npm test passes.
- npm run lint passes.
- npm run build passes.

At the end, print changed files and verification results. If live Kalshi API is unreachable, tests/fixture mode should still pass.