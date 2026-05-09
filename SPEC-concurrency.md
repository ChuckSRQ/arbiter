# Arbiter Collector Concurrency — SPEC

## Problem

Sequential fetching of 1,290 election series times out:
```
1,290 series × 0.35s delay = 7.5 min minimum
120s timeout in no_agent script
```

## Goal

Reduce collector run time from ~7.5 min to ~45-60 sec by fetching markets for multiple series concurrently.

---

## Design

### Threading Model

- `concurrent.futures.ThreadPoolExecutor` (Python stdlib, Python 3.9+)
- `WORKER_COUNT = 10` — 10 concurrent workers
- Each worker independently calls `fetch_markets_for_series(ticker)` then applies market-level filters
- Main thread handles state mutations and final write

### Data Flow

```
Main thread                     Worker threads (10 concurrent)
────────────────                 ─────────────────────────────────────────
discover_series()
  → list of 1,290 tickers

for ticker in tickers:
  → executor.submit(
      _fetch_and_filter_series,
      ticker
    )

                               _fetch_and_filter_series(ticker):
                                 markets = fetch_markets_for_series(ticker)
                                 return [_filter_market(m, ticker)
                                         for m in markets]

Collect futures as_completed:
  for future in as_completed(futures):
    result = future.result()
    for market_data in result:
      upsert_market(state, market_data)

write_state(state)
```

### Filtering

Market-level filters (title exclusion, date parse, date window, dedup) run inside workers. Only filtered market dicts cross the thread boundary — keeps memory and result-handling lightweight.

### Rate Limiting

- Each worker adds a small random jitter `random.uniform(0, 0.1)` before its API call — avoids all 10 workers hitting the API at the exact same instant
- Existing `_api_get` retry logic (3 retries, 429 backoff) stays unchanged

### What Stays the Same

- All filtering logic (title exclusions, date window, existing ticker dedup)
- State write behavior (one write at end)
- Output format and print statements
- `REQUEST_DELAY` constant (used for jitter)
- `WINDOW_DAYS`, `EXCLUDED_SERIES`, `EXCLUDED_TITLE_PATTERNS`
- `no_agent` script and cron job (they call `collect()` as before)

---

## Changes to `collector.py`

### 1. Imports (top of file)
```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
```

### 2. Constant
```python
WORKER_COUNT = 10
```

### 3. New function `_fetch_and_filter_series`
```python
def _fetch_and_filter_series(series_ticker):
    """Fetch and filter markets for one series. Runs in worker thread."""
    # Rate-limit jitter
    time.sleep(random.uniform(0, 0.1))

    markets = fetch_markets_for_series(series_ticker)
    if not markets:
        return []

    results = []
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=WINDOW_DAYS)

    for m in markets:
        ticker = m.get("ticker", "")
        title = m.get("title", "")

        if _is_excluded_by_title(title):
            continue

        cutoff_date = _parse_close_date(m)
        if not cutoff_date:
            continue
        if cutoff_date.tzinfo is None:
            cutoff_date = cutoff_date.replace(tzinfo=timezone.utc)
        if cutoff_date < now:
            continue
        if cutoff_date > cutoff:
            continue

        event_ticker = m.get("event_ticker", "")
        price = _get_market_price(m)

        results.append({
            "ticker": ticker,
            "title": title,
            "race_title": title,
            "candidate_name": m.get("yes_sub_title"),
            "event_ticker": event_ticker,
            "event_date": _parse_event_date(m),
            "series_ticker": m.get("series_ticker") or series_ticker,
            "market_price": price,
        })

    return results
```

### 4. Replace sequential loop in `collect()` (lines 171–225)

Old:
```python
for i, series_ticker in enumerate(series_list):
    if i > 0:
        time.sleep(REQUEST_DELAY)
    markets = fetch_markets_for_series(series_ticker)
    ...
```

New:
```python
print(f"  Fetching markets for {len(series_list)} series with {WORKER_COUNT} workers...")

all_markets = []
with ThreadPoolExecutor(max_workers=WORKER_COUNT) as executor:
    futures = {
        executor.submit(_fetch_and_filter_series, st): st
        for st in series_list
    }
    for future in as_completed(futures):
        series_ticker = futures[future]
        try:
            results = future.result()
            all_markets.extend(results)
        except Exception as e:
            print(f"    Error fetching {series_ticker}: {e}")

state = read_state()
existing_tickers = {m["ticker"] for m in state["markets"]}
new_count = 0

for market_data in all_markets:
    ticker = market_data["ticker"]
    if ticker in existing_tickers:
        continue
    upsert_market(state, market_data)
    existing_tickers.add(ticker)
    new_count += 1
    print(
        f"  + {ticker} | {market_data['title'][:50]} | "
        f"{market_data['market_price']}¢ | "
        f"cutoff {_parse_close_date_str(market_data)}"
    )
```

Note: `_parse_close_date_str` is a small helper that formats the cutoff date from `market_data` for the print statement. Alternatively, keep the cutoff date in the returned dict.

### 5. Add `_filter_close_date` helper

```python
def _filter_close_date_str(market_data):
    """Get cutoff date string for print output."""
    # market_data already has parsed fields — reconstruct from ticker
    # or add 'cutoff_date' to market_data dict before returning
    return market_data.get("cutoff_date_str", "")
```

Alternatively, add `cutoff_date_str` to the dict inside `_fetch_and_filter_series` before returning.

---

## Files Changed

| File | Change |
|------|--------|
| `collector.py` | Full concurrency refactor |

---

## Verification

```bash
# Should complete in ~45-60 sec
time python3 collector.py

# Confirm LA mayor markets present
python3 -c "
import json
s = json.load(open('state/analysis.json'))
lamayor = [m for m in s['markets'] if 'LAMAYOR' in m.get('ticker','')]
print(f'LA mayor markets: {len(lamayor)}')
for m in lamayor:
    print(f'  {m[\"ticker\"]} | {m[\"title\"]} | {m[\"market_price\"]}c')
"
```

---

## Risk & Mitigations

| Risk | Mitigation |
|------|-----------|
| 429 rate limit from 10 concurrent workers | Jitter + existing `_api_get` 3-retry backoff; `WORKER_COUNT` is tunable |
| Thread safety on state | State mutations only in main thread after results collected — no locking needed |
| Memory pressure from 1,290 × 10-100 markets in flight | Market-level filtering inside workers — only filtered results (tens to low hundreds) return to main thread |
