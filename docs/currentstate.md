# Current State

*Where the project is right now, the state machine, and the roadmap.*

---

## Status: Planning

The project is fully specced but not yet built. All documentation lives in `docs/`. No code has been written.

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

### Built (nothing yet)
- `docs/agentzeroth-agents.md` — agent roles and handoffs
- `docs/README.md` — project overview and MVP scope
- `docs/CHANGELOG.md` — this file, empty template
- `docs/artifact-reference/artifact.html` — design spec
- `state/` — directory, no files yet
- `output/` — directory, no files yet

### Planned (not built)
- `collector.py` — Kalshi API integration
- `engine.py` — Marcus analysis with Wikipedia polling
- `generator.py` — HTML report generator
- `state/analysis.json` — market state tracker
- `output/index.html` — the report

---

## MVP Roadmap

**Phase 1 — Core Pipeline (now)**
- [ ] `collector.py` — authenticated Kalshi API, ≤60d political markets, state write
- [ ] `engine.py` — VoteHub API + Ballotpedia polling fetch, FV calculation, verdict, full brief JSON
- [ ] `state/analysis.json` — schema + read/write functions
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

- Verdict tag styling (amber for TRADE, what for PASS — blue? grey? muted?)
- Wikipedia page URL structure for non-US elections (low priority, US-only for now)
- Cron WhatsApp message format — just "done" or a one-line summary?
- If 0 markets qualify, what does the report show?

All open questions go in `bugs.md` or get resolved before that phase is started.

---

*See agents.md for the technical handoff protocol. See README.md for project overview.*