# Arbiter — Agents

*Who does what, how they talk to each other, and where to find things.*

---

## The Team

| Agent | Role |
|---|---|
| **Cron Runner** | Hermes script — runs the daily pipeline at 1:30PM ET and delivers stdout to WhatsApp |
| **Collector** | `collector.py` — queries public Kalshi API, surfaces qualifying political markets |
| **Marcus / Engine** | `engine.py` — polling + financial research, fair value, verdict, full brief generation |
| **Generator** | `generator.py` — takes complete briefs, groups supported multi-contract races, renders `output/index.html`, prints `Done` |

---

## Marcus

Marcus is implemented by `engine.py`, the reasoning layer. He does not scrape Kalshi markets and he does not generate HTML. He reads market state, fetches polling/financial evidence, computes fair value, and writes a structured brief back to state.

**Marcus's inputs:**
- Market ticker (e.g. `KXMAYORLA-26JUN02`)
- Candidate name and `event_ticker` when Kalshi exposes a candidate-contract race
- Market title, expiry date, market price (from Collector)
- Polling data (see sources below)
- Financial data: candidate receipts, disbursements, top donors, outside spending (OpenFEC API)

**Marcus's outputs (per market):**
```json
{
  "ticker": "KXMAYORLA-26JUN02",
  "title": "Los Angeles Mayoral Primary",
  "election_date": "2026-06-02",
  "verdict": "TRADE | PASS",
  "market_price": 57,
  "marcus_fv": 65,
  "delta": 8,
  "context": "Full analysis paragraph.",
  "analysis": "Full reasoning paragraph.",
  "sources": [
    {"label": "VoteHub polling", "url": "..."},
    {"label": "OpenFEC financials", "url": "..."},
    {"label": "Ballotpedia", "url": "..."},
    {"label": "Kalshi market", "url": "..."}
  ],
  "status": "complete"
}
```

For supported multi-contract races, Marcus analyzes the full candidate field together, then writes candidate-level `marcus_fv`, `delta`, and `verdict` back to each individual Kalshi contract. The individual market rows remain the source of truth for tracking; the generator decides whether they appear as separate cards or one grouped race card.

**Verdict logic:** Absolute delta ≥5c → TRADE. Absolute delta <5c → PASS. Positive delta means Marcus FV is above market price; negative delta means Marcus FV is below market price. This is Marcus's signal, not Carlos's decision.

**Continuation:** Marcus reads `state/analysis.json` on startup. Markets marked `complete` are skipped. Markets marked `analyzing` are resumed. New markets enter `discovered` → `analyzing`. See `currentstate.md` for the full state machine.

**Polling sources (in priority order — all free, no API key required unless noted):**

| Priority | Source | Coverage | Method |
|---|---|---|---|
| 1 | **VoteHub API** | Presidential approval, generic ballot | REST (free, no key) |
| 2 | **Ballotpedia** | Senate, House, Governor, mayoral races | browser_navigate |
| 3 | **RaceToTheWH.com** | Senate, House, Governor averages | browser_navigate |
| 4 | **Wikipedia** | Mayorals, local races, historical context | browser_navigate |
| 5 | **Quinnipiac / Siena** | State-specific high-quality polls | web_extract |
| 6 | **MIT Election Lab** | Historical results / fundamentals baseline | Download CSV |
| 7 | **Dave Leip's Atlas** | Historical county/state results | browser_navigate |

**Financial data:**
| Source | Coverage | Method |
|---|---|---|
| **OpenFEC API** | Candidate receipts, disbursements, cash on hand, top donors, outside spend | REST (DEMO_KEY works, 1000 calls/hr limit) |

**Cross-market context (not trade venue):**
| Source | Use | Method |
|---|---|---|
| **Kalshi** | Primary trade venue | Public REST API for discovery; authenticated client only for future portfolio work |
| **PredictIt** | Optional cross-check for mispricing | REST API — not yet integrated |

**Data quality bar:** Marcus needs at least two independent sources before writing a brief. If VoteHub has approval numbers and Ballotpedia has the Senate race polling, that's enough. Don't chase a third source if two are solid.

*References: prediction-market-trading skill, OpenFEC API docs, VoteHub API docs*

---

## Collector

Collector is a Python script (`collector.py`). It runs first, before Marcus.

