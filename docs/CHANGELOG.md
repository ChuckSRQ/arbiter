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

### Changed
- `docs/agents.md` — expanded polling sources from Wikipedia-only to full table (VoteHub API primary, Ballotpedia secondary, RaceToTheWH, Wikipedia, Quinnipiac/Siena, MIT Election Lab, Dave Leip's Atlas). Added OpenFEC API for financial data. Added data quality bar (2 independent sources minimum).
- `docs/currentstate.md` — updated polling source decision to reflect full source list. Added OpenFEC financial data decision.
- `docs/README.md` — updated MVP scope to mention polling + financial data. Added data sources list. Updated non-US elections note to include Ballotpedia.
- `docs/bugs.md` — added OpenFEC rate limit limitation. Added RealClearPolling browser automation limitation. Updated wishlist with RealClearPolling (tertiary/reserve). Removed Polymarket (PredictIt not integrated).

### Resolved
- Verdict tag PASS styling: grey (#9CA3AF)
- WhatsApp message: "Done" only, no summary
- If 0 markets qualify: still show 3-5 briefs with full polling + analysis. Carlos decides, not Marcus.

---

## Rules

- Every meaningful change gets an entry. Small typo fixes don't.
- Format: `### Added/Changed/Fixed/Removed` under the relevant version header.
- If a change affects multiple areas, mention it once with context, don't repeat it.
- Breaking changes get a dedicated note.

---

*See currentstate.md for the full roadmap. See README.md for MVP scope.*