# SPEC: Arbiter Polling Pipeline — Phase 2

*Wiring Ballotpedia + RaceToTheWH, fixing OpenFEC, eliminating placeholder cards.*

## Status

Draft. Not yet approved for implementation.

---

## Problem Statement

The polling pipeline is 80% built but the most important sources for US elections — Ballotpedia and RaceToTheWH — were documented in `docs/agents.md` but never wired into `engine.py`. As a result:

- Senate, House, and Governor races fall into the `"other"` bucket and get placeholder analysis
- OpenFEC candidate IDs are extracted via regex on ticker/title strings, but Kalshi doesn't embed FEC IDs there — so financial data mostly fails
- Cards with failed polling still render with placeholder text, violating the rule: "never render a card with placeholder analysis"

---

## Phase 1 — Wire Ballotpedia and RaceToTheWH

### 1a. New `_market_type_race()` function

Replace `_market_type()` in `engine.py`. Returns a race-type string:

```python
def _market_type_race(ticker, series_ticker=None):
    t = (ticker or "").upper()
    s = (series_ticker or "").upper()

    if "APRPOTUS" in t or "APPROVAL" in t:
        return "approval"
    if "GENERICBALLOT" in t or "VOTEHUB" in t:
        return "generic"
    if "MAYOR" in t:
        return "mayor"
    if "SENATE" in s or "SENATE" in t or re.search(r"KXSE[A-Z]", t):
        return "senate"
    if "HOUSE" in s or "HOUSE" in t or re.search(r"KXHOU", t):
        return "house"
    if "GOV" in s or "GOV" in t or re.search(r"KXGOV", t):
        return "governor"
    if any(tag in (t + s) for tag in ("ARMENIA", "COLOMBIA", "LEBANON", "BRAZIL", "FRANCE", "GERMANY", "UK", "INTERNATIONAL")):
        return "international"
    return "other"
```

Keep `_market_type()` as a backward-compatible wrapper that maps `senate`/`house`/`governor`/`international` → `"other"` for now, but add a comment that it's deprecated. The new code uses `_market_type_race()`.

---

### 1b. BallotpediaPoller class (web_extract)

Ballotpedia pages are structured and scrapeable via `web_extract`:

- `https://ballotpedia.org/2026_United_States_Senate_elections` — Senate overview with polling tables
- `https://ballotpedia.org/2026_United_States_House_of_Representatives_elections` — House overview
- `https://ballotpedia.org/2026_gubernatorial_elections` — Governor overview

For a specific race, construct: `https://ballotpedia.org/{state}_Senate_election,_2026`

**Class structure:**

```python
class BallotpediaPoller:
    """Fetch polling data from Ballotpedia via web_extract."""

    BASE_URL = "https://ballotpedia.org"

    def __init__(self):
        self._cache = {}

    def poll(self, race_title, state, race_type):
        """Fetch polling for a specific race.

        Args:
            race_title: e.g. "California Senate 2026"
            state: two-letter state code, e.g. "CA"
            race_type: "senate", "house", or "governor"

        Returns:
            dict of {candidate_name: poll_pct}, or {} on failure.
        """
        # 1. Try race-specific page first
        # 2. Fall back to overview page for the election type
        # Parse HTML polling tables: find candidate names + most recent poll percentages
        # Filter candidates ≤6%
        # Return {}
        """
```

**Parsing strategy for Ballotpedia HTML:**
- Polling tables have candidate names in bold and percentages in cells
- Pattern: look for `<table` elements, parse `<tr>` rows, find `'''Candidate Name'''` bold text followed by percentage cells
- Use regex: `'''([^']+)'''` for bold names, `(\d+(?:\.\d+)?)\s*%` for poll numbers
- Take the rightmost percentage in each row (most recent)

---

### 1c. RaceToTheWHPoller class (browser automation)

RaceToTheWH loads via JavaScript. Use `browser_navigate` + extract.

- `https://racetothewh.com/senate` — Senate races with averages
- `https://racetothewh.com/house` — House races
- `https://racetothewh.com/governor` — Governor races
- Specific race pages: `https://racetothewh.com/senate/{state}` etc.

**Class structure:**

```python
class RaceToTheWHPoller:
    """Fetch polling averages from RaceToTheWH via browser automation."""

    BASE_URL = "https://racetothewh.com"

    def __init__(self):
        self._cache = {}

    def poll(self, race_title, state, race_type):
        """Fetch polling for a specific race.

        Args:
            race_title: e.g. "Texas Senate 2026"
            state: two-letter state code
            race_type: "senate", "house", or "governor"

        Returns:
            dict of {candidate_name: poll_pct}, or {} on failure.
        """
        # 1. Navigate to the specific race page
        # 2. Wait for page to load (JS rendering)
        # 3. Extract candidate names + polling percentages
        # 4. Filter candidates ≤6%
        # Return {}
```

