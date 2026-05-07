import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "collect_kalshi_portfolio.py"
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "kalshi_portfolio_fixture.json"


def load_module():
    spec = importlib.util.spec_from_file_location("collect_kalshi_portfolio", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {SCRIPT_PATH}.")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class KalshiPortfolioCollectorTests(unittest.TestCase):
    def test_signature_message_uses_trade_api_prefix_without_query(self):
        module = load_module()

        message = module.signature_message(
            "1715000000123",
            "GET",
            "https://api.elections.kalshi.com/trade-api/v2/portfolio/positions?limit=200",
        )

        self.assertEqual(
            message,
            b"1715000000123GET/trade-api/v2/portfolio/positions",
        )

    def test_missing_credentials_returns_clean_fallback(self):
        module = load_module()

        snapshot = module.build_snapshot(
            base_url=module.DEFAULT_BASE_URL,
            fixture_path=None,
            env={},
            collected_at=module.parse_datetime("2026-05-06T12:00:00Z"),
        )

        self.assertFalse(snapshot["available"])
        self.assertEqual(snapshot["positions"], [])
        self.assertIn("Missing Kalshi portfolio credentials", snapshot["warnings"][0])

    def test_fixture_normalization_produces_stable_shape(self):
        module = load_module()

        snapshot = module.build_snapshot(
            base_url=module.DEFAULT_BASE_URL,
            fixture_path=FIXTURE_PATH,
            env={},
            collected_at=module.parse_datetime("2026-05-06T12:00:00Z"),
        )

        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["source"]["base_url"], module.DEFAULT_BASE_URL)
        self.assertEqual(
            snapshot["balance"],
            {
                "cash_balance": 5300,
                "withdrawable_balance": 5000,
                "portfolio_value": 10120,
            },
        )
        self.assertEqual(
            snapshot["positions"],
            [
                {
                    "ticker": "OIL-ABOVE-85",
                    "market_title": "WTI settles above $85 this month",
                    "side": "YES",
                    "count": 60,
                    "avg_price": 52,
                    "current_price": 49,
                    "market_value": 2940,
                    "unrealized_pnl": -180,
                    "exposure": 3100,
                    "recommendation": "Reduce candidate",
                },
                {
                    "ticker": "F1-VER-WIN",
                    "market_title": "Verstappen wins next race",
                    "side": "YES",
                    "count": 25,
                    "avg_price": 63,
                    "current_price": 57,
                    "market_value": 1425,
                    "unrealized_pnl": -150,
                    "exposure": 1800,
                    "recommendation": "Exit candidate",
                },
            ],
        )
        self.assertEqual(snapshot["warnings"], [])

    def test_no_order_endpoints_are_referenced(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn('BALANCE_ENDPOINT = "/portfolio/balance"', source)
        self.assertIn('POSITIONS_ENDPOINT = "/portfolio/positions"', source)
        self.assertNotIn("/orders", source)
        self.assertNotIn("POST", source)
        self.assertNotIn("DELETE", source)


if __name__ == "__main__":
    unittest.main()
