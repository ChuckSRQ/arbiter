# Arbiter Market Filter — Election Race vs Event Contract

## Problem

The collector fetches all markets tagged "Elections" from Kalshi. Most are **event contracts** — binary yes/no questions about whether something will happen (an endorsement, a dropout, a resignation). These are not election races and cannot be analyzed mathematically. There is no polling data, no vote share, no demographic breakdown, no historical trend to model.

Arbiter's value is in **mathematical analysis of polling data** — computing win probabilities, momentum shifts, demographic splits, contextualizing against fundraising and historical results. None of that applies to event contracts.

We need a first-class filter that only passes markets where that analysis is actually possible.

---

## What Passes the Filter — Election Races

An election race market has:
1. **Multiple named candidates** — candidate A vs candidate B vs candidate C (or more)
2. **The question is "who wins"** — not "will event X happen"
3. **Outcome is determined by votes** — the winner is whoever gets the most votes

Examples that pass:
- `KXLAMAYOR` — Bass vs Caruso vs Pratt, LA Mayor election
- `SENATEPA` — Democrat vs Republican Pennsylvania Senate
- `HOUSEIN1` — Democrat vs Republican Indiana District 1
- `GOVTXX` — Governor race, Texas

---

## What Fails the Filter — Event Contracts

An event contract has:
1. **Binary yes/no question** — "Will X happen?" or "Will Y endorse Z?"
2. **The question is not about who wins a race** — it's about whether an event occurs
3. **No polling data, no vote share** — just contract resolution on a specific fact

Examples that fail (currently in collector output):
- `KXTRUMPENDORSE-26JUN02-SPRA` — Will Trump endorse Spencer Pratt?
- `KXDROPOUTPRIMARY-26-KPAX` — Will Ken Paxton drop out?
- `KXVENEZUELALEADER2-26JUN01-NMAD` — Will Maduro remain leader?
- `KXHOUSEEXPEL-26JUN01-T0` — Will the number of reps expelled be exactly 0?
- `KXPORTERDROPOUT-26JUN02` — Will Katie Porter drop out?
- `KXMILLSPLATNER-26NOV03-MAY15` — Will Mills endorse Platner?

---

## How to Detect Programmatically

### Signal 1: Market question type

Kalshi market objects have a `question` field. Pattern-match it:

**Fails** (event contract patterns):
- `Will X drop out` / `Will X resign` / `Will X be expelled`
- `Will X endorse Y` / `Will X appoint Y`
- `Will X happen before date Y`
- `Will the number of X be exactly Y`
- `Will X join Y before date Z`
- `Will X leave office before Y`
- `Will X be the head of state of Y`
- `Will X be Y's running mate`

**Passes** (race structure):
- `Who will win the [position] election in [state/city]`
- `Will [candidate] win [position]`
- `[Candidate A] vs [Candidate B]` — direct matchup format
- `What party will control [chamber/position]`

### Signal 2: `type` or `sub_tarket` field

Kalshi markets may have a `type` field. Binary event contracts typically have `event` or `binary` in the type or resolution logic. Race markets have candidate-based structure. Inspect actual API response shapes to confirm.

### Signal 3: Absence of polling-ticker association

Race markets can be associated with a `poll_ticker` or similar. Event contracts cannot be — they have no polling. Check if the market's series has a `polls` relationship in the Kalshi API. If yes, it's a race. If no, it's likely an event contract.

### Signal 4: Market resolution rules

Race markets resolve based on election results (official vote count). Event contracts resolve on specific facts (did X happen, did Y endorse Z). This information may be in the market object — check `resolution_source` or similar field.

---

## Implementation Decision

**Use Signal 1 (question text pattern matching) as the primary filter.**

Rationale: It requires no additional API calls, works from the market data we already fetch, and captures 95%+ of the categorical junk with a manageable set of patterns.

Add a `_is_race_market(market)` function in `collector.py` that returns `True` only if the market question text matches the "Passes" patterns AND does not match any of the "Fails" patterns.

If Signal 1 is inconclusive, **do not include the market** — when in doubt, leave it out. A sparse report is better than a noisy one.

---

## Integration

Add `_is_race_market(market)` as a filter step in `_fetch_and_filter_series()`, after the 60-day date check and before adding to results:

```python
if not _is_race_market(m):
    continue  # skip — not a real race, no polling to analyze
```

This replaces any blocklist approach entirely. The filter is semantic, not syntactic — it reads the question text and asks "can AI math actually apply here?"

---

## Expected Result

With this filter applied to the current collector run:
- LA Mayor markets (Bass/Caruso/Pratt) → **pass**
- Texas Senate runoff endorsement markets → fail
- Venezuela leader markets → fail
- Congressional expulsion markets → fail
- All event-contract categorical markets → fail

The report shows 1 race (LA Mayor) with its candidate markets, all of which have actual polling data that can be analyzed mathematically.

---

## Future: Signal 3 (Poll-Ticker Association)

Once the collector is stable with Signal 1, add a secondary check: attempt to fetch polling data for each passing market. If no polling exists, flag the market as "low data" — still include it, but note in the report that analysis will be limited.

This future step ensures we don't accidentally include races with zero underlying polling.