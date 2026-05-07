# Outcome tracking scaffold

Arbiter should keep outcome tracking separate from the live daily brief so the dashboard stays focused on current research, not post-hoc scorekeeping.

## Initial storage

- Directory: `data/outcomes/`
- Suggested first file: `data/outcomes/outcomes.json`
- One record per recommendation review, appended after the eventual market result or thesis resolution is known.

## Starter fields

Each tracked record should include:

- `recommendationDate`
- `ticker`
- `sideOrAction`
- `recommendedPrice`
- `fairValue`
- `eventualResult`
- `thesisOutcome`
- `notes`

## Notes

- `sideOrAction` should handle both new trades (`Buy YES`, `Buy NO`) and portfolio actions (`Hold`, `Reduce`, `Exit`, `Pass`).
- `eventualResult` can stay empty until the market resolves or the review window closes.
- `thesisOutcome` should describe whether the reasoning was directionally right, not just whether a market paid out.
- Keep this local-only for now; no remote sync or public reporting is needed.
