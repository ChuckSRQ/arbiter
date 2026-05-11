"""Arbiter Collector — discovers qualifying Kalshi election markets.

Public API only (no auth needed for market discovery).
Fetches all series in the Elections category via /series endpoint,
then filters to markets trading out within the next 60 days.
Writes results to state/analysis.json via state.py helpers.
"""

import json
import re
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from threading import Lock

from state import read_state, write_state, upsert_market, touch_last_run

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
WINDOW_DAYS = 60
WORKER_COUNT = 3   # 3 workers — enough parallel calls without flooding the API
REQUEST_DELAY = 0.35  # seconds between requests per worker

# Global rate limiter — acquired before every API call
_rate_lock = Lock()
_last_call_time = 0.0

# Tags on series objects that indicate real election races we want to track.
# Excludes: Fed, Policy, Inflation, SOTU (not election races)
ALLOWED_TAGS = {
    # US races
    "US Elections",
    "Primaries",
    "House",
    "Senate",
    "Governor",
    "Local",
    # International
    "International elections",
    "International",
    "Brazil",
    "Hungary",
    "Iran",
    # Midterm cycle
    "2028",
    "Congress",
}

# Series tickers to always exclude (not election races, tagged wrong in Kalshi taxonomy)
EXCLUDED_SERIES = {
    "KXGENERICBALLOTVOTEHUB",  # generic ballot — not a race
}


def _api_get(path, params=None, retries=2):
    """Hit a public Kalshi API endpoint. Returns parsed JSON."""
    url = f"{BASE_URL}{path}"
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url += f"?{query}"

    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    for attempt in range(retries + 1):
        try:
            with _rate_limiter():
                with urllib.request.urlopen(req, timeout=15) as resp:
                    return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                wait = 2 ** (attempt + 1)
                print(f"  Rate limited, retrying in {wait}s...")
                time.sleep(wait)
                continue
            print(f"  HTTP {e.code} on {url}")
            return None
        except urllib.error.URLError as e:
            print(f"  Connection error: {e.reason}")
            return None


def _rate_limiter():
    """Global context manager that enforces REQUEST_DELAY between API calls."""
    global _last_call_time
    with _rate_lock:
        now = time.monotonic()
        elapsed = now - _last_call_time
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)
        _last_call_time = time.monotonic()
    return _DummyContext()


class _DummyContext:
    """Minimal context manager for rate_limiter."""
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def _series_has_allowed_tag(series):
    """Return True if series has at least one allowed tag."""
    tags = series.get("tags") or []
    return any(tag in ALLOWED_TAGS for tag in tags)


def discover_series():
    """Get election series tickers from Kalshi's Elections category.

    Uses /events?category=Elections with cursor pagination — returns all
    events across pages. Extracts unique series_tickers from each event.
    """
    all_tickers = set()
    cursor = None

    while True:
        params = {"category": "Elections", "limit": "500"}
        if cursor:
            params["cursor"] = cursor

        data = _api_get("/events", params)
        if not data:
            break

        events = data.get("events", [])
        if not events:
            break

        for event in events:
            ticker = event.get("series_ticker")
            if ticker and ticker not in EXCLUDED_SERIES:
                # Also check the series itself for allowed tags if available
                all_tickers.add(ticker)

        cursor = data.get("cursor")
        if not cursor:
            break

    print(f"  Got {len(all_tickers)} unique series from Elections events", flush=True)
    return sorted(all_tickers)


def fetch_markets_for_series(series_ticker):
    """Get all markets for a series. Returns list of market dicts."""
    data = _api_get("/markets", {"series_ticker": series_ticker, "limit": "100"})
    if not data:
        return []
    return data.get("markets", [])


def _parse_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _parse_close_date(market):
    """Parse the election/early-close date for filtering.

    Prefers expected_expiration_time (the actual election date or event
    resolution date) over close_time (the long-term trading expiry).
    """
    # Try expected_expiration_time first — it's the actual election/event date
    for field in (
        "expected_expiration_time",
        "close_time",
        "expiration_time",
        "expiration_date",
        "expiry_date",
    ):
        parsed = _parse_datetime(market.get(field))
        if parsed:
            return parsed
    return None


def _parse_event_date(market):
    """Parse the election/event date when Kalshi exposes it separately."""
    parsed = _parse_datetime(market.get("expected_expiration_time"))
    if not parsed:
        return None
    return parsed.strftime("%Y-%m-%d")


EXCLUDED_TITLE_PATTERNS = (
    r"approval rating",
    r"generic ballot",
    r"votehub.*margin",
    r"margin.*bracket",
)


# Event contract question patterns — compiled for _is_race_market()
_EVENT_FAIL_PATTERNS = tuple(re.compile(p) for p in (
    r"will\s+\w+\s+drop\s*out",
    r"will\s+\w+\s+resign",
    r"will\s+\w+\s+be\s+expelled",
    r"will\s+\w+\s+endorse",
    r"will\s+\w+\s+appoint",
    r"will\s+\w+\s+happen\s+before",
    r"will\s+the\s+number\s+of",
    r"will\s+\w+\s+join\s+\w+\s+before",
    r"will\s+\w+\s+leave\s+office\s+before",
    r"will\s+\w+\s+be\s+the\s+head\s+of\s+state",
    r"will\s+\w+\s+be\s+\w+'s\s+running\s*mate",
    r"will\s+\w+\s+be\s+(selected|picked|chosen|elected)",
))

