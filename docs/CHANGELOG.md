# Changelog

*What changed, when, and why. Updated after each meaningful update to the project.*

---

## [Unreleased] — Wikipedia Polling + ≤6% Filter + Alert System

### Added
- `engine.py` — `WikipediaPoller` class and `_scrape_wiki_polls()` that auto-fetches Wikipedia polling for mayorals, international elections, and any unsupported race type when higher-priority sources (VoteHub/Ballotpedia/RaceToTheWH) return no data. Candidate name aliases for LA Mayor. ≤6% filter in `_filter_6pct()`.
- `engine.py` — `_wikipedia_url()` constructs Wikipedia article URLs for LA Mayor (`2026_Los_Angeles_mayoral_election`), Armenia parliamentary, Colombia presidential. Returns `None` for unknown election types.
- `engine.py` — `m_type == "other"` path now tries Wikipedia polling automatically before falling back to market-price FV + `_POOL_FAILED_` marker.
- `collector.py` — `discover_series()` now uses `/events?category=Elections` pagination (not `/series`) to match actual Kalshi API taxonomy. Extracts unique `series_ticker` from each event.
- `tests/test_wikipedia_polling.py` — unit coverage for URL construction, candidate name normalization, 6% filtering, and poll table row parsing.
- `tests/test_6pct_filter.py` — unit coverage for ≤6% candidate exclusion from candidate tables and analysis text, plus polling failure detection via placeholder text patterns.
- `tests/test_market_expiry_filter.py` — fixed tests to match `_parse_close_date()` priority (expected_expiration_time first), fixed `discover_series` mock for `/events` pagination, fixed `CollectTests` event dates for 60-day window.

### Changed
- `collector.py` — `discover_series()` paginates through `/events` (not `/series`), extracting `series_ticker` from each event dict. Removes `ALLOWED_TAGS` filtering since the Elections category already scopes to political races.
- `collector.py` — `_is_race_market()` title patterns unchanged; matchup questions filtered out as designed.
- `engine.py` — `m_type` detection changed from `if "KXMAYOR" in t` to `if "MAYOR" in t` to cover `KXLAMAYOR1R`, `KXLAMAYORMATCHUP`, etc. without matching non-mayor strings.
- `tests/test_market_expiry_filter.py` — updated `ParseCloseDateTests` to reflect `_parse_close_date()` priority (expected_expiration_time first, close_time fallback). Updated `CollectTests` event dates and title to match new behavior.
- `collector.py` — `_is_race_market()` filter using Signal 1 (question text pattern matching) to exclude event contracts (dropout, endorsement, resignation, binary appointment questions) and only pass markets with actual candidate races and polling data to analyze. Integrated after the 60-day cutoff check in `_fetch_and_filter_series()`. When in doubt, the market is excluded.
- `forecast/electoral.py` — Phase 4 exact Electoral College helper that turns per-state presidential win probabilities into a deterministic win-probability summary without adding any map/report UI.
- `tests/test_forecast_phase4.py` — unit coverage for presidential-state adapter labeling, congressional no-poll fallbacks, OpenFEC-style financial-direction effects, fundamentals-dominant low-confidence markers, and deterministic Electoral College summaries.
- `forecast/adapters.py` — Phase 3 forecast adapters for binary head-to-head, multicandidate plurality, and top-two races, with deterministic intervals plus uncertainty-aware verdict helpers that preserve top-level `marcus_fv` / `delta` / `verdict` compatibility.
- `tests/test_forecast_adapters.py` — unit coverage for binary probability monotonicity, ordered intervals, plurality win-probability totals, top-two advance behavior, uncertainty-aware PASS verdicting, and adapter output compatibility fields.
- `forecast/polling.py` — Phase 2 weighted polling-average engine with sample-size, recency, population, pollster-quality, and sponsor/internal weighting plus metadata hooks for later state/cache reuse.
- `tests/test_forecast_polling.py` — unit coverage for poll weighting, mild pollster discounts, stale-poll decay, sponsor/internal discounts, and empty-poll safety.
- `forecast/` package — Phase 1 forecast-model foundation with shared `Race` / `Candidate` / `Poll` / `Forecast` dataclasses, race classification helpers, and stdlib-only calibration loading.
- `calibration/base.json`, `calibration/polling.json`, `calibration/race_models.json` — manual forecast calibration constants (`manual-2026-05-09`) for later daily-engine use.
- `tests/test_forecast_foundation.py` — unit coverage for calibration loading and race classification.
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
- `engine.py` — grouped mayoral candidate markets now append a candidate-specific top-two forecast summary instead of reusing the forecast leader's note across every contract in the race.
- `tests/test_forecast_reporting_integration.py` — added a deterministic regression covering grouped mayoral forecast-note attachment so each candidate keeps the analysis text that matches its own nested forecast block.
- `engine.py` — Phase 5 integration now attaches nested `forecast` blocks to supported completed entries, keeps existing top-level market fields intact, adds concise uncertainty text to analysis output, and uses the shared `forecast/` adapters for conservative approval/generic threshold forecasts plus LA Mayor top-two-compatible candidate snapshots.
- `generator.py` — existing cards now render forecast median/range/confidence/data-quality details, and grouped race cards show compact per-candidate forecast summaries without breaking the portrait-card / 3-column layout.
- `README.md`, `docs/currentstate.md`, `docs/bugs.md` — replaced the Phase 5-next handoff note with a Phase 5 completion handoff, including deferred scope and verification output.
- `forecast/types.py`, `forecast/adapters.py`, `forecast/__init__.py` — Phase 4 readiness adds `RaceFundamentals` / `OutcomeFundamentals`, supports `presidential_state` and `congressional` in `adapt_race_forecast`, blends sparse polling with conservative fundamentals inputs, and marks fundamentals-dominant outputs as low confidence.
- `README.md`, `docs/currentstate.md`, `docs/bugs.md` — replaced the Phase 4-next handoff note with a concise Phase 4 completion handoff and called out Phase 5 report-path integration as the remaining step.
- `README.md`, `docs/currentstate.md`, `docs/bugs.md` — replaced the Phase 2 handoff note with a concise Phase 3 adapter handoff and called out Phase 4 presidential/congressional readiness as the next model step.
- `forecast/types.py`, `forecast/__init__.py` — added a shared `PollingAverage` type plus explicit internal-poll support on normalized `Poll` objects for the Phase 2 engine.
- `README.md`, `docs/currentstate.md`, `docs/bugs.md` — replaced the Phase 1-only handoff note with a concise Phase 2 polling-average handoff and called out Phase 3 as the next step.
- `collector.py` — restored `discover_series()` compatibility and switched series discovery to the Elections `/events` pagination path already expected by the existing test suite and docs.
- `README.md`, `docs/currentstate.md`, `docs/bugs.md` — added a concise Phase 1 forecast-model handoff note and called out that Phase 2 is still the polling-average engine.
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
- Phase 5 verification: `python3 -m unittest discover -s tests -p 'test*.py'` → `Ran 35 tests in 0.127s` / `OK`; `python3 -m py_compile collector.py state.py engine.py generator.py forecast/*.py` → success
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
