import unittest

from forecast.polling import compute_polling_average
from forecast.types import Poll, PollResult


def make_poll(
    pollster,
    candidate_a_support,
    candidate_b_support,
    *,
    end_date="2026-05-01",
    sample_size=100,
    population="lv",
    pollster_rating=1.0,
    sponsor=None,
    is_internal=False,
):
    return Poll(
        pollster=pollster,
        results=[
            PollResult(candidate_name="Candidate A", support_pct=candidate_a_support),
            PollResult(candidate_name="Candidate B", support_pct=candidate_b_support),
        ],
        end_date=end_date,
        sample_size=sample_size,
        population=population,
        pollster_rating=pollster_rating,
        sponsor=sponsor,
        is_internal=is_internal,
    )


class PollingAverageTests(unittest.TestCase):
    def test_compute_polling_average_weights_sample_size_and_population(self):
        average = compute_polling_average(
            [
                make_poll(
                    "Likely Voter Poll",
                    52.0,
                    48.0,
                    sample_size=400,
                    population="likely voters",
                ),
                make_poll(
                    "Adult Poll",
                    48.0,
                    52.0,
                    sample_size=100,
                    population="adults",
                ),
            ],
            as_of_date="2026-05-01",
        )

        self.assertAlmostEqual(
            average.support_by_candidate["Candidate A"],
            50.80701754385965,
        )
        self.assertAlmostEqual(average.lead_margin, 1.6140350877193018)
        self.assertEqual(average.poll_count, 2)
        self.assertEqual(average.data_quality, "polling_available")

    def test_compute_polling_average_applies_mild_pollster_quality_discount(self):
        average = compute_polling_average(
            [
                make_poll("Stronger Pollster", 52.0, 48.0, pollster_rating=1.0),
                make_poll("Weaker Pollster", 48.0, 52.0, pollster_rating=0.0),
            ],
            as_of_date="2026-05-01",
        )

        self.assertAlmostEqual(
            average.support_by_candidate["Candidate A"],
            50.22222222222222,
        )
        self.assertGreater(average.total_weight, 10.0)
        self.assertLess(average.support_by_candidate["Candidate A"], 52.0)

    def test_compute_polling_average_applies_internal_poll_discount_without_excluding_poll(self):
        average = compute_polling_average(
            [
                make_poll("Public Pollster", 52.0, 48.0),
                make_poll(
                    "Campaign Internal",
                    56.0,
                    44.0,
                    sponsor="Candidate A Committee",
                    is_internal=True,
                ),
            ],
            as_of_date="2026-05-01",
        )

        self.assertAlmostEqual(
            average.support_by_candidate["Candidate A"],
            53.89473684210526,
        )
        self.assertAlmostEqual(average.total_weight, 19.0)

    def test_compute_polling_average_decays_stale_polls(self):
        average = compute_polling_average(
            [
                make_poll("Recent Poll", 52.0, 48.0, end_date="2026-05-01"),
                make_poll("Old Poll", 48.0, 52.0, end_date="2026-04-03"),
            ],
            as_of_date="2026-05-01",
        )

        self.assertAlmostEqual(average.support_by_candidate["Candidate A"], 51.2)
        self.assertAlmostEqual(average.total_weight, 12.5)

    def test_compute_polling_average_handles_empty_polls(self):
        average = compute_polling_average([], as_of_date="2026-05-01")

        self.assertEqual(average.support_by_candidate, {})
        self.assertEqual(average.poll_count, 0)
        self.assertEqual(average.total_weight, 0.0)
        self.assertEqual(average.data_quality, "no_polls")
        self.assertIsNone(average.leading_candidate)
        self.assertIsNone(average.lead_margin)


if __name__ == "__main__":
    unittest.main()
