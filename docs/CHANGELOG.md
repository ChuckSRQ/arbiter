# Changelog

*What changed, when, and why. Updated after each meaningful update to the project.*

---

## [Unreleased] — MVP Development

### Added
- `collector.py`, `state.py` — persist Kalshi `event_ticker` and `candidate_name` so multi-contract races can be grouped without losing individual contract tracking.
- `engine.py` — mayoral race grouping and LA mayor candidate-field analysis keyed by `event_ticker`, with candidate-level Marcus FV, edge, and TRADE/PASS signals written back to each market.
- `generator.py` — race-level briefing cards for grouped candidate races, including a candidate table instead of one separate card per contract.
- `output/index.html` — regenerated report showing LA Mayor 2026 as one collapsed 10-candidate race card.
- `README.md` — project overview, MVP scope, file structure, roadmap
- `docs/agents.md` — agent roles, handoff protocol, brief specification
- `docs/currentstate.md` — project state, state machine, decisions made
- `docs/CHANGELOG.md` — this file
- `docs/artifact-reference/artifact.html` — design spec copied from `/Users/carlosmac/Desktop/artifact.html`
- `engine.py` — Task 3 polling analysis engine with VoteHub fetch, fair value heuristic, verdicting, and state transitions (`discovered/analyzing` → `complete`)
- `engine.py` — Task 4 OpenFEC financials integration with per-market `financials` population and OpenFEC source tracking
- `generator.py` — Task 5 HTML report generator reading complete markets from state and rendering artifact-matching cards to `output/index.html`
- `output/index.html` — generated sample report output
- Tasks 8, 10 completed — Hermes cron job (1:30PM ET, `arbiter-daily.py`, WhatsApp delivery), error handling with failure alert

### Changed
- `collector.py` — replaced hardcoded `/series` prefix gating with paginated `/events?category=Elections` discovery, switched expiry filtering to prefer `close_time` / `expiration_time`, and added title-based exclusions for approval-rating and generic-ballot markets.
- `state.py`, `generator.py` — state now carries `event_date` only; trading cutoff stays collector-internal for filtering and report cards use `event_date` for display.
- `README.md`, `docs/currentstate.md` — documented the Elections-category discovery flow, the event-date-only state fields, and the one-time state rebuild needed after this collector fix.
- `generator.py` — complete market rendering now groups supported multi-contract races by `event_ticker` before paginating cards, so briefing-card count reflects races/cards instead of raw contracts.
- `README.md`, `docs/currentstate.md`, `docs/CHANGELOG.md`, `docs/agents.md` — documented the race-level grouping behavior and mayoral analysis update.
- `generator.py` — wrapped CLI execution in try/except; on success prints `Generated {path}` and `Done`, on failure prints `ERROR: generator failed — ...` and exits non-zero.
- `README.md` — marked Task 6 (first full run), Task 7 (WhatsApp ping), and Task 9 (continuation logic) as **DONE** in roadmap table.
- `docs/currentstate.md` — checked off Phase 1 "First full pipeline run verified" and "WhatsApp 'Done' ping", checked off Phase 2 continuation logic, and updated in-progress/planned status items.
- `docs/agents.md` — expanded polling sources from Wikipedia-only to full table (VoteHub API primary, Ballotpedia secondary, RaceToTheWH, Wikipedia, Quinnipiac/Siena, MIT Election Lab, Dave Leip's Atlas). Added OpenFEC API for financial data. Added data quality bar (2 independent sources minimum).
- `docs/currentstate.md` — updated polling source decision to reflect full source list. Added OpenFEC financial data decision.
- `README.md` — updated MVP scope to mention polling + financial data. Added data sources list. Updated non-US elections note to include Ballotpedia.
- `docs/bugs.md` — added OpenFEC rate limit limitation. Added RealClearPolling browser automation limitation. Updated wishlist with RealClearPolling (tertiary/reserve). Removed Polymarket (PredictIt not integrated).
- `README.md` — marked Task 3 ("Write Engine (polling)") as DONE in roadmap table.
- `docs/currentstate.md` — moved engine polling work into Built and checked off Phase 1 engine item.
- `README.md` — marked Task 4 ("Write Engine (financials)") as DONE in roadmap table.
- `docs/currentstate.md` — updated Phase 1 engine checklist item to include OpenFEC financials and moved in-progress focus to generator work.
- `README.md` — marked Task 5 ("Write Generator") as DONE in roadmap table.
- `docs/currentstate.md` — moved generator/report output into Built and checked off Phase 1 generator/output items.
- `docs/agents.md`, `README.md`, `docs/currentstate.md` — synced docs to the completed MVP implementation: public Kalshi discovery, VoteHub/OpenFEC engine, cron runner, stdout-based WhatsApp delivery, and no remaining MVP tasks.

### Resolved
- Verdict tag PASS styling: grey (#9CA3AF)
- WhatsApp message: "Done" only, no summary
- If 0 markets qualify: still show 3-5 briefs with full polling + analysis. Carlos decides, not Marcus.

### Added
- `state.py` — state read/write/upsert/transition helpers (Task 1 complete)
- `state/analysis.json` — empty schema file
- `collector.py` — Kalshi market discovery via public API (Task 2 complete)

---

## Rules

- Every meaningful change gets an entry. Small typo fixes don't.
- Format: `### Added/Changed/Fixed/Removed` under the relevant version header.
- If a change affects multiple areas, mention it once with context, don't repeat it.
- Breaking changes get a dedicated note.

---

*See currentstate.md for the full roadmap. See README.md for MVP scope.*
