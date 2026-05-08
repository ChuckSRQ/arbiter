# Bugs & Open Questions

*Known issues, unresolved decisions, and things to solve before they block progress.*

---

## Known Limitations

### Wikipedia polling for non-US elections
Wikipedia has reliable polling tables for US federal/state elections. For UK general elections, Canadian provincial races, etc. — polling tables exist but structure varies and may not cover every race Marcus needs.

**Impact:** MVP is US-only. Non-US markets are Phase 4 roadmap.

**Workaround:** Ballotpedia covers some international races. If neither has coverage, note "no recent polling" and Marcus estimates from fundamentals.

---

### OpenFEC rate limits
OpenFEC allows 1,000 calls/hour on DEMO_KEY. With ≤5 markets per run and ~10 calls per market (candidate search, financials, top donors, outside spend), that's well within limits.

**Impact:** Very low. Only an issue if running multiple cron jobs per hour.

**Workaround:** If rate limit is hit, engine falls back to candidate search only (receipts + disbursements), skips top donors and outside spend for that run.

---

### RealClearPolling requires browser automation
RealClearPolling tables are scrapeable but use dynamic JS. Terminal HTTP (curl/urllib) returns 403. Browser automation (Playwright) works but adds dependency complexity.

**Impact:** Low — we have Ballotpedia + RaceToTheWH as alternatives. RealClearPolling is tertiary.

**Workaround:** Keep RealClearPolling in reserve for specific race gaps. Don't add Playwright to MVP unless Ballotpedia + RaceToTheWH both miss a race that has RCP coverage.

---

### Silver Bulletin blocks terminal HTTP
Silver Bulletin returns 403 on direct `urllib`/`requests` calls from terminal. Browser-based access (`browser_navigate`) works.

**Impact:** In a cron session without browser access, Silver Bulletin is unreachable.

**Workaround:** Wikipedia is primary. Silver Bulletin is tertiary fallback. Cron session uses Wikipedia + pollster sites only. If neither is available, the brief notes "no recent polling" and Marcus estimates from fundamentals.

---

### Kalshi political markets use `status=active`, not `status=open`
The default `/markets?status=open` returns only parlays (NBA, MLB props). All political markets use `status=active` and require `series_ticker` filter.

**Impact:** `collector.py` must pass both `series_ticker` and `status=active` for political queries.

**Known series tickers:**
- Presidential: `PRES-*`
- Senate: `SENATE*`
- House: `HOUSE*`
- Gubernatorial: `GOVPARTY*`
- Mayorals: `KXMAYORLA`, etc.

Full list in `kalshi-integration` skill `references/political-market-discovery.md`.

---

### 60-day window still misses some federal election markets
Federal Senate/House/Presidential markets resolve in 2027-2029. Even with a 60-day window, they're outside the horizon until much closer to the election.

**Impact:** MVP may show 0-2 markets some days if no state-level races are within 60 days of expiry.

**Workaround:** If 0 markets qualify, generator produces a "No markets in range today" card and cron still sends WhatsApp ping.

---

### API key not yet provided
Carlos will provide the Kalshi API key before collector.py is built.

**Impact:** Collector can't be tested until key is available.

**Workaround:** Document the credential storage location (`~/Documents/Obsidian Vault/credentials/Kalshi.md`) and the exact format the scripts expect.

---

## Open Questions (Unresolved)

| Question | Status | Blocking MVP? |
|---|---|---|
| Verdict tag PASS styling — blue? grey? muted? | Open | No |
| WhatsApp message — just "done" or one-line summary? | Open | No |
| If 0 markets qualify, show empty report or "no markets today"? | Open | No |
| Phase 3 hosting — Vercel account + domain? | Open | Yes (Phase 3 only) |
| Max markets per run — 5 hard cap or soft cap? | Open | No |

---

## Pitfalls to Avoid

1. **Don't use `status=open` for political markets.** Will return 0 political markets. Use `status=active` + `series_ticker`.

2. **Don't start polling research from scratch each day.** Read `state/analysis.json` first. Skip `complete`, resume `analyzing`, start `discovered`.

3. **Don't filter briefs by verdict.** Every qualifying market gets a full brief. TRADE or PASS is Marcus's signal, not Carlos's decision.

4. **Don't commit API keys or credentials to git.** Store in `~/Documents/Obsidian Vault/credentials/Kalshi.md`. Reference the path in env vars.

5. **Don't overengineer.** MVP only. Phase 2, 3, 4 are roadmap — not committed until Carlos approves them.

---

## Wishlist (Not Bugs — Future Ideas)

- Historical delta tracking to see how Marcus's FV accuracy evolves
- Export to PDF for archival
- Email delivery alternative to WhatsApp
- RealClearPolling integration (Playwright) — only if Ballotpedia + RaceToTheWH have a coverage gap

These belong in `currentstate.md` as Phase 4 candidates, not in MVP.

---

*See currentstate.md for roadmap. See agents.md for technical spec.*