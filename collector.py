"""Arbiter Collector — discovers qualifying Kalshi political markets.

Public API only (no auth needed for market discovery).
Filters to pollable political series, ≤60 days from expiry.
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

# Series prefixes that have underlying polling data
POLLABLE_PREFIXES = (
    "KXAPRPOTUS",
    "KXTRUMPAPPROVAL",
    "KXGOVTAPPROVAL",
    "KXGENERICBALLOT",
    "KXMAYOR",
    "SENATE",
    "HOUSE",
    "GOVPARTY",
    "PRES",
)

# Specific series to exclude even if prefix matches
EXCLUDED_SERIES = (
    "PRESADMIN",  # admin actions, not elections
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


def _is_pollable(series_ticker):
    """Check if a series has underlying polling data."""
    if not series_ticker:
        return False
    if series_ticker in EXCLUDED_SERIES:
        return False
    return any(series_ticker.startswith(p) for p in POLLABLE_PREFIXES)


def _derive_series_ticker(event_ticker):
    """Derive series_ticker from event_ticker by stripping suffixes.

    KXTRUMPTIME-26MAY09 -> KXTRUMPTIME
    SENATEWI-28 -> SENATEWI
    KXF1-26-KA -> KXF1
    """
    t = event_ticker
    for _ in range(4):
        t = re.sub(r"-[^-]+$", "", t)
        # Check if what remains is a known series prefix base
        # Stop stripping when no more hyphens
        if "-" not in t:
            break
    return t


def discover_series():
    """Get all series from Kalshi, return only pollable political ones."""
    data = _api_get("/series", {"limit": "500"})
    if not data:
        print("  Failed to fetch series list")
        return []

    all_series = [s.get("ticker", "") for s in data.get("series", [])]
    pollable = [s for s in all_series if _is_pollable(s)]

    print(f"  Found {len(all_series)} total series, {len(pollable)} pollable political")
    return pollable


def fetch_markets_for_series(series_ticker):
    """Get all markets for a series. Returns list of market dicts."""
    data = _api_get("/markets", {"series_ticker": series_ticker, "limit": "100"})
    if not data:
        return []
    return data.get("markets", [])


def _parse_close_date(market):
    """Parse market close/expiry date. Prefers expected_expiration_time (election date)
    over close_time (settlement date) for markets that use different dates."""
    for field in ("expected_expiration_time", "close_time", "expiration_date", "expiry_date"):
        val = market.get(field)
        if val:
            try:
                # ISO format with or without timezone
                val = val.replace("Z", "+00:00")
                return datetime.fromisoformat(val)
            except (ValueError, TypeError):
                continue
    return None


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

    # Discover pollable series
    series_list = discover_series()
    if not series_list:
        print("  No pollable series found. Check API connectivity.")
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
            close = _parse_close_date(m)

            # Skip if no close date
            if not close:
                continue

            # Make close timezone-aware if it isn't
            if close.tzinfo is None:
                close = close.replace(tzinfo=timezone.utc)

            # Skip if already expired (past) or outside future window
            if close < now:
                continue
            if close > cutoff:
                continue

            # Skip if already in state
            if ticker in existing_tickers:
                continue

            # Derive series ticker from event_ticker
            event_ticker = m.get("event_ticker", "")
            derived_series = _derive_series_ticker(event_ticker) if event_ticker else series_ticker

            # Double-check pollable (derived series might differ)
            if not _is_pollable(derived_series):
                continue

            price = _get_market_price(m)

            market_data = {
                "ticker": ticker,
                "title": title,
                "race_title": title,  # engine.py will refine this
                "candidate_name": m.get("yes_sub_title"),
                "event_ticker": event_ticker,  # race key for grouping
                "election_date": close.strftime("%Y-%m-%d"),
                "series_ticker": series_ticker,
                "market_price": price,
            }

            upsert_market(state, market_data)
            existing_tickers.add(ticker)
            new_count += 1
            print(f"  + {ticker} | {title[:50]} | {price}¢ | closes {close.strftime('%Y-%m-%d')}")

    # Update last_run and save
    touch_last_run(state)
    write_state(state)

    total = len(state["markets"])
    print(f"\nCollector done. {new_count} new markets, {total} total in state.")
    return new_count


if __name__ == "__main__":
    collect()