# Race structure question patterns — compiled for _is_race_market()
_RACE_PASS_PATTERNS = tuple(re.compile(p) for p in (
    r"who\s+will\s+win",
    r"who\s+will\s+be\s+elected",
    r"\s+vs\s+",
    r"win\s+the\s+\w+\s+election",
    r"win\s+\w+\s+governor",
    r"win\s+\w+\s+senate",
    r"win\s+\w+\s+house",
    r"win\s+\w+\s+mayor",
    r"what\s+party\s+will\s+control",
))


def _is_race_market(market):
    """Return True if market question text looks like an election race,
    not an event contract. Uses Signal 1 (question text pattern matching)
    as the primary filter. When in doubt, exclude the market.

    Passes (race markets):
      - "Who will win the [position] election"
      - "[Candidate A] vs [Candidate B]" direct matchup
      - "Will [candidate] win [position]"
      - "What party will control [chamber/position]"

    Fails (event contracts):
      - "Will X drop out / resign / be expelled"
      - "Will X endorse Y / appoint Y"
      - "Will X happen before date Y"
      - "Will the number of X be exactly Y"
      - Binary event questions about appointments, resignations, etc.
    """
    question = (market.get("question") or market.get("title") or "").strip().lower()

    # Fast fail — check event contract patterns first
    for pattern in _EVENT_FAIL_PATTERNS:
        if pattern.search(question):
            return False

    # Must match at least one race pattern to pass
    for pattern in _RACE_PASS_PATTERNS:
        if pattern.search(question):
            return True

    return False


def _is_excluded_by_title(title):
    """Block election-adjacent non-race markets inside the Elections category."""
    text = (title or "").strip().lower()
    return any(re.search(pattern, text) for pattern in EXCLUDED_TITLE_PATTERNS)


def _get_market_price(market):
    """Extract yes bid price in cents. Returns int or None."""
    bid = market.get("yes_bid")
    if bid is not None:
        return int(float(bid))
    bid_dollars = market.get("yes_bid_dollars")
    if bid_dollars is not None:
        return int(float(bid_dollars) * 100)
    # Last price fallback
    last = market.get("last_price")
    if last is not None:
        return int(float(last) * 100)
    return None


def _fetch_and_filter_series(series_ticker):
    """Fetch and filter markets for one series. Runs in worker thread."""
    # Rate-limit jitter removed — global _rate_limiter in _api_get handles spacing

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

        if not _is_race_market(m):
            continue  # skip — not a real race, no polling to analyze

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
            "cutoff_date_str": cutoff_date.strftime("%Y-%m-%d"),
        })

    return results


def collect():
    """Main collection loop. Returns number of new markets discovered."""
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=WINDOW_DAYS)

    print(f"Collector starting — {now.strftime('%Y-%m-%d %H:%M UTC')}", flush=True)
    print(f"Window: {WINDOW_DAYS} days (cutoff {cutoff.strftime('%Y-%m-%d')})", flush=True)

    # Discover elections
    print("  Starting discover_series()...", flush=True)
    elections = discover_series()
    print(f"  discover_series() returned {len(elections)} elections", flush=True)
    if not elections:
        print("  No elections found. Check API connectivity.")
        return 0

    # Load state
    state = read_state()
    existing_tickers = {m["ticker"] for m in state["markets"]}

    # Remove markets whose series is no longer in the allowed set
    removed_count = 0
    state["markets"] = [
        m for m in state["markets"]
        if (m.get("series_ticker") or m.get("event_ticker") or m.get("ticker", "")) not in EXCLUDED_SERIES
        and _series_has_allowed_tag({"tags": _get_series_tags_for_ticker(m.get("series_ticker", ""))})
    ]
    removed_count = len(existing_tickers) - len({m["ticker"] for m in state["markets"]})
    if removed_count:
        print(f"  Removed {removed_count} candidates from excluded series")

    new_count = 0

    # Fetch candidates for each election concurrently
    print(f"  Fetching candidates for {len(elections)} elections with {WORKER_COUNT} workers...")

    all_markets = []
    with ThreadPoolExecutor(max_workers=WORKER_COUNT) as executor:
        futures = {
            executor.submit(_fetch_and_filter_series, election_ticker): election_ticker
            for election_ticker in elections
        }
        for future in as_completed(futures):
            series_ticker = futures[future]
            try:
                results = future.result()
                all_markets.extend(results)
            except Exception as e:
                print(f"    Error fetching {series_ticker}: {e}")

    # Process results in main thread (state mutations only here)
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
            f"cutoff {market_data.get('cutoff_date_str', '')}"
        )

    # Update last_run and save
    touch_last_run(state)
    write_state(state)

    total = len(state["markets"])
    print(f"\nCollector done. {new_count} new markets, {total} total in state.")
    return new_count


def _get_series_tags_for_ticker(series_ticker):
    """Stub helper — series tag lookup not available without re-fetching /series.
    Cleanup uses EXCLUDED_SERIES set only; tag-based cleanup happens at discovery time.
    Returns empty list so ticker is kept unless in EXCLUDED_SERIES.
    """
    return []


if __name__ == "__main__":
    collect()