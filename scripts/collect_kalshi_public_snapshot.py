#!/usr/bin/env python3
"""Collect a public-only Kalshi market snapshot for markets closing soon."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen


DEFAULT_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
MARKETS_ENDPOINT = "/markets"
DEFAULT_WINDOW_DAYS = 30
DEFAULT_MAX_PAGES = 5
DEFAULT_PAGE_LIMIT = 200


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect a public-only Kalshi snapshot of open markets expiring soon."
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
    close_time = market_close_time(market)
    if close_time is None:
        return False

    return collected_at <= close_time <= collected_at + timedelta(days=window_days)


def normalize_market(raw_market: dict[str, Any]) -> dict[str, Any]:
    yes_bid_cents = parse_price_to_cents(first_non_empty(raw_market.get("yes_bid"), raw_market.get("yes_bid_dollars")))
    yes_ask_cents = parse_price_to_cents(first_non_empty(raw_market.get("yes_ask"), raw_market.get("yes_ask_dollars")))
    no_bid_cents = parse_price_to_cents(first_non_empty(raw_market.get("no_bid"), raw_market.get("no_bid_dollars")))
    no_ask_cents = parse_price_to_cents(first_non_empty(raw_market.get("no_ask"), raw_market.get("no_ask_dollars")))
    close_time = first_non_empty(raw_market.get("close_time"), raw_market.get("expiration_time"))
    expiration_time = first_non_empty(raw_market.get("expiration_time"), raw_market.get("close_time"))
    rules_text = first_non_empty(raw_market.get("rules_primary"), raw_market.get("rules_secondary"), raw_market.get("subtitle"))

    return {
        "ticker": raw_market.get("ticker"),
        "title": first_non_empty(raw_market.get("title"), raw_market.get("subtitle")),
        "event_ticker": raw_market.get("event_ticker"),
        "series_ticker": raw_market.get("series_ticker"),
        "category": raw_market.get("category"),
        "close_time": close_time,
        "expiration_time": expiration_time,
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


def fetch_page(base_url: str, *, cursor: str | None) -> dict[str, Any]:
    params = {"status": "open", "limit": DEFAULT_PAGE_LIMIT}
    if cursor:
        params["cursor"] = cursor

    url = f"{base_url.rstrip('/')}{MARKETS_ENDPOINT}?{urlencode(params)}"
    with urlopen(url, timeout=30) as response:
        return json.load(response)


def iter_market_pages(base_url: str, *, max_pages: int, fixture_path: Path | None) -> list[dict[str, Any]]:
    if fixture_path is not None:
        return load_fixture_pages(fixture_path)[:max_pages]

    pages: list[dict[str, Any]] = []
    cursor: str | None = None

    for _ in range(max_pages):
        page = fetch_page(base_url, cursor=cursor)
        pages.append(page)
        cursor = page.get("cursor") or None
        if not cursor:
            break

    return pages


def build_snapshot(
    *,
    base_url: str,
    window_days: int,
    max_pages: int,
    fixture_path: Path | None,
    collected_at: datetime | None = None,
) -> dict[str, Any]:
    collected_at = collected_at or datetime.now().astimezone()
    pages = iter_market_pages(base_url, max_pages=max_pages, fixture_path=fixture_path)

    normalized_markets = [
        normalize_market(market)
        for page in pages
        for market in page.get("markets", [])
        if market_closes_within_window(market, collected_at=collected_at, window_days=window_days)
    ]
    normalized_markets.sort(key=lambda market: (market.get("expiration_time") or "", market.get("ticker") or ""))

    return {
        "collected_at": isoformat_utc(collected_at),
        "source": {
            "base_url": base_url,
            "endpoint": MARKETS_ENDPOINT,
        },
        "filters": {
            "window_days": window_days,
            "status": "open",
            "max_pages": max_pages,
        },
        "markets": normalized_markets,
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
    snapshot = build_snapshot(
        base_url=args.base_url,
        window_days=args.window_days,
        max_pages=args.max_pages,
        fixture_path=args.fixture,
        collected_at=collected_at,
    )
    output_path = write_snapshot(snapshot, args.output or default_output_path(collected_at))

    print(
        json.dumps(
            {
                "output": str(output_path),
                "markets": len(snapshot["markets"]),
                "status": snapshot["filters"]["status"],
                "window_days": snapshot["filters"]["window_days"],
                "base_url": snapshot["source"]["base_url"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
