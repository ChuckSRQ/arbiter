# Forecast Model Architecture Spec

## Approved Direction

Carlos approved building Arbiter's forecast model once, cleanly, with support for presidential and congressional elections when those markets become relevant. The implementation should avoid multiple competing model implementations.

Core priorities:
- Daily report must stay fast and reliable.
- First search/analysis for a new market may be the expensive step.
- Subsequent daily runs should reuse cached/stateful work and avoid recomputing everything.
- Arbiter remains a market-specific briefing tool, not a national-map dashboard.
- One PR contains all changes. No direct commits to `main`.

## Confirmed Product Decisions

1. Arbiter should produce market-specific briefs only.
   - No national/presidential map summary in this implementation.
   - Presidential and congressional support should exist at the forecast/data-model layer so Kalshi market briefs can use it later.

2. Congressional races with no polling should still get a fundamentals-based fair value.
   - The model must use OpenFEC financial data as part of fundamentals when polling is sparse or unavailable.
   - It should mark lower confidence rather than refusing to estimate.

3. Pollster quality discounts should exist, but not be harsh or politically loaded.
   - Do not ban pollsters by default.
   - Use modest weights so a pollster judged weaker is discounted, not erased.
   - The default stance is: include with mild-to-moderate discount unless there is a concrete data reason to exclude.

4. Prioritize speed.
   - Use cached state and deterministic local Python.
   - Do not run heavy Bayesian fitting in the daily cron path.
   - Daily cron should read calibration/config files, not regenerate them.

5. Calibration is manual/occasional for now.
   - No weekly calibration cron in this PR.
   - Keep calibration constants in files that can be manually updated later.

## Implementation Shape

Use a two-layer model architecture:

1. Fast daily forecast engine
   - Python stdlib only unless the repo already depends on something.
   - Computes weighted polling averages, fallback fundamentals, and probabilities quickly.
   - Produces `forecast` blocks for state entries while preserving current top-level fields.

2. Offline/manual calibration layer
   - Calibration constants live in JSON files.
   - The daily engine loads them.
   - Heavy R/Stan/PyMC research is out of the daily path.

## Required State Compatibility

Do not break existing `state/analysis.json` compatibility.

Existing top-level fields must remain available:
- `marcus_fv`
- `delta`
- `verdict`
- `context`
- `analysis`
- `sources`
- `financials`
- `status`

Add a nested forecast block where analysis exists:

```json
"forecast": {
  "model": "arbiter_forecast_v2",
  "race_type": "binary_head_to_head",
  "polling_average": 52.3,
  "polling_lead": 4.1,
  "p05": 0.63,
  "p25": 0.70,
  "p50": 0.76,
  "p75": 0.81,
  "p95": 0.88,
  "confidence": "medium",
  "data_quality": "polling_available",
  "calibration_version": "manual-2026-05-09"
}
```

## Phase Tasks

### Phase 1 — Architecture foundation

Goal: add the model package structure and shared types/config loading without changing report behavior.

Required:
- Add a forecast/model package or modules.
- Define race/candidate/poll/forecast dataclasses or typed dicts.
- Add calibration JSON config files.
- Add classification helpers for binary, multicandidate, top-two, congressional, and presidential state race types.
- Add tests.
- Update README, docs/CHANGELOG.md, docs/currentstate.md, docs/bugs.md.

### Phase 2 — Polling average engine

Goal: turn normalized polls into a weighted polling average.

Required:
- Implement poll weighting with:
  - sample-size weight
  - recency decay
  - population type weight
  - modest pollster quality weight
  - modest sponsor/internal poll discount
- Do not ban pollsters by default.
- Add cache/state-friendly hooks so expensive source lookup can be reused later.
- Add tests for weighting, mild pollster discounts, stale-poll decay, and empty-poll behavior.
- Update README, docs/CHANGELOG.md, docs/currentstate.md, docs/bugs.md.

### Phase 3 — Forecast adapters

Goal: produce probabilities for supported race types.

Required:
- Binary head-to-head adapter using calibrated polling lead to probability.
- Multi-candidate plurality simulation adapter.
- Top-two advance simulation adapter.
- Probability intervals and confidence labels.
- Verdict logic that uses median FV but respects uncertainty.
- Preserve current top-level `marcus_fv`, `delta`, and `verdict` fields.
- Add tests.
- Update README, docs/CHANGELOG.md, docs/currentstate.md, docs/bugs.md.

### Phase 4 — Presidential/congressional readiness

Goal: prepare the model for presidential and congressional market briefs without building a separate implementation later.

Required:
- Add presidential state race support and a lightweight Electoral College simulation helper that can run quickly when given state forecasts.
- Add congressional/district fallback fundamentals support.
- Use OpenFEC financials in congressional sparse-poll fundamentals.
- Mark lower confidence when forecasts rely mostly on fundamentals.
- Do not add national map UI; keep output market-specific.
- Add tests.
- Update README, docs/CHANGELOG.md, docs/currentstate.md, docs/bugs.md.

### Phase 5 — Reporting integration

Goal: show the forecast block in reports and make engine output uncertainty-aware.

Required:
- Integrate forecast modules into `engine.py` without breaking current mayoral grouped analysis.
- Add `forecast` block to completed state entries.
- Update analysis text to mention probability range/confidence/data quality when available.
- Update `generator.py` to render probability range/confidence elegantly inside existing card design.
- Keep portrait cards and 3-column desktop behavior.
- Add tests or deterministic fixture checks.
- Update README, docs/CHANGELOG.md, docs/currentstate.md, docs/bugs.md.

## Verification Required Before PR

At minimum:
- `python3 -m pytest tests/ -q`
- `python3 -m py_compile collector.py state.py engine.py generator.py`
- If safe and not too slow: `python3 generator.py` against existing state.
- No direct commits to `main`.
- One branch, one PR.

## Documentation Handoff Rule

Every phase must read and update these files:
- `README.md`
- `docs/CHANGELOG.md`
- `docs/currentstate.md`
- `docs/bugs.md`

Each update should leave enough context for the next subagent to understand what was built, what was intentionally deferred, and what verification passed.
