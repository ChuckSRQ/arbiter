# Current State

*Where the project is right now, the state machine, and the roadmap.*

---

## Status: Phase 1 — Core Pipeline

Documentation complete. Code development starting. No Python written yet.

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

**Market exits the pipeline at `complete` (or `stale`).** The report only shows `complete` markets.

---

## What's Built vs What's Planned

### Built
- `docs/agents.md` — agent roles, handoffs, brief specification
- `docs/README.md` — project overview and MVP scope (root)
- `docs/currentstate.md` — project state + state machine
- `docs/CHANGELOG.md` — change log
- `docs/bugs.md` — known limitations, resolved questions, pitfalls
- `docs/artifact-reference/artifact.html` — design spec
- `state.py` — state read/write/upsert/transition helpers
- `state/analysis.json` — empty schema
- `output/` — directory, empty

### In Progress
- Task 2: `collector.py` — awaiting Kalshi API key

### Planned (not built)
- `collector.py` — Kalshi API integration
- `engine.py` — polling + financials analysis
- `generator.py` — HTML report generator
- `output/index.html` — the report

---

## MVP Roadmap

**Phase 1 — Core Pipeline (now)**
- [x] `state/analysis.json` — schema + `state.py` read/write/transition helpers
- [ ] `collector.py` — authenticated Kalshi API, ≤60d political markets, state write
- [ ] `engine.py` — VoteHub API + Ballotpedia polling fetch, FV calculation, verdict, full brief JSON
- [ ] `generator.py` — index.html from brief JSON, artifact design
- [ ] `output/index.html` — first generated report
- [ ] WhatsApp ping on completion

**Phase 2 — Localhost Cron**
- [ ] Hermes cron job at 1:30PM ET
- [ ] Continuation logic (don't restart analysis from scratch)
- [ ] Error handling with WhatsApp failure alert

**Stays Local (no deployment planned)**
- No Vercel, no GitHub Pages, no cloud hosting
- Arbiter runs on Carlos's machine via localhost

---

## Decisions Made

| Decision | Resolution |
|---|---|
| Stack | Python + static HTML. No Next.js/DB for MVP. |
| Polling sources | VoteHub API (primary), Ballotpedia (secondary), RaceToTheWH, Wikipedia (mayorals), Quinnipiac/Siena (tertiary). Not locked to any single source. |
| Financial data | OpenFEC API — candidate receipts, disbursements, cash on hand, top donors, outside spend. DEMO_KEY works, no key required. |
| Market filter | ≤60 days from expiry, political/election only, has polling |
| Full briefs | Every qualifying market gets a full brief. No filtering by verdict. |
| Verdict tag | TRADE (amber) or PASS (grey) — on its own line below election date |
| Report minimum | Always show 3-5 political briefs per day. If fewer markets qualify, show what's available. Even PASS verdicts show full polling + analysis. Carlos decides, not Marcus. |
| WhatsApp ping | "Done" on completion — no summary, just confirmation |

---

## What's Still Open

- Wikipedia page URL structure for non-US elections (low priority, US-only for now)
- How to handle 3-5 minimum when fewer than 3 markets qualify — show what's available, no padding

All open questions go in `bugs.md` or get resolved before that phase is started.

---

*See agents.md for the technical handoff protocol. See README.md for project overview.*