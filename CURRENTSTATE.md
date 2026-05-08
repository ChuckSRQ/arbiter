# CURRENTSTATE

## Active market coverage

- Active election market: `KXMAYORLA` (Los Angeles Mayor, 10 candidates, expires 2027-06-02).
- Active trackers:
  - `KXAPRPOTUS` (presidential approval rating)
  - `KXGENERICBALLOTVOTEHUB` (generic congressional ballot)

## Polling evidence

- `data/polling_evidence/current.json` currently contains 11 race evidence entries.
- There is no `KXMAYORLA` polling evidence entry yet.

## Pipeline status

Pipeline is operating end-to-end:

1. collector (`scripts/collect_kalshi_public_snapshot.py`)
2. engine (`src/analysis/engine.ts`)
3. report generation (`scripts/generate_daily_report.ts` / `scripts/run_daily_report.ts`)
4. site rendering (`src/app/page.tsx`)

## Known limitations

- Kalshi currently has very few open US election markets.
- Most 2026 midterm markets are not listed yet, limiting election opportunity breadth.
