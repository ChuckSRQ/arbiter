#!/usr/bin/env python3
"""Collect a Kalshi market snapshot of election and polling markets.

Only collects markets with underlying polling data — tracker markets like
presidential approval and the generic ballot, plus curated election winner
markets. Excludes government-administration markets (Fed, SCOTUS, cabinet, etc.).

Usage:
    python collect_kalshi_public_snapshot.py                          # electoral + polling
    python collect_kalshi_public_snapshot.py --no-political          # empty (no markets)
    python collect_kalshi_public_snapshot.py --fixture path.json      # from fixture
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen


DEFAULT_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
MARKETS_ENDPOINT = "/markets"
DEFAULT_WINDOW_DAYS = 60
DEFAULT_MAX_PAGES = 5
DEFAULT_PAGE_LIMIT = 200

# Sleep between series queries to avoid hammering the API
SERIES_QUERY_DELAY = 0.05  # 50ms

# Curated tracker series. These update frequently and should be represented as
# informational pulse checks, not a pile of duplicate sub-markets.
TRACKER_SERIES = [
    "KXAPRPOTUS",  # RealClearPolitics presidential approval rating
    "KXGENERICBALLOTVOTEHUB",  # Generic congressional ballot spread
]

# Curated election series with real polling behind them.
# Add future election tickers here as Kalshi lists more true election markets.
ELECTION_SERIES = [
    "KXMAYORLA",  # 2026 Los Angeles mayoral election
]

# Elections worth carrying even when they sit outside the default near-term
# window because the polling file still tracks them.
ELECTION_WATCHLIST = [
    "KXMAYORLA",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect a public-only Kalshi snapshot of political and F1 markets expiring soon."
    )
    parser.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    parser.add_argument("--max-pages", "--limit-pages", dest="max_pages", type=int, default=DEFAULT_MAX_PAGES)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--fixture",
        type=Path,
        help="Optional JSON fixture path. Accepts a single Kalshi page object or an array of page objects.",
    )
    parser.add_argument(
        "--no-political",
        action="store_true",
        help="Skip electoral/polling markets.",
    )
    parser.add_argument(
        "--series-only",
        type=Path,
        metavar="FILE",
        help="Write the discovered political series tickers to a file and exit. "
             "Useful for auditing which series are scanned.",
    )
    return parser.parse_args()


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).astimezone(timezone.utc)


def isoformat_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_price_to_cents(value: str | int | float | Decimal | None) -> int | None:
    if value in (None, ""):
        return None
    raw_value = str(value).strip()
    decimal_value = Decimal(raw_value)
    if "." in raw_value or abs(decimal_value) <= 1:
        cents = (decimal_value * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return int(cents)
    return int(decimal_value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def parse_number(value: Any) -> int | float | None:
    if value in (None, ""):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    decimal_value = Decimal(str(value).strip())
    if decimal_value == decimal_value.to_integral():
        return int(decimal_value)
    return float(decimal_value)


def first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def midpoint_cents(bid_cents: int | None, ask_cents: int | None) -> int | None:
    if bid_cents is None or ask_cents is None:
        return None
    midpoint = (Decimal(bid_cents) + Decimal(ask_cents)) / Decimal("2")
    return int(midpoint.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def market_close_time(market: dict[str, Any]) -> datetime | None:
    close_value = first_non_empty(
        market.get("close_time"),
        market.get("expiration_time"),
        market.get("expected_expiration_time"),
        market.get("latest_expiration_time"),
    )
    return parse_datetime(close_value)


def market_closes_within_window(
    market: dict[str, Any],
    *,
    collected_at: datetime,
    window_days: int,
) -> bool:
    if is_watchlisted_market(market):
        return True

    close_time = market_close_time(market)
    if close_time is None:
        return False
    return collected_at <= close_time <= collected_at + timedelta(days=window_days)


def derive_series_ticker(event_ticker: str | None) -> str | None:
    """Extract series_ticker from event_ticker by stripping trailing date/suffix segments.

    event_ticker examples:
      KXTRUMPTIME-26MAY09    → KXTRUMPTIME
      KXTRUMPTIME-26MAY09-H5 → KXTRUMPTIME  (market sub-type)
      KXF1-26-KA             → KXF1
      KXFEDDISSENT-26JUN-MBAR → KXFEDDISSENT
      KXTRUMPDELETE-26MAY-01 → KXTRUMPDELETE

    Strategy: strip trailing -XX segments (date codes, sub-market types) twice.
    """
    if not event_ticker:
        return None
    import re

    def _strip_suffix(s: str) -> str:
        # Strip trailing "-XX" where XX is 2+ alphanumeric chars
        return re.sub(r"-[A-Z0-9]{2,}$", "", s)

    # Strip up to 3 suffix segments (handles nested types like -26MAY09-H5)
    result = _strip_suffix(event_ticker)
    result = _strip_suffix(result)
    result = _strip_suffix(result)
    return result


def market_series_ticker(market: dict[str, Any]) -> str | None:
    return market.get("series_ticker") or derive_series_ticker(market.get("event_ticker"))


def is_tracker_series(series_ticker: str | None) -> bool:
    return series_ticker in TRACKER_SERIES


def is_watchlisted_market(market: dict[str, Any]) -> bool:
    return market_series_ticker(market) in ELECTION_WATCHLIST


def tracker_display_value(raw_market: dict[str, Any]) -> str | None:
    return first_non_empty(raw_market.get("subtitle"), raw_market.get("yes_sub_title"))


def normalize_market(raw_market: dict[str, Any]) -> dict[str, Any]:
    yes_bid_cents = parse_price_to_cents(first_non_empty(raw_market.get("yes_bid"), raw_market.get("yes_bid_dollars")))
    yes_ask_cents = parse_price_to_cents(first_non_empty(raw_market.get("yes_ask"), raw_market.get("yes_ask_dollars")))
    no_bid_cents = parse_price_to_cents(first_non_empty(raw_market.get("no_bid"), raw_market.get("no_bid_dollars")))
    no_ask_cents = parse_price_to_cents(first_non_empty(raw_market.get("no_ask"), raw_market.get("no_ask_dollars")))
    close_time = first_non_empty(raw_market.get("close_time"), raw_market.get("expiration_time"))
    expiration_time = first_non_empty(raw_market.get("expiration_time"), raw_market.get("close_time"))
    rules_text = first_non_empty(raw_market.get("rules_primary"), raw_market.get("rules_secondary"), raw_market.get("subtitle"))

    raw_series_ticker = raw_market.get("series_ticker")
    # When querying by series_ticker, the API doesn't return it in market objects.
    # Derive it from event_ticker instead.
    event_ticker = raw_market.get("event_ticker")
    derived_series = derive_series_ticker(event_ticker)
    series_ticker = raw_series_ticker or derived_series

    return {
        "ticker": raw_market.get("ticker"),
        "title": first_non_empty(raw_market.get("title"), raw_market.get("subtitle")),
        "event_ticker": event_ticker,
        "series_ticker": series_ticker,
        "type": "tracker" if is_tracker_series(series_ticker) else "election",
        "category": raw_market.get("category"),
        "close_time": close_time,
        "expiration_time": expiration_time,
        "candidate_name": first_non_empty(raw_market.get("yes_sub_title"), raw_market.get("subtitle")),
        "tracker_value": tracker_display_value(raw_market),
        "yes_bid_cents": yes_bid_cents,
        "yes_ask_cents": yes_ask_cents,
        "no_bid_cents": no_bid_cents,
        "no_ask_cents": no_ask_cents,
        "yes_midpoint_cents": midpoint_cents(yes_bid_cents, yes_ask_cents),
        "no_midpoint_cents": midpoint_cents(no_bid_cents, no_ask_cents),
        "volume": first_non_empty(parse_number(raw_market.get("volume")), parse_number(raw_market.get("volume_fp"))),
        "open_interest": first_non_empty(
            parse_number(raw_market.get("open_interest")),
            parse_number(raw_market.get("open_interest_fp")),
        ),
        "liquidity": first_non_empty(
            parse_number(raw_market.get("liquidity")),
            parse_number(raw_market.get("liquidity_dollars")),
        ),
        "rules_text": rules_text,
    }


def load_fixture_pages(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return [payload]
    raise ValueError(f"Fixture must be a JSON object or array: {path}")


def fetch_page(
    base_url: str,
    *,
    cursor: str | None,
    status: str = "open",
    series_ticker: str | None = None,
) -> dict[str, Any]:
    params: dict[str, str | int] = {"status": status, "limit": DEFAULT_PAGE_LIMIT}
    if cursor:
        params["cursor"] = cursor
    if series_ticker:
        params["series_ticker"] = series_ticker

    url = f"{base_url.rstrip('/')}{MARKETS_ENDPOINT}?{urlencode(params)}"
    with urlopen(url, timeout=30) as response:
        return json.load(response)


def iter_market_pages(
    base_url: str,
    *,
    max_pages: int,
    fixture_path: Path | None,
    series_ticker: str | None = None,
) -> list[dict[str, Any]]:
    if fixture_path is not None:
        return load_fixture_pages(fixture_path)[:max_pages]

    pages: list[dict[str, Any]] = []
    cursor: str | None = None

    for _ in range(max_pages):
        page = fetch_page(base_url, cursor=cursor, series_ticker=series_ticker)
        pages.append(page)
        cursor = page.get("cursor") or None
        if not cursor:
            break

    return pages


def curated_political_series_tickers() -> list[str]:
    return [*TRACKER_SERIES, *ELECTION_SERIES]


def collect_markets_for_series(
    base_url: str,
    series_ticker: str,
    max_pages: int,
) -> list[dict[str, Any]]:
    """Fetch all market pages for a single series ticker.

    Uses status=open which returns active political markets.
    Returns a flat list of raw market dicts.
    """
    pages = iter_market_pages(base_url, max_pages=max_pages, fixture_path=None, series_ticker=series_ticker)
    return [market for page in pages for market in page.get("markets", [])]


def representative_tracker_market(markets: list[dict[str, Any]]) -> dict[str, Any]:
    def sort_key(market: dict[str, Any]) -> tuple[float, float, str]:
        volume = market.get("volume")
        volume_score = float(volume) if isinstance(volume, (int, float)) else -1.0
        center_price = first_non_empty(market.get("yes_midpoint_cents"), market.get("yes_ask_cents"), 50)
        distance_from_center = abs(float(center_price) - 50.0)
        return (-distance_from_center, volume_score, str(market.get("ticker") or ""))

    representative = max(markets, key=sort_key)
    if len(markets) == 1:
        return representative

    return {
        **representative,
        "tracker_components": [market["ticker"] for market in sorted(markets, key=lambda market: str(market.get("ticker") or ""))],
    }


def collapse_tracker_markets(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    collapsed: list[dict[str, Any]] = []
    tracker_groups: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for market in markets:
        if market.get("type") != "tracker":
            collapsed.append(market)
            continue

        key = (
            str(market.get("series_ticker") or ""),
            str(market.get("event_ticker") or market.get("ticker") or ""),
        )
        tracker_groups.setdefault(key, []).append(market)

    collapsed.extend(representative_tracker_market(group) for _, group in sorted(tracker_groups.items()))
    return collapsed


def build_snapshot(
    *,
    base_url: str,
    window_days: int,
    max_pages: int,
    fixture_path: Path | None,
    collected_at: datetime | None = None,
    include_political: bool = True,
) -> dict[str, Any]:
    collected_at = collected_at or datetime.now().astimezone()

    all_markets_raw: list[dict[str, Any]] = []

    # Curated election/tracker series collection only.
    political_tickers: list[str] = []
    if include_political:
        political_tickers = curated_political_series_tickers()
        print(f"Scanning {len(political_tickers)} curated election/tracker series", file=__import__("sys").stderr)

        for ticker in political_tickers:
            try:
                markets = collect_markets_for_series(base_url, ticker, max_pages)
                all_markets_raw.extend(markets)
                time.sleep(SERIES_QUERY_DELAY)  # rate limit courtesy
            except (OSError, ValueError) as error:
                print(f"Warning: failed to collect {ticker}: {error}", file=__import__("sys").stderr)

    # Deduplicate by ticker
    normalized_markets = collapse_tracker_markets([
        normalize_market(market)
        for market in all_markets_raw
        if market_closes_within_window(market, collected_at=collected_at, window_days=window_days)
    ])

    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for m in normalized_markets:
        ticker = m.get("ticker") or ""
        if ticker not in seen:
            seen.add(ticker)
            deduped.append(m)

    deduped.sort(key=lambda market: (market.get("expiration_time") or "", market.get("ticker") or ""))

    return {
        "collected_at": isoformat_utc(collected_at),
        "source": {
            "base_url": base_url,
            "endpoint": MARKETS_ENDPOINT,
        },
        "filters": {
            "window_days": window_days,
            "status": "open",
            "include_political": include_political,
            "electoral_series_count": len(political_tickers) if include_political else 0,
            "max_pages": max_pages,
        },
        "markets": deduped,
    }


def default_output_path(collected_at: datetime) -> Path:
    return Path("data") / "kalshi_snapshot" / f"{collected_at.date().isoformat()}.json"


def write_snapshot(snapshot: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(f"{json.dumps(snapshot, indent=2)}\n", encoding="utf-8")
    return output_path


def main() -> int:
    args = parse_args()
    collected_at = datetime.now().astimezone()

    # --series-only mode: just dump the curated tickers the collector will scan.
    if args.series_only:
        political_tickers = curated_political_series_tickers()
        args.series_only.write_text("\n".join(sorted(political_tickers)) + "\n")
        print(f"Wrote {len(political_tickers)} political series tickers to {args.series_only}")
        return 0

    snapshot = build_snapshot(
        base_url=args.base_url,
        window_days=args.window_days,
        max_pages=args.max_pages,
        fixture_path=args.fixture,
        collected_at=collected_at,
        include_political=not args.no_political,
    )
    output_path = write_snapshot(snapshot, args.output or default_output_path(collected_at))

    print(
        json.dumps(
            {
                "output": str(output_path),
                "markets": len(snapshot["markets"]),
                "electoral_series_scanned": snapshot["filters"].get("electoral_series_count", 0),
                "include_political": snapshot["filters"]["include_political"],
                "window_days": snapshot["filters"]["window_days"],
                "base_url": snapshot["source"]["base_url"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
