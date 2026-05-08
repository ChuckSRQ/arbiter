# Arbiter

*A daily political briefing from Marcus — powered by Kalshi prediction markets.*

---

## What Is This

Arbiter is a daily report that surfaces Kalshi political/election markets expiring within 60 days, researched by Marcus with full polling-backed briefs.

Carlos opens the report and sees 3-5 markets, each with:
- The race and election date
- Marcus's TRADE or PASS verdict
- Market price vs Marcus's fair value
- Full analysis and polling sources

Carlos makes the final call. Marcus is the analyst, not the trader.

---

## MVP Scope (North Star)

**In scope for MVP:**
- Daily cron at 1:30PM ET
- Collector → Kalshi API, finds ≤60d election markets with polling
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

**Out of scope (roadmap):**
- Vercel/GitHub Pages deployment — localhost only for now
- Trading, order placement, portfolio sync
- Multiple page sections, filters, tabs
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
  → Queries Kalshi API (authenticated with Carlos's key)
  → Returns markets expiring ≤60 days
  → Updates state/analysis.json
    │
    ▼
engine.py (Marcus)
  → Reads state/analysis.json
  → Per market: Wikipedia polling → fair value → delta → verdict
  → Writes brief to state/analysis.json (status: complete)
    │
    ▼
generator.py
  → Reads all complete markets
  → Renders output/index.html
  → WhatsApp "Arbiter report ready" to Carlos
```

**State:** All scripts read/write `state/analysis.json`. Marcus skips `complete` markets, resumes `analyzing`, starts new `discovered` markets. The report always continues from where it left off.

---

## File Structure

```
arbiter/
├── collector.py       # Step 1: Kalshi market discovery
├── engine.py           # Step 2: Marcus analysis
├── generator.py       # Step 3: HTML generation
├── state/
│   └── analysis.json   # Market state tracker (source of truth)
├── output/
│   └── index.html      # The report (what Carlos opens)
└── docs/
    ├── README.md       # This file
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
- `kalshi_python_sync` installed
- Kalshi API key (stored in `~/Documents/Obsidian Vault/credentials/Kalshi.md`)
- Hermes cron configured

### Running locally
```bash
cd /Users/carlosmac/arbiter

# Step by step
python3 collector.py
python3 engine.py
python3 generator.py

# Or run the full pipeline
bash run_pipeline.sh
```

### Cron (after setup)
Daily at 1:30PM ET via Hermes cron. No manual intervention needed.

---

## Road to MVP

Each task is a self-contained 5-minute coding session. Do them in order.

| # | Task | File | What |
|---|---|---|---|
| 1 | Define state schema | `state/analysis.json` | Schema + read/write helpers |
| 2 | Write Collector | `collector.py` | Kalshi API, ≤60d markets, write to state |
| 3 | Write Engine (polling) | `engine.py` | VoteHub API + Ballotpedia polling fetch, FV, verdict |
| 4 | Write Engine (financials) | `engine.py` | OpenFEC API — receipts, top donors, outside spend |
| 5 | Write Generator | `generator.py` | Read complete markets → `output/index.html` |
| 6 | First full run | — | Run pipeline end-to-end, verify output |
| 7 | WhatsApp ping | `generator.py` | Send confirmation on completion |
| 8 | Hermes cron | — | Schedule 1:30PM ET, test with dry run |
| 9 | Continuation logic | `engine.py` | Skip complete, resume analyzing on restart |
| 10 | Error handling | `collector.py`, `engine.py` | Alert on failure, don't skip steps |

*Phase 2 (Vercel deploy) starts after all 10 are done. Each task requires explicit approval before moving to the next.*

---

## Design Reference

The report matches `docs/artifact-reference/artifact.html`:
- Dark background (#0D0F1A)
- Blue primary (#60A5FA) + amber accent (#FCD34D)
- Card-based layout, 1200px max-width, centered
- Sticky header with "Arbiter Political Briefing ● Live"
- Per-card: kalshi badge, race title, election date, verdict tag, price row, analysis, sources

---

*See agents.md for the technical specification. See currentstate.md for the state machine and roadmap.*