**Browser automation pattern:**
- Use `browser_navigate(url)` → `browser_snapshot()` → parse the accessibility tree
- Look for candidate name + percentage pairs in the rendered content
- Timeout: 15s for page load

---

### 1d. Wire polling priority chain in `run()`

Update the `run()` function in `engine.py`. The `"other"` market type handling is replaced with the new `_market_type_race()`:

```python
# In run(), replace the "other" block with:
m_type = _market_type_race(ticker, market.get("series_ticker"))

if m_type == "other":
    # Still try WikipediaPoller as last resort
    ...

# For senate, house, governor:
if m_type in ("senate", "house", "governor"):
    # Priority 1: Ballotpedia
    bp = BallotpediaPoller()
    state_abbr = _extract_state_from_ticker(ticker)  # e.g. "CA" from "KXSENCAL-26"
    bp_polls = bp.poll(race_title, state_abbr, m_type)

    if bp_polls:
        # Use Ballotpedia polling
        ...
    else:
        # Priority 2: RaceToTheWH
        rtwh = RaceToTheWHPoller()
        rtwh_polls = rtwh.poll(race_title, state_abbr, m_type)
        if rtwh_polls:
            # Use RaceToTheWH polling
            ...
        else:
            # Priority 3: Wikipedia fallback
            wiki = WikipediaPoller()
            wiki_polls, wiki_meta = wiki.poll_with_meta(race_title, event_date, candidates)
            if wiki_polls:
                # Use Wikipedia polling
                ...
            else:
                # All sources exhausted — mark as poll_failed, don't render
                market["_poll_failed"] = True
                # Skip adding to state — generator will skip it
                continue  # don't transition to complete
```

**Key behavior:** If all three polling sources fail, mark `market["_poll_failed"] = True` and `continue` — do NOT call `_finalize_market()`, do NOT transition to `complete`. The generator skips `_poll_failed` markets.

---

### 1e. Expand `WikipediaPoller._wikipedia_url()`

Add more international races:

```python
def _wikipedia_url(race_title, event_date):
    # ... existing LA Mayor, Armenia, Colombia ...

    # UK General Election
    if any(kw in title_lower for kw in ["uk", "united kingdom", "british", "britain"]):
        if "parliament" in title_lower or "general" in title_lower:
            return f"{_WIKIPEDIA_BASE}/2026_United_Kingdom_general_election"

    # France Presidential
    if "france" in title_lower and "president" in title_lower:
        return f"{_WIKIPEDIA_BASE}/2026_French_presidential_election"

    # Germany Federal
    if "germany" in title_lower and ("bundestag" in title_lower or "federal" in title_lower):
        return f"{_WIKIPEDIA_BASE}/2026_German_federal_election"

    # Generic international fallback
    if "presidential" in title_lower:
        country = re.sub(r"\b20\d{2}\b", "", title_lower).strip()
        country = re.sub(r"\s*presidential.*", "", country).strip()
        if country:
            return f"{_WIKIPEDIA_BASE}/{year}_{country}_presidential_election"

    # ... rest of existing logic ...
```

---

## Phase 2 — Fix OpenFEC Candidate ID Lookup

### 2a. Add FEC candidate search by name

When `_extract_candidate_id()` returns None (almost always), fall back to OpenFEC's candidate search endpoint:

```python
def _search_fec_candidate_by_name(name, state=None):
    """Search OpenFEC for a candidate by name, return candidate_id or None."""
    params = {
        "api_key": OPENFEC_KEY,
        "q": name,
        "per_page": 10,
    }
    if state:
        params["state"] = state
    payload = fec_client._get("/candidate/search", params)
    if not isinstance(payload, dict):
        return None
    results = payload.get("results", [])
    if results and isinstance(results, list):
        # Return first match with a valid FEC ID
        for r in results:
            cid = r.get("candidate_id")
            if cid and re.match(r"^[HPS]\d{5,8}$", str(cid)):
                return cid
    return None
```

Wire this into `_attach_financials()`:

```python
def _attach_financials(market, fec_client):
    m_type = _market_type_race(market.get("ticker"), market.get("series_ticker"))
    if m_type in ("approval", "generic", "international"):
        market["financials"] = {"note": "No US FEC data for this race type"}
        return

    candidate_id = _extract_candidate_id(market)
    if not candidate_id:
        # Try FEC name search
        candidate_name = (market.get("candidate_name") or "").strip()
        state = _extract_state_from_ticker(market.get("ticker") or "")
        candidate_id = _search_fec_candidate_by_name(candidate_name, state)

    if not candidate_id:
        market["financials"] = {"note": "Could not find FEC candidate ID"}
        return

    financials = fec_client.fetch_candidate_financials(candidate_id)
    if financials:
        market["financials"] = financials
    else:
        market["financials"] = {"error": "OpenFEC fetch failed"}
```

### 2b. International races get a graceful "no US data" note

Set `market["financials"] = {"note": "International race — no US FEC data"}` for `m_type == "international"`.

