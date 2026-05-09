import unittest

from forecast.adapters import adapt_race_forecast
from forecast.electoral import compute_electoral_college_outlook
from forecast.polling import compute_polling_average
from forecast.types import (
    Candidate,
    OutcomeFundamentals,
    PollingAverage,
    Race,
    RaceFundamentals,
)


def make_race(title, candidates, **kwargs):
    return Race(title=title, candidates=candidates, **kwargs)


def make_candidates(*entries):
    return [
        Candidate(name=name, contract_ticker=ticker, market_price=market_price)
        for name, ticker, market_price in entries
    ]


def make_polling_average(
    support_by_candidate,
    *,
    poll_count=4,
    data_quality="polling_available",
    total_weight=24.0,
):
    ranked = sorted(support_by_candidate.items(), key=lambda item: (-item[1], item[0]))
    leading_candidate = None
    leading_support = None
    runner_up_candidate = None
    runner_up_support = None
    lead_margin = None
    if ranked:
        leading_candidate, leading_support = ranked[0]
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
        total_weight=total_weight,
    )


class ForecastPhase4Tests(unittest.TestCase):
    def test_presidential_state_adapter_uses_presidential_race_type_and_accepts_state_lean(self):
        race = make_race(
            "Pennsylvania presidential race",
            make_candidates(("Alice", "ALICE", 49), ("Bob", "BOB", 51)),
            office="President",
            geography="PA",
        )
        sparse_polling = make_polling_average(
            {"Alice": 49.5, "Bob": 50.5},
            poll_count=1,
            data_quality="sparse_polling",
            total_weight=7.5,
        )

        neutral = adapt_race_forecast(race, sparse_polling)
        leaned = adapt_race_forecast(
            race,
            sparse_polling,
            fundamentals=RaceFundamentals(
                favored_candidate="Alice",
                baseline_margin=4.0,
            ),
        )

        self.assertEqual(leaned["ALICE"]["forecast"]["race_type"], "presidential_state")
        self.assertGreater(leaned["ALICE"]["forecast"]["p50"], neutral["ALICE"]["forecast"]["p50"])

    def test_congressional_no_poll_fallback_returns_forecast(self):
        race = make_race(
            "Arizona 6th congressional district election",
            make_candidates(("Alice", "ALICE", 47), ("Bob", "BOB", 53)),
            office="U.S. House",
            geography="AZ-06",
        )

        forecast = adapt_race_forecast(
            race,
            compute_polling_average([], as_of_date="2026-05-09"),
            fundamentals=RaceFundamentals(
                favored_candidate="Alice",
                baseline_margin=2.5,
                outcome_fundamentals={
                    "Alice": OutcomeFundamentals(
                        receipts=2_800_000.0,
                        disbursements=1_400_000.0,
                        cash_on_hand=1_100_000.0,
                        outside_spend=500_000.0,
                    ),
                    "Bob": OutcomeFundamentals(
                        receipts=1_900_000.0,
                        disbursements=1_700_000.0,
                        cash_on_hand=650_000.0,
                        outside_spend=250_000.0,
                    ),
                },
            ),
        )

        self.assertIn("ALICE", forecast)
        self.assertEqual(forecast["ALICE"]["forecast"]["race_type"], "congressional")
        self.assertGreater(forecast["ALICE"]["forecast"]["p50"], 0.5)

    def test_openfec_financials_move_congressional_probability_directionally(self):
        race = make_race(
            "Nevada Senate election",
            make_candidates(("Alice", "ALICE", 50), ("Bob", "BOB", 50)),
            office="U.S. Senate",
            geography="NV",
        )
        sparse_polling = make_polling_average(
            {"Alice": 50.0, "Bob": 50.0},
            poll_count=1,
            data_quality="sparse_polling",
            total_weight=6.0,
        )

        neutral = adapt_race_forecast(
            race,
            sparse_polling,
            fundamentals=RaceFundamentals(),
        )
        pro_alice = adapt_race_forecast(
            race,
            sparse_polling,
            fundamentals=RaceFundamentals(
                outcome_fundamentals={
                    "Alice": OutcomeFundamentals(
                        receipts=3_400_000.0,
                        disbursements=1_500_000.0,
                        cash_on_hand=1_600_000.0,
                        outside_spend=800_000.0,
                    ),
                    "Bob": OutcomeFundamentals(
                        receipts=1_200_000.0,
                        disbursements=1_600_000.0,
                        cash_on_hand=400_000.0,
                        outside_spend=150_000.0,
                    ),
                }
            ),
        )

        self.assertGreater(
            pro_alice["ALICE"]["forecast"]["p50"],
            neutral["ALICE"]["forecast"]["p50"],
        )
        self.assertLess(
            pro_alice["BOB"]["forecast"]["p50"],
            neutral["BOB"]["forecast"]["p50"],
        )

    def test_fundamentals_dominant_forecast_marks_low_confidence(self):
        race = make_race(
            "Michigan Senate election",
            make_candidates(("Alice", "ALICE", 48), ("Bob", "BOB", 52)),
            office="U.S. Senate",
            geography="MI",
        )
        sparse_polling = make_polling_average(
            {"Alice": 50.5, "Bob": 49.5},
            poll_count=1,
            data_quality="sparse_polling",
            total_weight=5.0,
        )

        outcome = adapt_race_forecast(
            race,
            sparse_polling,
            fundamentals=RaceFundamentals(
                favored_candidate="Alice",
                baseline_margin=5.0,
                outcome_fundamentals={
                    "Alice": OutcomeFundamentals(
                        receipts=3_100_000.0,
                        disbursements=1_400_000.0,
                        cash_on_hand=1_500_000.0,
                        outside_spend=750_000.0,
                    ),
                    "Bob": OutcomeFundamentals(
                        receipts=1_600_000.0,
                        disbursements=1_500_000.0,
                        cash_on_hand=500_000.0,
                        outside_spend=200_000.0,
                    ),
                },
            ),
        )["ALICE"]["forecast"]

        self.assertEqual(outcome["confidence"], "low")
        self.assertEqual(outcome["data_quality"], "fundamentals_dominant")

    def test_electoral_college_helper_returns_deterministic_summary_for_simple_map(self):
        map_summary = compute_electoral_college_outlook(
            {
                "PA": {"electoral_votes": 19, "win_probability": 0.60},
                "MI": {"electoral_votes": 15, "win_probability": 0.55},
                "WI": {"electoral_votes": 10, "win_probability": 0.50},
            },
            target_electoral_votes=29,
        )

        self.assertEqual(map_summary["method"], "exact")
        self.assertEqual(map_summary["state_count"], 3)
        self.assertAlmostEqual(map_summary["win_probability"], 0.465)
        self.assertAlmostEqual(map_summary["expected_electoral_votes"], 24.65)
        self.assertEqual(
            map_summary,
            compute_electoral_college_outlook(
                {
                    "PA": {"electoral_votes": 19, "win_probability": 0.60},
                    "MI": {"electoral_votes": 15, "win_probability": 0.55},
                    "WI": {"electoral_votes": 10, "win_probability": 0.50},
                },
                target_electoral_votes=29,
            ),
        )


if __name__ == "__main__":
    unittest.main()
