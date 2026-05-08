# Changelog

*What changed, when, and why. Updated after each meaningful update to the project.*

---

## [Unreleased] — MVP Development

### Added
- `docs/README.md` — project overview, MVP scope, file structure, roadmap
- `docs/agents.md` — agent roles, handoff protocol, brief specification
- `docs/currentstate.md` — project state, state machine, decisions made
- `docs/CHANGELOG.md` — this file
- `docs/artifact-reference/artifact.html` — design spec copied from `/Users/carlosmac/Desktop/artifact.html`
- `engine.py` — Task 3 polling analysis engine with VoteHub fetch, fair value heuristic, verdicting, and state transitions (`discovered/analyzing` → `complete`)
- `engine.py` — Task 4 OpenFEC financials integration with per-market `financials` population and OpenFEC source tracking
- `generator.py` — Task 5 HTML report generator reading complete markets from state and rendering artifact-matching cards to `output/index.html`
- `output/index.html` — generated sample report output

### Changed
- `generator.py` — wrapped CLI execution in try/except; on success prints `Generated {path}` and `Done`, on failure prints `ERROR: generator failed — ...` and exits non-zero.
- `README.md` — marked Task 6 (first full run), Task 7 (WhatsApp ping), and Task 9 (continuation logic) as **DONE** in roadmap table.
- `docs/currentstate.md` — checked off Phase 1 "First full pipeline run verified" and "WhatsApp 'Done' ping", checked off Phase 2 continuation logic, and updated in-progress/planned status items.
- `docs/agents.md` — expanded polling sources from Wikipedia-only to full table (VoteHub API primary, Ballotpedia secondary, RaceToTheWH, Wikipedia, Quinnipiac/Siena, MIT Election Lab, Dave Leip's Atlas). Added OpenFEC API for financial data. Added data quality bar (2 independent sources minimum).
- `docs/currentstate.md` — updated polling source decision to reflect full source list. Added OpenFEC financial data decision.
- `docs/README.md` — updated MVP scope to mention polling + financial data. Added data sources list. Updated non-US elections note to include Ballotpedia.
- `docs/bugs.md` — added OpenFEC rate limit limitation. Added RealClearPolling browser automation limitation. Updated wishlist with RealClearPolling (tertiary/reserve). Removed Polymarket (PredictIt not integrated).
- `README.md` — marked Task 3 ("Write Engine (polling)") as DONE in roadmap table.
- `docs/currentstate.md` — moved engine polling work into Built and checked off Phase 1 engine item.
- `README.md` — marked Task 4 ("Write Engine (financials)") as DONE in roadmap table.
- `docs/currentstate.md` — updated Phase 1 engine checklist item to include OpenFEC financials and moved in-progress focus to generator work.
- `README.md` — marked Task 5 ("Write Generator") as DONE in roadmap table.
- `docs/currentstate.md` — moved generator/report output into Built and checked off Phase 1 generator/output items.

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
