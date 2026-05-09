# Bugs & Open Questions

*Known issues, unresolved decisions, and things to solve before they block progress.*

---

## Known Limitations

### Threshold-market forecasts are intentionally conservative
Phase 5 now writes `forecast` blocks into supported completed entries and renders them in the report, but approval/generic-ballot contracts still use a synthetic YES/NO polling transform because those Kalshi markets resolve on thresholds, not direct candidate-vs-candidate outcomes.

**Impact:** The nested forecast block is useful as an uncertainty-aware briefing aid, but it should be read as a conservative directional probability layer rather than as a second precision model for threshold contracts.

**Workaround:** Keep using the existing top-level `marcus_fv`, `delta`, and verdict fields as the primary trading signal; treat the forecast block as supporting range/confidence context.

---

### LA Mayor forecast block is a top-two snapshot, not a final win model
Grouped mayor race cards now carry forecast blocks built from the existing hardcoded LA field polling, but the current adapter path is intentionally a top-two-compatible snapshot because that is the practical fit for the sparse public field data.

**Impact:** Top-level mayor `marcus_fv` remains on the existing grouped-race heuristic for report compatibility, while the nested forecast block captures who looks strongest to advance under current sparse polling.

**Workaround:** Read the forecast block as a structured uncertainty cue for the candidate field, not as a replacement for the current market heuristic until fuller live mayoral source wiring is added.

---

### No national map/report UI by design
Phase 4 adds only forecast-layer readiness for presidential state markets. The new Electoral College helper remains intentionally backend-only after Phase 5.

**Impact:** None. Arbiter remains a market-specific briefing tool, not a national dashboard.

**Workaround:** Keep any presidential summary logic inside `forecast/` helpers until a later phase explicitly expands product scope.

---

### Wikipedia polling for non-US elections
Wikipedia has reliable polling tables for US federal/state elections. For UK general elections, Canadian provincial races, etc. — polling tables exist but structure varies and may not cover every race Marcus needs.

**Impact:** MVP is US-only. Non-US markets are still outside the approved forecast/reporting phases.

**Workaround:** Ballotpedia covers some international races. If neither has coverage, note "no recent polling" and Marcus estimates from fundamentals.

---

### Unsupported `other` markets still omit forecast blocks
If a market still falls into the no-polling-source fallback path, Arbiter completes the brief and preserves state continuity, but it does not fabricate a nested forecast block.

**Impact:** Some markets will still render without forecast metadata until a real polling/source path exists for that contract type.

**Workaround:** Keep the current PASS/no-source fallback for those cards and only add new forecast coverage when a real source path is implemented.

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

## Open Questions (Resolved)

| Question | Resolution |
|---|---|
| Verdict tag PASS styling | Grey (#9CA3AF or similar muted tone) |
| WhatsApp message | "Done" — no summary, just confirmation |
| If 0 markets qualify | Still show 3-5 briefs. Marcus writes full analysis on all political markets regardless of verdict. Carlos decides, not Marcus. |

---

## Pitfalls to Avoid

1. **Don't use `status=open` for political markets.** Will return 0 political markets. Use `status=active` + `series_ticker`.

2. **Don't start polling research from scratch each day.** Read `state/analysis.json` first. Skip `complete`, resume `analyzing`, start `discovered`.

3. **Don't filter briefs by verdict.** Every qualifying market gets a full brief. TRADE or PASS is Marcus's signal, not Carlos's decision.

4. **Don't commit API keys or credentials to git.** Store in `~/Documents/Obsidian Vault/credentials/Kalshi.md`. Reference the path in env vars.

5. **Don't overengineer.** MVP only. Remaining forecast work stays scoped to the approved roadmap.

---

## Wishlist (Not Bugs — Future Ideas)

- Historical delta tracking to see how Marcus's FV accuracy evolves
- Export to PDF for archival
- Email delivery alternative to WhatsApp
- RealClearPolling integration (Playwright) — only if Ballotpedia + RaceToTheWH have a coverage gap

These belong in `currentstate.md` as future candidates, not in MVP.

---

*See currentstate.md for roadmap. See agents.md for technical spec.*
