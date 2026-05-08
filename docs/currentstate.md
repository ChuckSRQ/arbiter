# Current State

*Where the project is right now, the state machine, and the roadmap.*

---

## Status: Phase 1 Complete — MVP Running

Core pipeline complete. All 10 original MVP tasks done. Daily cron fires at 1:30PM ET. Race-level grouping for multi-contract candidate markets is now implemented for mayoral races, and collector discovery now comes directly from Kalshi's Elections category with trading-cutoff date filtering.

---

## State Machine

Every market in `state/analysis.json` moves through states:

```
discovered → analyzing → complete
                         ↳ stale (if new polling data arrives)
```

| State | Meaning | Engine action |
|---|---|---|
| `discovered` | Market found by Collector, not yet analyzed | Move to `analyzing`, start research |
| `analyzing` | Marcus is working on it | Continue research, don't skip |
| `complete` | Brief written, market on report | Skip on next cron run |
| `stale` | Market was complete but new polling may change FV | Re-enter `analyzing` for delta recalculation |

**Market exits the pipeline at `complete` (or `stale`).** The report only shows `complete` markets. Multi-contract races still store each contract as an individual market row, but the generator can collapse supported races into one briefing card keyed by `event_ticker`.

---

## What's Built vs What's Planned

### Built
- `docs/agents.md` — agent roles, handoffs, brief specification
- `README.md` — project overview and MVP scope (root)
- `docs/currentstate.md` — project state + state machine
- `docs/CHANGELOG.md` — change log
- `docs/bugs.md` — known limitations, resolved questions, pitfalls
- `docs/artifact-reference/artifact.html` — design spec
- `state.py` — state read/write/upsert/transition helpers
- `collector.py` — Kalshi market discovery via `/events?category=Elections` (public API, rate-limited, 0.35s delay) with title-based exclusions, trading-cutoff filtering, and `event_ticker` / `candidate_name` / `event_date` capture for candidate-contract races
- `engine.py` — polling + financials analysis engine (VoteHub fetch, OpenFEC financials, FV heuristic, verdict, brief writing) with grouped mayoral race analysis
- `generator.py` — HTML report generator from complete market state; groups supported multi-contract races into one race card with a candidate table
- `~/.hermes/scripts/arbiter-daily.py` — Hermes cron pipeline runner (collector → engine → generator, non-zero failure alerts)
- `state/analysis.json` — populated market state with completed briefs
- `output/index.html` — generated report output

### In Progress
- (all core tasks complete)

### Planned (not built)
- (no remaining MVP tasks)

### Post-MVP candidates
- Broader polling-source coverage beyond VoteHub/approval/generic ballot when reliable free sources are available

---

## MVP Roadmap

**Phase 1 — Core Pipeline (now)**
- [x] `state/analysis.json` — schema + `state.py` read/write/transition helpers
- [x] `collector.py` — public Kalshi API, pollable series filter, ≤60d window, rate-limited
- [x] `engine.py` — VoteHub API polling fetch + OpenFEC financials, FV calculation, verdict, full brief JSON
- [x] `generator.py` — index.html from brief JSON, artifact design
- [x] `output/index.html` — first generated report
- [x] First full pipeline run verified
- [x] WhatsApp "Done" ping

**Phase 2 — Localhost Cron**
- [x] Hermes cron job at 1:30PM ET (`arbiter-daily.py` via no_agent script, WhatsApp delivery)
- [x] Continuation logic (don't restart analysis from scratch)
- [x] Error handling with WhatsApp failure alert (non-zero exit triggers Hermes error notification)

**Phase 3 — Brief Quality Improvements**
- [x] Race-level cards for multi-contract candidate races keyed by `event_ticker`
- [x] Mayor race analysis groups all contracts in the race before assigning candidate-level FV/edge/verdict
- [x] LA Mayor 2026 verified as one race card with 10 candidates instead of 10 separate candidate cards
- [x] Collector discovery switched from hardcoded prefix guessing to Kalshi Elections events taxonomy
- [x] Collector now uses market trading cutoff (`close_time` / `expiration_time`) for the 60-day window while storing only `event_date` in state for display
- [x] Election-adjacent approval/generic-ballot titles are excluded inside the Elections category

**Stays Local (no deployment planned)**
- No Vercel, no GitHub Pages, no cloud hosting
- Arbiter runs on Carlos's machine via localhost

---

## Decisions Made

| Decision | Resolution |
|---|---|
| Stack | Python + static HTML. No Next.js/DB for MVP. |
| Cron | Hermes job `799f5a1b57ba`, `no_agent=true`, schedule `30 13 * * *`, script `~/.hermes/scripts/arbiter-daily.py` |
| Polling sources | VoteHub API (primary), Ballotpedia (secondary), RaceToTheWH, Wikipedia (mayorals), Quinnipiac/Siena (tertiary). Not locked to any single source. |
| Financial data | OpenFEC API — candidate receipts, disbursements, cash on hand, top donors, outside spend. DEMO_KEY works, no key required. |
| Market filter | Kalshi Elections category only; include markets whose trading cutoff is within 60 days; exclude election-adjacent approval/generic-ballot titles |
| Full briefs | Every qualifying market gets a full brief. No filtering by verdict. |
| Verdict tag | TRADE (amber) or PASS (grey) — on its own line below election date |
| Report minimum | Always show 3-5 political briefs per day. If fewer markets qualify, show what's available. Even PASS verdicts show full polling + analysis. Carlos decides, not Marcus. |
| WhatsApp ping | "Done" on completion — no summary, just confirmation |
| Multi-contract races | Keep each Kalshi contract in state for tracking, but group supported candidate races by `event_ticker` at render time. Mayor races are analyzed as a candidate field, not isolated binary contracts. |

---

## What's Still Open

- Existing `state/analysis.json` snapshots produced before the Elections-category expiry-filter fix should be rebuilt once so title exclusions and date fields are clean.
- Wikipedia page URL structure for non-US elections (low priority, US-only for now)
- Senate, House, and Governor races still need dedicated race-level analysis before they should be grouped like mayorals.

All open questions go in `bugs.md` or get resolved before that phase is started.

---

*See agents.md for the technical handoff protocol. See README.md for project overview.*
