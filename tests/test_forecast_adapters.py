import unittest

from forecast.adapters import adapt_race_forecast, build_verdict
from forecast.types import Candidate, PollingAverage, Race


def make_race(title, candidates, **kwargs):
    return Race(title=title, candidates=candidates, **kwargs)


def make_candidates(*entries):
    return [
        Candidate(name=name, contract_ticker=ticker, market_price=market_price)
        for name, ticker, market_price in entries
    ]


def make_polling_average(support_by_candidate, *, poll_count=4, data_quality="polling_available"):
    ranked = sorted(support_by_candidate.items(), key=lambda item: (-item[1], item[0]))
    leading_candidate, leading_support = ranked[0]
    runner_up_candidate = None
    runner_up_support = None
    lead_margin = None
    if len(ranked) > 1:
        runner_up_candidate, runner_up_support = ranked[1]
        lead_margin = leading_support - runner_up_support

    return PollingAverage(
        support_by_candidate=dict(support_by_candidate),
        leading_candidate=leading_candidate,
        leading_support=leading_support,
        runner_up_candidate=runner_up_candidate,
        runner_up_support=runner_up_support,
        lead_margin=lead_margin,
        poll_count=poll_count,
        as_of_date="2026-05-09",
        data_quality=data_quality,
        total_weight=24.0,
    )


class ForecastAdapterTests(unittest.TestCase):
    def test_binary_head_to_head_leader_probability_increases_with_lead(self):
        race = make_race(
            "Phoenix mayor general election",
            make_candidates(("Alice", "ALICE", 53), ("Bob", "BOB", 47)),
        )

        narrow = adapt_race_forecast(
            race,
            make_polling_average({"Alice": 50.5, "Bob": 49.5}),
        )
        wide = adapt_race_forecast(
            race,
            make_polling_average({"Alice": 54.5, "Bob": 45.5}),
        )

        self.assertGreater(
            wide["ALICE"]["forecast"]["p50"],
            narrow["ALICE"]["forecast"]["p50"],
        )

    def test_binary_head_to_head_intervals_are_ordered(self):
        race = make_race(
            "Phoenix mayor general election",
            make_candidates(("Alice", "ALICE", 53), ("Bob", "BOB", 47)),
        )

        forecast = adapt_race_forecast(
            race,
            make_polling_average({"Alice": 53.0, "Bob": 47.0}),
        )["ALICE"]["forecast"]

        interval = [forecast[key] for key in ("p05", "p25", "p50", "p75", "p95")]
        self.assertEqual(interval, sorted(interval))

    def test_plurality_adapter_probabilities_sum_close_to_one(self):
        race = make_race(
            "Los Angeles mayor primary",
            make_candidates(
                ("Alice", "ALICE", 36),
                ("Bob", "BOB", 32),
                ("Carla", "CARLA", 18),
                ("Diego", "DIEGO", 14),
            ),
        )

        forecasts = adapt_race_forecast(
            race,
            make_polling_average({"Alice": 37.0, "Bob": 31.0, "Carla": 18.0, "Diego": 14.0}),
        )

        total_probability = sum(item["forecast"]["p50"] for item in forecasts.values())
        self.assertAlmostEqual(total_probability, 1.0, delta=0.03)

    def test_top_two_probabilities_can_exceed_plurality_probabilities(self):
        candidates = make_candidates(
            ("Alice", "ALICE", 34),
            ("Bob", "BOB", 30),
            ("Carla", "CARLA", 22),
            ("Diego", "DIEGO", 14),
        )
        support = {"Alice": 34.0, "Bob": 30.0, "Carla": 22.0, "Diego": 14.0}

        plurality = adapt_race_forecast(
            make_race("Seattle mayor primary", candidates),
            make_polling_average(support),
        )
        top_two = adapt_race_forecast(
            make_race(
                "Seattle mayor jungle primary",
                candidates,
                format_hint="top-two",
            ),
            make_polling_average(support),
        )

        self.assertGreater(
            top_two["ALICE"]["forecast"]["p50"],
            plurality["ALICE"]["forecast"]["p50"],
        )
        self.assertGreaterEqual(top_two["ALICE"]["forecast"]["p50"], 0.5)
        self.assertLessEqual(top_two["ALICE"]["forecast"]["p50"], 1.0)

    def test_verdict_passes_when_market_price_sits_inside_uncertainty_band(self):
        verdict = build_verdict(
            market_price=60,
            p25=0.58,
            p50=0.67,
            p75=0.76,
        )

        self.assertEqual(verdict["verdict"], "PASS")
        self.assertEqual(verdict["edge"], 7)
        self.assertFalse(verdict["uncertainty_supports_trade"])

    def test_adapter_output_includes_state_compatibility_fields(self):
        race = make_race(
            "Phoenix mayor general election",
            make_candidates(("Alice", "ALICE", 46), ("Bob", "BOB", 54)),
        )

        outcome = adapt_race_forecast(
            race,
            make_polling_average({"Alice": 52.0, "Bob": 48.0}),
        )["ALICE"]

        self.assertEqual(outcome["contract_ticker"], "ALICE")
        self.assertEqual(outcome["candidate_name"], "Alice")
        self.assertIn("forecast", outcome)
        self.assertIn("marcus_fv", outcome)
        self.assertIn("delta", outcome)
        self.assertIn("verdict", outcome)
        self.assertIn("verdict_details", outcome)


if __name__ == "__main__":
    unittest.main()
