# Arbiter

*A daily political briefing from Marcus — powered by Kalshi prediction markets.*

---

## What Is This

Arbiter is a daily report that surfaces Kalshi election markets that stop trading within 60 days, researched by Marcus with full polling-backed briefs.

Carlos opens the report and sees every qualifying complete market, with multi-contract candidate races collapsed into one race-level briefing card when the contracts share an `event_ticker`. Each card shows:
- The race and election date
- Marcus's TRADE or PASS verdict
- Market price vs Marcus's fair value
- Full analysis and polling sources

For candidate fields like LA Mayor, Arbiter keeps individual Kalshi contracts in state for tracking, but renders one race card with a candidate table instead of flooding the briefing with one card per candidate contract.

Carlos makes the final call. Marcus is the analyst, not the trader.

---

## MVP Scope (North Star)

**In scope for MVP:**
- Daily cron at 1:30PM ET
- Collector → Kalshi Elections API, finds election markets whose trading cutoff is within 60 days
- Marcus → full brief per market (polling + financial data)
- Generator → `index.html` matching the artifact design, 1200px max-width
- WhatsApp ping to Carlos on completion
- State continuation — Marcus resumes where he left off, doesn't restart

**Data sources (all free, no API key required unless noted):**
- **VoteHub API** — presidential approval, generic ballot (REST, no key)
- **Ballotpedia** — Senate, House, Governor, mayoral races
- **RaceToTheWH** — Senate, House, Governor race averages
- **Wikipedia** — mayorals, local races, historical context
- **Quinnipiac / Siena** — state-specific high-quality polls
- **MIT Election Lab + Dave Leip's Atlas** — historical baselines (download CSV)
- **OpenFEC API** — candidate financials (receipts, disbursements, cash on hand, top donors, outside spend). DEMO_KEY works, no key required.

**Data quality bar:** Marcus needs at least two independent sources before writing a brief. If VoteHub has approval numbers and Ballotpedia has the Senate race polling, that's enough.

**Out of scope:**
- Vercel, GitHub Pages, or any cloud deployment — this stays local on Carlos's machine
- Trading, order placement, portfolio sync
- Portfolio dashboards, filters, or non-briefing sections
- Non-US elections (until Ballotpedia/Wikipedia have reliable polling for them)
- Any market without polling data (admin/government-action markets excluded)

**MVP is the ceiling until explicitly expanded.** Do not add features that aren't in the spec. If something seems important, surface it in `docs/bugs.md` or `docs/currentstate.md` as a proposed addition.

---

## How It Works

```
1:30PM — Cron fires
    │
    ▼
collector.py
  → Queries Kalshi Elections API via `/series?category=Elections` (no auth required for discovery)
  → For each election, fetches all candidate contracts via `/markets?series_ticker=`
  → Filters on `close_time` / `expiration_time` so the 60-day window uses the real trading cutoff
  → `_is_race_market()` pattern-matches question text to exclude event contracts (dropout, endorsement, resignation, binary appointment questions) — only passes markets where polling-based math actually applies
  → Stores `event_date` (election date when present), `candidate_name`, and `event_ticker`
  → Updates state/analysis.json
    │
    ▼
engine.py (Marcus)
  → Reads state/analysis.json
  → Per market or grouped race: VoteHub/polling context + OpenFEC financials → fair value → delta → verdict
  → For supported mayoral races, evaluates the full candidate field together and writes candidate-level FV back to each contract
  → Writes brief to state/analysis.json (status: complete)
    │
    ▼
generator.py
  → Reads all complete markets
  → Groups supported multi-contract races by event_ticker
  → Renders output/index.html
  → Prints "Done"; Hermes cron delivers stdout to WhatsApp
```

**State:** All scripts read/write `state/analysis.json`. Marcus skips `complete` markets, resumes `analyzing`, starts new `discovered` markets. The report always continues from where it left off. Candidate contracts retain market-level fields (`ticker`, `candidate_name`, `event_ticker`, `event_date`, price, FV, verdict) even when the HTML output groups them into a race card.

---

## File Structure

```
arbiter/
├── state.py            # State read/write/upsert/transition helpers
├── collector.py        # Step 1: Kalshi market discovery
├── engine.py           # Step 2: Marcus analysis
├── generator.py       # Step 3: HTML generation
├── state/
│   └── analysis.json   # Market state tracker (source of truth)
├── output/
│   └── index.html      # The report (what Carlos opens)
├── README.md           # This file
└── docs/
    ├── agents.md       # Who does what + handoff protocol
    ├── currentstate.md # Project state + state machine + roadmap
    ├── bugs.md         # Known issues, limitations, edge cases
    ├── CHANGELOG.md    # What changed
    └── artifact-reference/
        └── artifact.html  # Design spec (the reference artifact)
```

