# Arbiter — Agents

*Who does what, how they talk to each other, and where to find things.*

---

## The Team

| Agent | Role |
|---|---|
| **Marcus** | Analysis engine — polling research, fair value, verdict, full brief generation |
| **Collector** | Python script — queries Kalshi API, surfaces qualifying markets |
| **Generator** | Python script — takes Marcus output, renders `index.html` |

---

## Marcus

Marcus is the reasoning layer. He does not scrape Kalshi, he does not generate HTML. He receives a market ticker and returns a structured brief.

**Marcus's inputs:**
- Market ticker (e.g. `KXMAYORLA-26JUN02`)
- Market title, expiry date, market price (from Collector)
- Polling data (from Wikipedia, pollster sites, Silver Bulletin as fallback)

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
    {"label": "Wikipedia polls", "url": "..."},
    {"label": "Kalshi market", "url": "..."}
  ],
  "status": "complete"
}
```

**Verdict logic:** Delta ≥5c → TRADE. Delta <5c → PASS. This is Marcus's signal, not Carlos's decision.

**Continuation:** Marcus reads `state/analysis.json` on startup. Markets marked `complete` are skipped. Markets marked `analyzing` are resumed. New markets enter `discovered` → `analyzing`. See `currentstate.md` for the full state machine.

**Polling sources (in priority order):**
1. Wikipedia election polling pages
2. Pollster websites directly
3. Silver Bulletin (browser_navigate required — terminal HTTP blocked)
4. RealClearPolling (web_search fallback)

*References: prediction-market-trading skill (`references/political-polling-market-analysis.md`), currentstate.md*

---

## Collector

Collector is a Python script (`collector.py`). It runs first, before Marcus.

**What it does:**
1. Queries Kalshi API for all political/election markets
2. Filters to markets expiring within 60 days
3. Further filters to markets with polling-accessible races (excludes DOGE, tariff, admin-action markets)
4. Compares against `state/analysis.json` — identifies new markets vs existing
5. Writes market list to `state/analysis.json` (new markets as `discovered`)
6. Returns ticker, title, expiry, market_price for each new market

**API:** Uses `kalshi_python_sync` with Carlos's API key. Public endpoints for market data; authenticated for any portfolio calls later.

**Output:** Updates `state/analysis.json`. Does not talk to Marcus directly — writes state, Marcus reads it.

*References: kalshi-integration skill (`references/political-market-discovery.md`), bugs.md*

---

## Generator

Generator is a Python script (`generator.py`). It runs last, after Marcus.

**What it does:**
1. Reads `state/analysis.json` for all markets with `status: complete`
2. Renders `index.html` matching the design in `docs/artifact-reference/`
3. Writes to `output/index.html`
4. Sends WhatsApp ping to Carlos

**HTML design:** Dark theme, blue + amber accents, 1200px max-width, card-per-market layout. See `docs/artifact-reference/artifact.html` for the exact design spec.

*Reference: README.md*

---

## Handoff Protocol

```
Daily Cron (1:30PM ET)
    │
    ▼
[1] collector.py
    → Writes state/analysis.json
    │
    ▼
[2] engine.py (Marcus)
    → For each market in discovered/analyzing:
      → Fetch polling
      → Compute FV + delta + verdict
      → Write back to state/analysis.json
    │
    ▼
[3] generator.py
    → Reads complete markets from state/analysis.json
    → Renders output/index.html
    → WhatsApp ping to Carlos
```

**State file:** `state/analysis.json` is the single source of truth. All three scripts read/write it.

**Failure handling:** If any step fails, cron sends Carlos a WhatsApp with the error and retries next day. Do not skip steps or partially update state.

---

## Key Files

| File | Purpose |
|---|---|
| `state/analysis.json` | Market state tracker |
| `collector.py` | Kalshi market discovery |
| `engine.py` | Marcus analysis |
| `generator.py` | HTML generation |
| `output/index.html` | The deliverable |
| `docs/currentstate.md` | Project state + state machine |
| `docs/bugs.md` | Known limitations and edge cases |
| `docs/CHANGELOG.md` | What changed |
| `docs/README.md` | Project overview |
| `docs/artifact-reference/artifact.html` | Design spec |

---

## What Goes In a Brief (Full Specification)

Every market that enters the pipeline gets a full brief. No filtering by verdict.

**Required fields:**
- `kalshi_badge`: ticker + market type (e.g. "KXLAXMAY26 / First Round Winner")
- `race_title`: short name of the race
- `election_date`: ISO date
- `verdict_tag`: TRADE (amber) or PASS (blue) — below election date
- `context`: 1-2 paragraph overview of the race — candidates, dynamics, key variables
- `price_row`: Market price | Delta | Marcus FV (styled per artifact)
- `analysis`: Marcus's full reasoning — what polls say, why market is mispriced or not, what he's watching
- `sources`: List of poll sources with labels

**Optional (if applicable):**
- `no_market_reason`: If market price is "—" (not yet trading), explain why and what triggers market creation

---

*See currentstate.md for the full project state machine and roadmap.*