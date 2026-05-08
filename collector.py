"""Arbiter Collector — discovers qualifying Kalshi election markets.

Public API only (no auth needed for market discovery).
Filters to Kalshi Elections category markets trading out within the next 60 days.
Writes results to state/analysis.json via state.py helpers.
"""

import json
import re
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

from state import read_state, write_state, upsert_market, touch_last_run

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
WINDOW_DAYS = 60
REQUEST_DELAY = 0.35  # seconds between API calls to avoid 429

EXCLUDED_SERIES = (
    "PRESADMIN",  # admin actions, not elections
)

EXCLUDED_TITLE_PATTERNS = (
    r"approval rating",
    r"generic ballot",
    r"votehub.*margin",
    r"margin.*bracket",
)


def _api_get(path, params=None, retries=2):
    """Hit a public Kalshi API endpoint. Returns parsed JSON."""
    url = f"{BASE_URL}{path}"
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url += f"?{query}"

    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    for attempt in range(retries + 1):
        try:
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


def discover_series():
    """Get all election series from Kalshi events pagination."""
    all_series = set()
    cursor = None

    while True:
        params = {"category": "Elections", "limit": "500"}
        if cursor:
            params["cursor"] = cursor

        data = _api_get("/events", params)
        if not data:
            if not all_series:
                print("  Failed to fetch election events")
            break

        events = data.get("events", [])
        if not events:
            break

        for event in events:
            series_ticker = event.get("series_ticker")
            if series_ticker and series_ticker not in EXCLUDED_SERIES:
                all_series.add(series_ticker)

        cursor = data.get("cursor")
        if not cursor:
            break

    print(f"  Found {len(all_series)} election series")
    return sorted(all_series)


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
    """Parse the trading cutoff date for filtering."""
    for field in (
        "close_time",
        "expiration_time",
        "expected_expiration_time",
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


def collect():
    """Main collection loop. Returns number of new markets discovered."""
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=WINDOW_DAYS)

    print(f"Collector starting — {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Window: {WINDOW_DAYS} days (cutoff {cutoff.strftime('%Y-%m-%d')})")

    # Discover election series
    series_list = discover_series()
    if not series_list:
        print("  No election series found. Check API connectivity.")
        return 0

    # Load state
    state = read_state()
    existing_tickers = {m["ticker"] for m in state["markets"]}
    new_count = 0

    # Fetch markets for each series
    for i, series_ticker in enumerate(series_list):
        if i > 0:
            time.sleep(REQUEST_DELAY)
        markets = fetch_markets_for_series(series_ticker)
        if not markets:
            continue

        for m in markets:
            ticker = m.get("ticker", "")
            title = m.get("title", "")

            if _is_excluded_by_title(title):
                continue

            cutoff_date = _parse_close_date(m)

            # Skip if no trading cutoff date
            if not cutoff_date:
                continue

            # Make cutoff timezone-aware if it isn't
            if cutoff_date.tzinfo is None:
                cutoff_date = cutoff_date.replace(tzinfo=timezone.utc)

            # Skip if already expired (past) or outside future window
            if cutoff_date < now:
                continue
            if cutoff_date > cutoff:
                continue

            # Skip if already in state
            if ticker in existing_tickers:
                continue

            event_ticker = m.get("event_ticker", "")
            price = _get_market_price(m)

            market_data = {
                "ticker": ticker,
                "title": title,
                "race_title": title,  # engine.py will refine this
                "candidate_name": m.get("yes_sub_title"),
                "event_ticker": event_ticker,  # race key for grouping
                "event_date": _parse_event_date(m),
                "series_ticker": m.get("series_ticker") or series_ticker,
                "market_price": price,
            }

            upsert_market(state, market_data)
            existing_tickers.add(ticker)
            new_count += 1
            print(
                f"  + {ticker} | {title[:50]} | {price}¢ | cutoff {cutoff_date.strftime('%Y-%m-%d')}"
            )

    # Update last_run and save
    touch_last_run(state)
    write_state(state)

    total = len(state["markets"])
    print(f"\nCollector done. {new_count} new markets, {total} total in state.")
    return new_count


if __name__ == "__main__":
    collect()
