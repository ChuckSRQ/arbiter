#!/usr/bin/env python3
"""Collect a read-only Kalshi portfolio snapshot with safe local fallback."""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
BALANCE_ENDPOINT = "/portfolio/balance"
POSITIONS_ENDPOINT = "/portfolio/positions"
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_DOTENV_PATH = Path(".env")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect a read-only Kalshi portfolio snapshot with safe missing-credential fallback."
    )
    parser.add_argument("--base-url")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--fixture",
        type=Path,
        help="Optional sanitized fixture path. Accepts raw balance/positions payloads or normalized output.",
    )
    return parser.parse_args()


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).astimezone(timezone.utc)


def isoformat_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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


def parse_cents(value: Any) -> int | None:
    if value in (None, ""):
        return None

    raw_value = str(value).strip()
    decimal_value = Decimal(raw_value)
    if "." in raw_value or abs(decimal_value) <= 1:
        cents = (decimal_value * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return int(cents)
    return int(decimal_value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def load_dotenv_values(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, raw_value = stripped.split("=", 1)
        values[key.strip()] = raw_value.strip().strip('"').strip("'")
    return values


def resolve_setting(name: str, env: Mapping[str, str], dotenv_values: Mapping[str, str]) -> str | None:
    return first_non_empty(env.get(name), dotenv_values.get(name))


def resolve_base_url(
    base_url: str | None,
    env: Mapping[str, str],
    dotenv_values: Mapping[str, str],
) -> str:
    return first_non_empty(base_url, resolve_setting("KALSHI_BASE_URL", env, dotenv_values), DEFAULT_BASE_URL)


def signature_message(timestamp_ms: str, method: str, request_url: str) -> bytes:
    parsed = urlsplit(request_url)
    signed_path = parsed.path or request_url
    return f"{timestamp_ms}{method.upper()}{signed_path}".encode("utf-8")


def sign_message(message: bytes, private_key_path: Path) -> str:
    completed = subprocess.run(
        [
            "openssl",
            "dgst",
            "-sha256",
            "-sign",
            str(private_key_path),
            "-sigopt",
            "rsa_padding_mode:pss",
            "-sigopt",
            "rsa_pss_saltlen:-1",
            "-binary",
        ],
        input=message,
        capture_output=True,
        check=True,
    )
    return base64.b64encode(completed.stdout).decode("ascii")


def build_auth_headers(
    *,
    key_id: str,
    private_key_path: Path,
    method: str,
    request_url: str,
    timestamp_ms: str | None = None,
) -> dict[str, str]:
    resolved_timestamp = timestamp_ms or str(int(datetime.now(tz=timezone.utc).timestamp() * 1000))
    signature = sign_message(signature_message(resolved_timestamp, method, request_url), private_key_path)
    return {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-TIMESTAMP": resolved_timestamp,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "Accept": "application/json",
    }


def fetch_json(
    *,
    base_url: str,
    endpoint: str,
    key_id: str,
    private_key_path: Path,
) -> dict[str, Any]:
    request_url = f"{base_url.rstrip('/')}{endpoint}"
    request = Request(
        request_url,
        method="GET",
        headers=build_auth_headers(
            key_id=key_id,
            private_key_path=private_key_path,
            method="GET",
            request_url=request_url,
        ),
    )
    with urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
        return json.load(response)


def normalize_balance(raw_balance: Mapping[str, Any]) -> dict[str, int | float | None]:
    return {
        "cash_balance": parse_number(
            first_non_empty(
                raw_balance.get("cash_balance"),
                raw_balance.get("available_balance"),
                raw_balance.get("available_cash"),
                raw_balance.get("balance"),
            )
        ),
        "withdrawable_balance": parse_number(
            first_non_empty(
                raw_balance.get("withdrawable_balance"),
                raw_balance.get("withdrawable_cash"),
            )
        ),
        "portfolio_value": parse_number(
            first_non_empty(
                raw_balance.get("portfolio_value"),
                raw_balance.get("account_value"),
            )
        ),
    }


def recommendation_placeholder(exposure: int | float | None, unrealized_pnl: int | float | None) -> str:
    if exposure is not None and exposure >= 2000:
        return "Reduce candidate"
    if unrealized_pnl is not None and unrealized_pnl <= -100:
        return "Exit candidate"
    return "Review"


def normalize_position(raw_position: Mapping[str, Any]) -> dict[str, Any]:
    count = parse_number(
        first_non_empty(
            raw_position.get("count"),
            raw_position.get("contracts"),
            raw_position.get("position"),
            raw_position.get("quantity"),
        )
    )
    avg_price = parse_cents(first_non_empty(raw_position.get("avg_price"), raw_position.get("average_price")))
    current_price = parse_cents(
        first_non_empty(
            raw_position.get("current_price"),
            raw_position.get("mark_price"),
            raw_position.get("last_price"),
        )
    )
    market_value = parse_number(
        first_non_empty(
            raw_position.get("market_value"),
            raw_position.get("mark_value"),
            (count * current_price) if count is not None and current_price is not None else None,
        )
    )
    unrealized_pnl = parse_number(
        first_non_empty(
            raw_position.get("unrealized_pnl"),
            raw_position.get("pnl"),
            raw_position.get("profit_loss"),
        )
    )
    exposure = parse_number(
        first_non_empty(
            raw_position.get("exposure"),
            raw_position.get("cost_basis"),
            (count * avg_price) if count is not None and avg_price is not None else None,
        )
    )

    return {
        "ticker": str(first_non_empty(raw_position.get("ticker"), raw_position.get("market_ticker"), "UNKNOWN")),
        "market_title": str(
            first_non_empty(raw_position.get("market_title"), raw_position.get("title"), "Unknown market")
        ),
        "side": str(first_non_empty(raw_position.get("side"), raw_position.get("position_side"), "UNKNOWN")).upper(),
        "count": count,
        "avg_price": avg_price,
        "current_price": current_price,
        "market_value": market_value,
        "unrealized_pnl": unrealized_pnl,
        "exposure": exposure,
        "recommendation": recommendation_placeholder(exposure, unrealized_pnl),
    }


def normalize_snapshot(
    *,
    base_url: str,
    balance_payload: Mapping[str, Any] | None,
    positions_payload: list[Mapping[str, Any]],
    collected_at: datetime,
    warnings: list[str] | None = None,
    available: bool = True,
) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "collected_at": isoformat_utc(collected_at),
        "source": {"base_url": base_url},
        "available": available,
        "positions": [normalize_position(position) for position in positions_payload],
        "warnings": warnings or [],
    }
    if balance_payload is not None:
        snapshot["balance"] = normalize_balance(balance_payload)
    return snapshot


def fallback_snapshot(*, base_url: str, collected_at: datetime, warning: str) -> dict[str, Any]:
    return {
        "collected_at": isoformat_utc(collected_at),
        "source": {"base_url": base_url},
        "available": False,
        "positions": [],
        "warnings": [warning],
    }


def load_fixture_payload(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_fixture_payload(payload: Any, *, base_url: str, collected_at: datetime) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(f"Fixture must be a JSON object: {payload!r}")

    if "available" in payload and "positions" in payload:
        normalized = {
            "collected_at": payload.get("collected_at", isoformat_utc(collected_at)),
            "source": {"base_url": payload.get("source", {}).get("base_url", base_url)},
            "available": bool(payload.get("available")),
            "positions": [normalize_position(position) for position in payload.get("positions", [])],
            "warnings": [str(item) for item in payload.get("warnings", [])],
        }
        if "balance" in payload and isinstance(payload["balance"], dict):
            normalized["balance"] = normalize_balance(payload["balance"])
        return normalized

    balance_payload = payload.get("balance")
    positions_payload = payload.get("positions")
    if not isinstance(balance_payload, dict) or not isinstance(positions_payload, list):
        raise ValueError("Fixture must include balance and positions fields.")

    return normalize_snapshot(
        base_url=base_url,
        balance_payload=balance_payload,
        positions_payload=[position for position in positions_payload if isinstance(position, dict)],
        collected_at=collected_at,
    )


def build_snapshot(
    *,
    base_url: str | None,
    fixture_path: Path | None,
    env: Mapping[str, str] | None = None,
    collected_at: datetime | None = None,
    dotenv_path: Path = DEFAULT_DOTENV_PATH,
) -> dict[str, Any]:
    collected_at = collected_at or datetime.now().astimezone()
    env = env or os.environ
    dotenv_values = load_dotenv_values(dotenv_path)
    resolved_base_url = resolve_base_url(base_url, env, dotenv_values)

    if fixture_path is not None:
        return normalize_fixture_payload(
            load_fixture_payload(fixture_path),
            base_url=resolved_base_url,
            collected_at=collected_at,
        )

    key_id = resolve_setting("KALSHI_API_KEY_ID", env, dotenv_values)
    private_key_path_value = resolve_setting("KALSHI_PRIVATE_KEY_PATH", env, dotenv_values)
    if not key_id or not private_key_path_value:
        return fallback_snapshot(
            base_url=resolved_base_url,
            collected_at=collected_at,
            warning=(
                "Missing Kalshi portfolio credentials. Add KALSHI_API_KEY_ID and "
                "KALSHI_PRIVATE_KEY_PATH locally to enable the live reader."
            ),
        )

    private_key_path = Path(private_key_path_value).expanduser()
    if not private_key_path.exists():
        return fallback_snapshot(
            base_url=resolved_base_url,
            collected_at=collected_at,
            warning=f"Kalshi private key file was not found at {private_key_path}.",
        )

    try:
        balance_response = fetch_json(
            base_url=resolved_base_url,
            endpoint=BALANCE_ENDPOINT,
            key_id=key_id,
            private_key_path=private_key_path,
        )
        positions_response = fetch_json(
            base_url=resolved_base_url,
            endpoint=POSITIONS_ENDPOINT,
            key_id=key_id,
            private_key_path=private_key_path,
        )
    except FileNotFoundError:
        return fallback_snapshot(
            base_url=resolved_base_url,
            collected_at=collected_at,
            warning="OpenSSL is required for Kalshi RSA-PSS signing.",
        )
    except subprocess.CalledProcessError as error:
        return fallback_snapshot(
            base_url=resolved_base_url,
            collected_at=collected_at,
            warning=f"Kalshi signing failed with exit code {error.returncode}.",
        )
    except HTTPError as error:
        return fallback_snapshot(
            base_url=resolved_base_url,
            collected_at=collected_at,
            warning=f"Kalshi portfolio request failed with HTTP {error.code}.",
        )
    except URLError as error:
        return fallback_snapshot(
            base_url=resolved_base_url,
            collected_at=collected_at,
            warning=f"Kalshi portfolio request failed: {error.reason}.",
        )

    return normalize_snapshot(
        base_url=resolved_base_url,
        balance_payload=balance_response.get("balance")
        if isinstance(balance_response.get("balance"), dict)
        else balance_response,
        positions_payload=[
            position
            for position in positions_response.get("positions", [])
            if isinstance(position, dict)
        ],
        collected_at=collected_at,
        warnings=[],
        available=True,
    )


def default_output_path(collected_at: datetime) -> Path:
    return Path("data") / "portfolio" / f"{collected_at.date().isoformat()}.json"


def write_snapshot(snapshot: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(f"{json.dumps(snapshot, indent=2)}\n", encoding="utf-8")
    return output_path


def main() -> int:
    args = parse_args()
    collected_at = datetime.now().astimezone()
    snapshot = build_snapshot(
        base_url=args.base_url,
        fixture_path=args.fixture,
        collected_at=collected_at,
    )
    output_path = write_snapshot(snapshot, args.output or default_output_path(collected_at))
    print(
        json.dumps(
            {
                "output": str(output_path),
                "available": snapshot["available"],
                "positions": len(snapshot["positions"]),
                "warnings": snapshot["warnings"],
                "base_url": snapshot["source"]["base_url"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
