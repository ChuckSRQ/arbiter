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
- Marcus → full brief per market (Wikipedia polling primary source)
- Generator → `index.html` matching the artifact design, 1200px max-width
- WhatsApp ping to Carlos on completion
- State continuation — Marcus resumes where he left off, doesn't restart

**Out of scope (roadmap):**
- Vercel/GitHub Pages deployment — localhost only for now
- Trading, order placement, portfolio sync
- Multiple page sections, filters, tabs
- Non-US elections (until Wikipedia has reliable polling for them)
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

| Phase | What |
|---|---|
| MVP (now) | Collector + Engine + Generator + localhost HTML + WhatsApp |
| Phase 2 | Deploy to Vercel, real URL |
| Phase 3 | Add non-US election markets |
| Phase 4 | Portfolio sync, trade recommendations |

*Roadmap is not a commitment. Each phase requires explicit approval from Carlos.*

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