---

## Setup

### Prerequisites
- Python 3.9+
- Hermes cron configured
- Kalshi credentials stored externally at `~/Documents/Obsidian Vault/credentials/Kalshi.md` for future authenticated work (not needed for current public market discovery)

### Running locally
```bash
cd /Users/carlosmac/arbiter

# One-time cleanup after the Elections-category expiry-filter fix
rm -f state/analysis.json

# Step by step
python3 collector.py
python3 engine.py
python3 generator.py

# Or run the full pipeline exactly like cron does
python3 ~/.hermes/scripts/arbiter-daily.py
```

### Cron (after setup)
Daily at 1:30PM ET via Hermes cron job `799f5a1b57ba` (`Arbiter Daily Political Briefing`). It runs `~/.hermes/scripts/arbiter-daily.py` with `no_agent=true`, so there is no LLM overhead; stdout is delivered to WhatsApp.

---

## Road to MVP

Each task is a self-contained 5-minute coding session. Do them in order.

| # | Task | File | What |
|---|---|---|---|
| 1 | Define state schema | `state/analysis.json`, `state.py` | Schema + read/write/transition helpers **DONE** |
| 2 | Write Collector | `collector.py` | Kalshi API, ≤60d markets, write to state **DONE** |
| 3 | Write Engine (polling) | `engine.py` | VoteHub API + Ballotpedia polling fetch, FV, verdict **DONE** |
| 4 | Write Engine (financials) | `engine.py` | OpenFEC API — receipts, top donors, outside spend **DONE** |
| 5 | Write Generator | `generator.py` | Read complete markets → `output/index.html` **DONE** |
| 6 | First full run | — | Run pipeline end-to-end, verify output **DONE** |
| 7 | WhatsApp ping | `generator.py` | Send "Done" on completion **DONE** |
| 8 | Hermes cron | — | Schedule 1:30PM ET, test with dry run **DONE** |
| 9 | Continuation logic | `engine.py` | Skip complete, resume analyzing on restart **DONE** |
| 10 | Error handling | `collector.py`, `engine.py` | Alert on failure, don't skip steps **DONE** |
| 11 | Race-level cards | `collector.py`, `engine.py`, `generator.py`, `state.py` | Group multi-contract races by `event_ticker`, analyze mayoral fields together, render one candidate-table card **DONE** |
| 12 | Elections expiry filter fix | `collector.py`, `state.py`, `generator.py` | Discover via Elections events, use trading cutoff for the 60-day window, exclude approval/generic-ballot titles, persist `event_date` **DONE** |
| 13 | Event contract filter | `collector.py` | `_is_race_market()` question-text pattern filter — exclude dropout/endorsement/resignation markets, only pass markets with polling data to analyze **DONE** |

*Arbiter stays local. No Vercel, no deployment — this is a local tool on Carlos's machine, served via localhost.*

---

## Forecast Model Reporting (Post-MVP)

Phases 1-5 of the forecast-model architecture are now in place. Arbiter still keeps the existing top-level report fields (`marcus_fv`, `delta`, `verdict`, `context`, `analysis`, `sources`, `financials`, `status`) for compatibility, but completed entries can now also carry a nested `forecast` block generated from the shared stdlib-only `forecast/` package.

Phase 5 wires those forecast blocks into the live report path without creating a second model flow. Approval and generic-ballot threshold markets now get conservative binary forecast summaries when VoteHub polling is usable, LA Mayor grouped candidate cards now carry top-two-compatible forecast blocks built from the hardcoded field polling inputs, and the HTML cards render median probability, range, confidence, and data quality inside the existing dark-navy portrait-card layout.

OpenFEC financial data remains part of congressional readiness inputs inside the forecast layer. This is still market-specific briefing infrastructure only: there is no national-map UI, unsupported market types without a polling source still omit forecast blocks, and live presidential/congressional report wiring beyond today's supported inputs remains deferred.

Latest verification: `python3 -m unittest discover -s tests -p 'test*.py'` → `Ran 35 tests in 0.127s` / `OK`; `python3 -m py_compile collector.py state.py engine.py generator.py forecast/*.py` → success.

---

## Design Reference

The report matches `docs/artifact-reference/artifact.html`:
- Dark background (#0D0F1A)
- Blue primary (#60A5FA) + amber accent (#FCD34D)
- Card-based layout, centered, with portrait-width brief cards paginated in groups of 3 when needed
- Sticky header with "Arbiter Political Briefing ● Live"
- Per-card: kalshi badge, race title, election date, verdict tag, price row, analysis, sources
- Race cards: one collapsed card for a multi-contract race, with a candidate table showing market price, Marcus FV, edge, and signal

---

*See agents.md for the technical specification. See currentstate.md for the state machine and roadmap.*
