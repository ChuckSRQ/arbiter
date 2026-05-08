# Changelog

## [Unreleased] - 2026-05-07

### Added

- Curated political series collection with explicit lists:
  - `TRACKER_SERIES`
  - `ELECTION_SERIES`
  - `ELECTION_WATCHLIST`
- New report sections: `onWatch`, `trackers`, `passes` alongside `opportunities`.
- New site sections: Opportunities, On Watch, and Pulse Check.
- Priority scoring via `calculateOpportunityScore()` using `edge * confidence * timeWeight`.
- Collector tests for tracker collapse and watchlist bypass behavior.

### Changed

- Collector rewritten to a 60-day default collection window with watchlist override support.
- Analysis engine classification tightened to `politics | tracker | other`.
- Tracker markets routed into dedicated tracker entries instead of election opportunity flow.
- Site cards simplified for no-trade and opportunity display, with on-watch candidate tables.
- Daily pipeline flow standardized: collector -> runner -> generator -> report JSON -> site render.

### Removed

- Portfolio collection from the daily runner pipeline.
- Portfolio display section from the dashboard main flow.
- Legacy hardcoded default market model behavior and obsolete market-type regex handling.
- Opportunity card `whatWouldChange` display and old pass-pill component.