**What it does:**
1. Queries Kalshi API for all political/election markets
2. Filters to markets expiring within 60 days
3. Further filters to markets with polling-accessible races (excludes DOGE, tariff, admin-action markets)
4. Compares against `state/analysis.json` — identifies new markets vs existing
5. Writes market list to `state/analysis.json` (new markets as `discovered`)
6. Returns ticker, title, expiry, market_price, `event_ticker`, and candidate name when available for each new market

**API:** Uses Kalshi's public elections API for market discovery. No authentication is required for the current collector path; credentials are stored externally for future authenticated work only.

**Output:** Updates `state/analysis.json`. Does not talk to Marcus directly — writes state, Marcus reads it.

*References: kalshi-integration skill (`references/political-market-discovery.md`), bugs.md*

---

## Generator

Generator is a Python script (`generator.py`). It runs last, after Marcus.

**What it does:**
1. Reads `state/analysis.json` for all markets with `status: complete`
2. Groups supported multi-contract races by `event_ticker` into one race card while preserving individual market state
3. Renders `index.html` matching the design in `docs/artifact-reference/`
4. Writes to `output/index.html`
5. Prints `Done` on success; the Hermes cron job delivers stdout to WhatsApp

**HTML design:** Dark theme, blue + amber accents, portrait-width briefing cards, 3 cards per desktop page when possible. Single-contract markets render as normal cards; grouped races render one race card with a candidate table. See `docs/artifact-reference/artifact.html` for the design baseline.

*Reference: README.md*

---

## Handoff Protocol

```
Daily Cron (1:30PM ET)
    │
    ▼
~/.hermes/scripts/arbiter-daily.py
    → Runs collector.py → engine.py → generator.py
    → Exits non-zero on any failed step
    │
    ▼
[1] collector.py
    → Writes discovered markets to state/analysis.json
    │
    ▼
[2] engine.py (Marcus)
    → For each market, or supported grouped race, in discovered/analyzing:
      → Fetch VoteHub polling + OpenFEC financials
      → Compute FV + delta + verdict
      → Write back to state/analysis.json
    │
    ▼
[3] generator.py
    → Reads complete markets from state/analysis.json
    → Groups supported candidate-contract races by event_ticker
    → Renders output/index.html
    → Prints "Done"; Hermes delivers stdout to WhatsApp
```

**State file:** `state/analysis.json` is the single source of truth. All three scripts read/write it.

**Failure handling:** If any step fails, cron sends Carlos a WhatsApp with the error and retries next day. Do not skip steps or partially update state.

---

## Key Files

| File | Purpose |
|---|---|
| `~/.hermes/scripts/arbiter-daily.py` | Hermes cron pipeline runner |
| `state/analysis.json` | Market state tracker |
| `state.py` | State read/write/upsert/transition helpers |
| `collector.py` | Kalshi market discovery |
| `engine.py` | Marcus analysis |
| `generator.py` | HTML generation |
| `output/index.html` | The deliverable |
| `docs/currentstate.md` | Project state + state machine |
| `docs/bugs.md` | Known limitations and edge cases |
| `docs/CHANGELOG.md` | What changed |
| `README.md` | Project overview |
| `docs/artifact-reference/artifact.html` | Design spec |

---

## What Goes In a Brief (Full Specification)

Every market that enters the pipeline gets a full brief. No filtering by verdict. Supported multi-contract candidate races may render as one grouped race card instead of one card per contract.

**Required fields:**
- `kalshi_badge`: ticker + market type (e.g. "KXLAXMAY26 / First Round Winner")
- `race_title`: short name of the race
- `election_date`: ISO date
- `verdict_tag`: TRADE (amber) or PASS (grey) — below election date
- `context`: 1-2 paragraph overview of the race — candidates, dynamics, key variables
- `price_row`: Market price | Delta | Marcus FV (styled per artifact)
- `analysis`: Marcus's full reasoning — what polls say, why market is mispriced or not, what he's watching
- `sources`: List of poll sources with labels
- For grouped race cards: candidate table with candidate, market price, Marcus FV, edge, and TRADE/PASS signal

**Optional (if applicable):**
- `no_market_reason`: If market price is "—" (not yet trading), explain why and what triggers market creation

---

*See currentstate.md for the full project state machine and roadmap.*