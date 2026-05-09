import unittest
from unittest.mock import patch

import engine
import generator


def make_forecast(
    *,
    race_type="binary_head_to_head",
    p25=0.56,
    p50=0.64,
    p75=0.72,
    confidence="medium",
    data_quality="polling_available",
):
    return {
        "model": "arbiter_forecast_v2",
        "race_type": race_type,
        "calibration_version": "manual-2026-05-09",
        "polling_average": 52.0,
        "polling_lead": 4.0,
        "p05": max(0.0, p25 - 0.12),
        "p25": p25,
        "p50": p50,
        "p75": p75,
        "p95": min(1.0, p75 + 0.12),
        "confidence": confidence,
        "data_quality": data_quality,
        "inputs": {"poll_count": 4.0, "total_weight": 24.0},
    }


class EngineForecastReportingTests(unittest.TestCase):
    def test_finalize_market_attaches_forecast_and_preserves_top_level_fields(self):
        market = {
            "ticker": "KXTEST-ALICE",
            "title": "Will Alice win the election?",
            "market_price": 52,
            "status": "analyzing",
        }
        forecast = make_forecast()
        sources = [{"label": "Polling", "url": "https://example.com/poll"}]

        engine._finalize_market(
            market,
            64,
            "Polling average still favors Alice.",
            "Alice has room above the current price.",
            sources,
            forecast=forecast,
        )

        self.assertEqual(market["marcus_fv"], 64)
        self.assertEqual(market["delta"], 12)
        self.assertEqual(market["verdict"], "TRADE")
        self.assertEqual(market["context"], "Polling average still favors Alice.")
        self.assertEqual(market["sources"], sources)
        self.assertEqual(market["forecast"], forecast)
        self.assertIn("Alice has room above the current price.", market["analysis"])
        self.assertIn("64% median", market["analysis"])
        self.assertIn("56-72%", market["analysis"])
        self.assertIn("medium confidence", market["analysis"].lower())
        self.assertIn("polling available", market["analysis"].lower())

    def test_run_uses_candidate_specific_forecast_note_for_grouped_mayor_race(self):
        karen_forecast = make_forecast(
            race_type="top_two_advance",
            p25=0.54,
            p50=0.61,
            p75=0.67,
            confidence="medium",
            data_quality="polling_available",
        )
        nithya_forecast = make_forecast(
            race_type="top_two_advance",
            p25=0.39,
            p50=0.44,
            p75=0.51,
            confidence="low",
            data_quality="sparse_polling",
        )
        state = {
            "last_run": None,
            "markets": [
                {
                    "ticker": "KXMAYOR-LA-KB",
                    "title": "Will Karen Bass win the LA mayoral election?",
                    "candidate_name": "Karen Bass",
                    "event_ticker": "KXMAYOR-LA-2026",
                    "event_date": "2026-06-02",
                    "series_ticker": "KXMAYORLA",
                    "market_price": 38,
                    "status": "discovered",
                    "sources": [],
                },
                {
                    "ticker": "KXMAYOR-LA-NR",
                    "title": "Will Nithya Raman win the LA mayoral election?",
                    "candidate_name": "Nithya Raman",
                    "event_ticker": "KXMAYOR-LA-2026",
                    "event_date": "2026-06-02",
                    "series_ticker": "KXMAYORLA",
                    "market_price": 29,
                    "status": "discovered",
                    "sources": [],
                },
            ],
        }

        with (
            patch.object(engine, "read_state", return_value=state),
            patch.object(engine, "write_state"),
            patch.object(engine, "_attach_financials"),
            patch.object(
                engine,
                "adapt_race_forecast",
                return_value={
                    "KXMAYOR-LA-KB": {"forecast": karen_forecast},
                    "KXMAYOR-LA-NR": {"forecast": nithya_forecast},
                },
            ),
        ):
            processed = engine.run()

        self.assertEqual(processed, 2)

        karen_market = next(m for m in state["markets"] if m["ticker"] == "KXMAYOR-LA-KB")
        nithya_market = next(m for m in state["markets"] if m["ticker"] == "KXMAYOR-LA-NR")

        self.assertEqual(karen_market["status"], "complete")
        self.assertEqual(nithya_market["status"], "complete")
        self.assertEqual(karen_market["context"], nithya_market["context"])

        self.assertIn("Top-two forecast for Karen Bass: 61% median", karen_market["analysis"])
        self.assertIn("54-67%", karen_market["analysis"])
        self.assertIn("medium confidence", karen_market["analysis"].lower())

        self.assertIn("Top-two forecast for Nithya Raman: 44% median", nithya_market["analysis"])
        self.assertIn("39-51%", nithya_market["analysis"])
        self.assertIn("low confidence", nithya_market["analysis"].lower())
        self.assertIn("sparse polling", nithya_market["analysis"].lower())
        self.assertNotIn("Top-two forecast for Karen Bass", nithya_market["analysis"])


class GeneratorForecastRenderingTests(unittest.TestCase):
    def test_render_card_includes_forecast_range_and_confidence(self):
        html = generator._render_card(
            {
                "ticker": "KXTEST-ALICE",
                "title": "Will Alice win the election?",
                "event_date": "2026-11-03",
                "market_price": 52,
                "marcus_fv": 64,
                "delta": 12,
                "verdict": "TRADE",
                "context": "Context",
                "analysis": "Analysis",
                "sources": [],
                "forecast": make_forecast(),
            }
        )

        self.assertIn("Forecast", html)
        self.assertIn("64% median", html)
        self.assertIn("56-72%", html)
        self.assertIn("Medium confidence", html)
        self.assertIn("Polling available", html)

    def test_render_race_card_handles_grouped_candidate_forecasts(self):
        html = generator._render_race_card(
            "KXTOPTWO-26",
            [
                {
                    "ticker": "ALICE",
                    "title": "Will Alice win?",
                    "candidate_name": "Alice",
                    "event_date": "2026-06-02",
                    "market_price": 38,
                    "marcus_fv": 61,
                    "delta": 23,
                    "verdict": "TRADE",
                    "forecast": make_forecast(
                        race_type="top_two_advance",
                        p25=0.54,
                        p50=0.61,
                        p75=0.67,
                        confidence="medium",
                    ),
                    "context": "Race context",
                    "analysis": "Grouped analysis",
                    "sources": [],
                },
                {
                    "ticker": "BOB",
                    "title": "Will Bob win?",
                    "candidate_name": "Bob",
                    "event_date": "2026-06-02",
                    "market_price": 29,
                    "marcus_fv": 44,
                    "delta": 15,
                    "verdict": "TRADE",
                    "forecast": make_forecast(
                        race_type="top_two_advance",
                        p25=0.39,
                        p50=0.44,
                        p75=0.51,
                        confidence="low",
                        data_quality="sparse_polling",
                    ),
                },
            ],
        )

        self.assertIn(">Forecast<", html)
        self.assertIn("61% median", html)
        self.assertIn("54-67%", html)
        self.assertIn("Medium", html)
        self.assertIn("44% median", html)
        self.assertIn("Sparse polling", html)


if __name__ == "__main__":
    unittest.main()
