import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import collector
import generator
import state


class DiscoverSeriesTests(unittest.TestCase):
    def test_discover_series_uses_elections_events_pagination(self):
        responses = [
            {
                "events": [
                    {"series_ticker": "KXLAMAYOR1R"},
                    {"series_ticker": "KXLAMAYORMATCHUP"},
                    {"series_ticker": "KXLAMAYOR1R"},
                ],
                "cursor": "page-2",
            },
            {
                "events": [
                    {"series_ticker": "KXNYCMAYOR"},
                ]
            },
        ]
        calls = []

        def fake_api_get(path, params=None, retries=2):
            calls.append((path, dict(params or {})))
            if not responses:
                return {"events": []}
            return responses.pop(0)

        with patch.object(collector, "_api_get", side_effect=fake_api_get):
            series = collector.discover_series()

        self.assertEqual(
            calls,
            [
                ("/events", {"category": "Elections", "limit": "500"}),
                ("/events", {"category": "Elections", "limit": "500", "cursor": "page-2"}),
            ],
        )
        self.assertEqual(set(series), {"KXLAMAYOR1R", "KXLAMAYORMATCHUP", "KXNYCMAYOR"})


class ParseCloseDateTests(unittest.TestCase):
    def test_parse_close_date_prefers_expected_expiration_time(self):
        """expected_expiration_time is the actual election/event date — it takes priority."""
        market = {
            "close_time": "2027-06-02T00:00:00Z",
            "expiration_time": "2027-06-01T00:00:00Z",
            "expected_expiration_time": "2026-06-02T00:00:00Z",
        }

        close = collector._parse_close_date(market)

        self.assertEqual(close.isoformat(), "2026-06-02T00:00:00+00:00")

    def test_parse_close_date_falls_back_to_close_time(self):
        """close_time is used when expected_expiration_time is absent."""
        market = {
            "close_time": "2027-05-02T00:00:00Z",
            "expiration_time": "2026-05-02T00:00:00Z",
        }

        close = collector._parse_close_date(market)

        self.assertEqual(close.isoformat(), "2027-05-02T00:00:00+00:00")


class CollectTests(unittest.TestCase):
    def test_collect_stores_event_date_only_and_skips_excluded_titles(self):
        now = datetime.now(timezone.utc)
        # close_time is near-term (within 60-day window) — used for filtering
        close_time = (now + timedelta(days=10)).replace(microsecond=0)
        # expected_expiration_time is the election date (may be outside 60-day window)
        # but _parse_close_date now prefers expected_expiration_time, so set it
        # to something within 60 days so the market is actually collected
        election_time = (now + timedelta(days=30)).replace(microsecond=0)

        markets = [
            {
                "ticker": "KXLAMAYORMATCHUP-YES",
                "title": "Who will win the Los Angeles mayoral election?",
                "yes_sub_title": "Candidate A",
                "event_ticker": "KXLAMAYORMATCHUP-27",
                "close_time": close_time.isoformat().replace("+00:00", "Z"),
                "expected_expiration_time": election_time.isoformat().replace("+00:00", "Z"),
                "yes_bid": 44,
            },
            {
                "ticker": "KXAPPROVAL-YES",
                "title": "Will the president approval rating rise this week?",
                "yes_sub_title": "Approval",
                "event_ticker": "KXAPPROVAL-26",
                "close_time": close_time.isoformat().replace("+00:00", "Z"),
                "expected_expiration_time": election_time.isoformat().replace("+00:00", "Z"),
                "yes_bid": 51,
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            original_state_file = state.STATE_FILE
            state.STATE_FILE = Path(tmpdir) / "analysis.json"
            try:
                with patch.object(collector, "discover_series", return_value=["KXLAMAYORMATCHUP"]):
                    with patch.object(collector, "fetch_markets_for_series", return_value=markets):
                        added = collector.collect()
                saved = state.read_state()
            finally:
                state.STATE_FILE = original_state_file

        self.assertEqual(added, 1)
        self.assertEqual(len(saved["markets"]), 1)
        market = saved["markets"][0]
        self.assertEqual(market["ticker"], "KXLAMAYORMATCHUP-YES")
        self.assertEqual(market["event_date"], election_time.strftime("%Y-%m-%d"))
        self.assertNotIn("close_date", market)


class StateTests(unittest.TestCase):
    def test_upsert_market_persists_event_date_only(self):
        current_state = {"last_run": None, "markets": []}

        entry = state.upsert_market(
            current_state,
            {
                "ticker": "KXLAMAYORMATCHUP-YES",
                "title": "Will Candidate A win?",
                "event_date": "2027-06-02",
                "market_price": 42,
            },
        )

        self.assertEqual(entry["event_date"], "2027-06-02")
        self.assertNotIn("close_date", entry)


class GeneratorDateTests(unittest.TestCase):
    def test_render_card_prefers_event_date_for_display(self):
        html = generator._render_card(
            {
                "ticker": "KXLAMAYORMATCHUP-YES",
                "title": "Will Candidate A win?",
                "event_date": "2027-06-02",
                "market_price": 42,
                "delta": 8,
                "marcus_fv": 50,
                "analysis": "Analysis",
                "context": "Context",
                "sources": [],
            }
        )

        self.assertIn("June 2, 2027", html)
        self.assertNotIn("May 18, 2026", html)

    def test_render_race_card_prefers_event_date_for_display(self):
        html = generator._render_race_card(
            "KXLAMAYORMATCHUP-27",
            [
                {
                    "ticker": "KXLAMAYORMATCHUP-YES",
                    "title": "Will Candidate A win?",
                    "candidate_name": "Candidate A",
                    "event_date": "2027-06-02",
                    "market_price": 42,
                    "delta": 8,
                    "marcus_fv": 50,
                    "verdict": "TRADE",
                }
            ],
        )

        self.assertIn("June 2, 2027", html)
        self.assertNotIn("May 18, 2026", html)


if __name__ == "__main__":
    unittest.main()
