import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "collect_kalshi_public_snapshot.py"


def load_module():
    spec = importlib.util.spec_from_file_location("collect_kalshi_public_snapshot", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {SCRIPT_PATH}.")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class KalshiPublicSnapshotTests(unittest.TestCase):
    def test_parse_price_to_cents_converts_dollar_strings(self):
        module = load_module()

        self.assertEqual(module.parse_price_to_cents("0.4200"), 42)
        self.assertEqual(module.parse_price_to_cents("1.0000"), 100)
        self.assertEqual(module.parse_price_to_cents("0.0050"), 1)
        self.assertIsNone(module.parse_price_to_cents(None))

    def test_market_within_window_uses_expiration_or_close_time(self):
        module = load_module()

        self.assertTrue(
            module.market_closes_within_window(
                {
                    "ticker": "SOON",
                    "close_time": "2026-05-20T12:00:00Z",
                },
                collected_at=module.parse_datetime("2026-05-06T12:00:00Z"),
                window_days=30,
            )
        )
        self.assertFalse(
            module.market_closes_within_window(
                {
                    "ticker": "LATE",
                    "expiration_time": "2026-07-20T12:00:00Z",
                },
                collected_at=module.parse_datetime("2026-05-06T12:00:00Z"),
                window_days=30,
            )
        )

    def test_normalize_market_shapes_expected_fields(self):
        module = load_module()

        normalized = module.normalize_market(
            {
                "ticker": "PRES-DEM-2028",
                "title": "Will the Democratic nominee win the 2028 presidential election?",
                "event_ticker": "PRES-2028",
                "series_ticker": "PRES",
                "category": "Politics",
                "close_time": "2026-05-20T12:00:00Z",
                "yes_bid": "0.4100",
                "yes_ask": "0.4300",
                "no_bid": "0.5700",
                "no_ask": "0.5900",
                "volume": 12345,
                "open_interest": 6789,
                "liquidity": 1500,
                "rules_primary": "Resolved to YES if the Democratic nominee wins the general election.",
            }
        )

        self.assertEqual(
            normalized,
            {
                "ticker": "PRES-DEM-2028",
                "title": "Will the Democratic nominee win the 2028 presidential election?",
                "event_ticker": "PRES-2028",
                "series_ticker": "PRES",
                "category": "Politics",
                "close_time": "2026-05-20T12:00:00Z",
                "expiration_time": "2026-05-20T12:00:00Z",
                "yes_bid_cents": 41,
                "yes_ask_cents": 43,
                "no_bid_cents": 57,
                "no_ask_cents": 59,
                "yes_midpoint_cents": 42,
                "no_midpoint_cents": 58,
                "volume": 12345,
                "open_interest": 6789,
                "liquidity": 1500,
                "rules_text": "Resolved to YES if the Democratic nominee wins the general election.",
            },
        )


if __name__ == "__main__":
    unittest.main()