---

## Phase 3 — Never Render Placeholder Analysis

### 3a. Mark poll-failed markets

In `engine.py`, when all polling sources are exhausted:

```python
market["_poll_failed"] = True
# Do NOT call _finalize_market() — skip the market entirely
# Do NOT transition to "complete" — keep in "analyzing" or leave as-is
# The generator will skip it
```

### 3b. Generator skips `_poll_failed` markets

In `generator.py`, filter before rendering:

```python
def get_complete_markets(state):
    """Return complete markets, excluding those where polling failed."""
    complete = get_complete(state)
    return [m for m in complete if not m.get("_poll_failed")]
```

Update all call sites in `generator.py` to use `get_complete_markets()` instead of `get_complete()`.

---

## Phase 4 — Fundamentals Modeling for Sparse/No-Poll Races

### 4a. `_fundamentals_fv()` function

For races where all polling sources fail AND we have some structural information:

```python
def _fundamentals_fv(market, generic_ballot_lean=None):
    """Estimate FV from structural/fundamental factors when no polling is available.

    Args:
        market: market dict
        generic_ballot_lean: Democratic margin on generic ballot (positive = D lean)

    Returns:
        (fv_cents, analysis_text, confidence)
    """
    ticker = market.get("ticker", "")
    m_type = _market_type_race(ticker, market.get("series_ticker"))

    # Incumbency: federal incumbents get +8c baseline advantage
    incumbent_bonus = 0
    if m_type in ("senate", "house", "governor"):
        title = (market.get("title") or "").lower()
        if "incumbent" in title or "inc" in title:
            incumbent_bonus = 8

    # National environment adjustment
    env_adjustment = 0
    if generic_ballot_lean is not None:
        # Generic ballot lean: each point D lean → +1c for D candidates
        # This is a directional signal only
        env_adjustment = int(generic_ballot_lean * 0.5)  # half-weight

    base_fv = 50 + incumbent_bonus + env_adjustment
    base_fv = max(5, min(95, base_fv))  # clamp

    confidence = "low" if (not incumbent_bonus and not env_adjustment) else "medium"

    analysis = (
        f"No live polling is available for this race. "
        f"Fundamentals-based estimate is {base_fv}¢ using incumbency ({incumbent_bonus:+d}) "
        f"and national environment adjustment ({env_adjustment:+d}). "
        f"Confidence is {confidence} — this estimate should be treated as a directional placeholder."
    )
    return base_fv, analysis, confidence
```

### 4b. Wire fundamentals as last resort before skipping

In `run()`, after all three polling sources fail for a senate/house/governor race:

```python
if m_type in ("senate", "house", "governor"):
    # Try Ballotpedia → RaceToTheWH → Wikipedia
    # If all fail:
    fv, analysis, confidence = _fundamentals_fv(market)
    if confidence != "low":
        # We had some structural info — use it
        context = "Fundamentals-based estimate — no live polling available."
        sources = [{"label": "Fundamentals model", "url": None}]
        _finalize_market(market, fv, context, analysis, sources)
        market["_fundamentals_used"] = True
        # Attach financials, transition, etc.
    else:
        # True no-data state — skip the card
        market["_poll_failed"] = True
        continue
```

---

## Phase 5 — Cron Job Verification

After all code changes:

1. `python3 -m py_compile engine.py generator.py collector.py` — syntax check
2. `python3 collector.py` — run collector (background if long)
3. `python3 engine.py` — run engine
4. `python3 generator.py` — generate report
5. Open `output/index.html` in browser — visual inspection
6. Check that no card has placeholder text ("polling source not yet implemented", "_POOL_FAILED_", "no recent polling")
7. Check that `state/analysis.json` has no markets with `analysis` containing "not yet implemented"
8. Verify the cron job definition is unchanged: `hermes cron list` → job 799f5a1b57ba still active

---

## Files to Modify

| File | Changes |
|---|---|
| `engine.py` | Add `_market_type_race()`, `BallotpediaPoller`, `RaceToTheWHPoller`, `_fundamentals_fv()`, update `run()` polling chain, fix FEC lookup by name |
| `generator.py` | Add `get_complete_markets()` filter, use it everywhere |
| `docs/agents.md` | Update polling sources table to reflect wired sources |
| `docs/CHANGELOG.md` | Document all changes |

---

## Verification Checklist

- [ ] No `market["_poll_failed"]` cards appear in `output/index.html`
- [ ] No analysis text contains "polling source not yet implemented" or "_POOL_FAILED_"
- [ ] Senate/House/Governor races show Ballotpedia or RaceToTheWH in sources
- [ ] FEC financials appear on candidate cards where candidate name was found
- [ ] Fundamentals-based cards clearly state "no live polling"
- [ ] Cron job 799f5a1b57ba still active and unchanged
- [ ] `python3 -m py_compile engine.py generator.py` passes with no errors
