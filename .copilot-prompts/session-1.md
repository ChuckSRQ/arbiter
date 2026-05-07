You are working in /Users/carlosmac/users/carlosmac/arbiter on branch feat/roadmap-sessions.

Model instruction: use gpt-5.4 quality. You have 10 minutes. Be pragmatic and ship a working increment. Do NOT commit, push, create PRs, place trades, or touch any real Kalshi credentials.

Project: Arbiter — a private Kalshi intelligence dashboard. Next.js 16, React 19, TypeScript, Tailwind CSS 4. This is a separate project from AgentZeroth. Do not use AgentZeroth orange. Use deep indigo/electric-blue Virtual CFO-inspired styling.

Read first:
- AGENTS.md
- README.md
- docs/roadmap.md
- src/app/page.tsx
- src/app/globals.css

Session 1 goal: Project Scaffold + Static Dashboard Shell.

Implement a polished static dashboard shell using mocked data only. No live Kalshi API, no auth, no cron.

Required UI:
- App shell with Arbiter branding and private terminal / financial report feel.
- Tabs or tab-like sections: Today, Opportunities, Portfolio, Evidence, Archive.
- Today tab should show top 3-5 opportunities from mock data.
- Include an explicit no-trade state somewhere, because no trade is valid.
- Show market cards with: ticker, title, action, current Kalshi price, Marcus fair value, edge, confidence, reason, evidence count.
- Show portfolio summary with mock exposure/P&L and hold/reduce/exit examples.
- Show evidence section with mock polling/F1/source links.
- Show archive cards for prior daily reports.

Design constraints:
- Deep indigo shell #1B1B4A or darker.
- Electric blue accent #3B82C4.
- Warm off-white/sand text.
- Green for favorable edge/profit.
- Red for exit/risk.
- Amber only for caution.
- No grey body text; avoid neutral grey UI.
- No AgentZeroth orange.

Technical constraints:
- Keep it simple. You may put mock data and components in src/app/page.tsx if fastest, or split components if helpful.
- Use TypeScript types for mock report data.
- Do not add unnecessary dependencies.
- Preserve Next.js 16 compatibility.
- Run npm run lint and npm run build before finishing if time allows.

Acceptance criteria:
- npm run lint passes.
- npm run build passes.
- Dashboard makes it obvious Arbiter is an edge filter, not a broad market screener.
- No secrets or real credentials.

At the end, print a concise summary of files changed and verification results.