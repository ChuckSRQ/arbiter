# Current State

*Where the project is right now, the state machine, and the roadmap.*

---

## Status: MVP Running + Forecast Phase 5 Reporting Integrated + Event Contract Filter

Core pipeline complete. Collector now filters out event contracts (dropout, endorsement, resignation questions) via `_is_race_market()` using question text pattern matching, passing only markets with actual candidate races and polling data for Marcus to analyze.

### Latest verification
- `python3 -m unittest discover -s tests -p 'test*.py'` → `Ran 35 tests in 0.127s` / `OK`
- `python3 -m py_compile collector.py state.py engine.py generator.py forecast/*.py` → success

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
- `engine.py` — polling + financials analysis engine (VoteHub fetch, OpenFEC financials, FV heuristic, verdict, brief writing) with grouped mayoral race analysis plus nested forecast-block integration and uncertainty-aware brief text
- `generator.py` — HTML report generator from complete market state; groups supported multi-contract races into one race card with a candidate table and renders compact forecast summaries on market/race cards
- `forecast/polling.py` — pure-Python polling-average engine for normalized polls with configurable sample-size, recency, population, pollster-quality, and sponsor/internal weights plus metadata hooks (`poll_count`, `as_of_date`, `data_quality`, `total_weight`)
- `forecast/adapters.py` — forecast adapters for binary head-to-head, multicandidate plurality, top-two, presidential-state, and congressional races, including conservative fundamentals blending and low-confidence markers when fundamentals dominate
- `forecast/electoral.py` — exact Electoral College helper for deterministic presidential state-map probability summaries in the forecast layer only
- `~/.hermes/scripts/arbiter-daily.py` — Hermes cron pipeline runner (collector → engine → generator, non-zero failure alerts)
- `state/analysis.json` — populated market state with completed briefs
- `output/index.html` — generated report output

### In Progress
- (all core tasks complete)

### Planned (not built)
- (no remaining MVP tasks)

### Post-MVP candidates
- Broader polling-source coverage beyond VoteHub/approval/generic ballot when reliable free sources are available

### Forecast model roadmap
- **Phase 1 complete:** `forecast/` package added with shared race/candidate/poll/forecast dataclasses, race classification helpers, and stdlib-only calibration loading from `calibration/`.
- **Phase 2 complete:** weighted polling averages now compute from normalized polls using sample size, recency decay, population type, pollster quality, and mild sponsor/internal discounts while returning metadata hooks for later state/cache reuse.
- **Phase 3 complete:** supported race adapters now turn polling averages into binary win probabilities, multicandidate plurality win probabilities, and top-two advance probabilities while preserving top-level `marcus_fv`, `delta`, and `verdict` compatibility.
- **Phase 4 complete:** the forecast layer now supports `presidential_state` and `congressional`, conservative fundamentals fallbacks for sparse/no-poll races, OpenFEC-style financial inputs, lower-confidence/data-quality markers when fundamentals dominate, and a deterministic Electoral College helper.
- **Phase 5 complete:** `engine.py` now attaches forecast blocks where supported, market briefs mention uncertainty concisely, and `generator.py` renders median/range/confidence/data-quality details without changing the existing card grid or grouped-race output.

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
- Unsupported `other` markets still omit forecast blocks instead of inventing unsupported probabilities; they remain covered by the existing PASS/no-source fallback.
- LA Mayor forecast blocks currently represent a top-two-compatible snapshot built from the hardcoded field polling, while top-level `marcus_fv` stays on the existing market heuristic for compatibility with today's grouped card flow.
- Senate, House, Governor, and presidential state markets still need live polling/source wiring in the engine before the Phase 4 readiness layer can power those report cards end to end.
- National-map rendering remains intentionally out of scope; the Electoral College helper is forecast-layer-only support for later market briefs.

All open questions go in `bugs.md` or get resolved before that phase is started.

---

*See agents.md for the technical handoff protocol. See README.md for project overview.*
