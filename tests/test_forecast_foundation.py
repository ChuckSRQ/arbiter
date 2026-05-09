import json
import tempfile
import unittest
from pathlib import Path

from forecast.calibration import load_calibration_bundle
from forecast.classify import classify_race
from forecast.types import Candidate, Race


def make_candidates(count):
    return [
        Candidate(name=f"Candidate {index}", contract_ticker=f"TICKER-{index}")
        for index in range(1, count + 1)
    ]


class CalibrationLoadingTests(unittest.TestCase):
    def test_load_calibration_bundle_reads_manual_version_and_sections(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            calibration_dir = Path(tmpdir)
            (calibration_dir / "base.json").write_text(
                json.dumps(
                    {
                        "calibration_version": "manual-2026-05-09",
                        "model_name": "arbiter_forecast_v2",
                    }
                ),
                encoding="utf-8",
            )
            (calibration_dir / "polling.json").write_text(
                json.dumps({"sample_size_exponent": 0.5, "recency_half_life_days": 14}),
                encoding="utf-8",
            )
            (calibration_dir / "race_models.json").write_text(
                json.dumps({"binary_head_to_head": {"lead_scale": 3.25}}),
                encoding="utf-8",
            )

            calibration = load_calibration_bundle(calibration_dir)

        self.assertEqual(calibration.version, "manual-2026-05-09")
        self.assertEqual(calibration.model_name, "arbiter_forecast_v2")
        self.assertEqual(calibration.polling_weights["sample_size_exponent"], 0.5)
        self.assertEqual(
            calibration.race_models["binary_head_to_head"]["lead_scale"],
            3.25,
        )

    def test_load_calibration_bundle_rejects_non_manual_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            calibration_dir = Path(tmpdir)
            (calibration_dir / "base.json").write_text(
                json.dumps({"calibration_version": "auto-2026-05-09"}),
                encoding="utf-8",
            )
            (calibration_dir / "polling.json").write_text("{}", encoding="utf-8")
            (calibration_dir / "race_models.json").write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "manual-"):
                load_calibration_bundle(calibration_dir)


class RaceClassificationTests(unittest.TestCase):
    def test_classify_race_detects_binary_head_to_head(self):
        race = Race(title="Phoenix mayor general election", candidates=make_candidates(2))

        self.assertEqual(classify_race(race), "binary_head_to_head")

    def test_classify_race_detects_multicandidate_plurality(self):
        race = Race(title="Los Angeles mayoral primary", candidates=make_candidates(5))

        self.assertEqual(classify_race(race), "multicandidate_plurality")

    def test_classify_race_detects_top_two_advance(self):
        race = Race(
            title="California jungle primary",
            format_hint="top-two",
            candidates=make_candidates(4),
        )

        self.assertEqual(classify_race(race), "top_two_advance")

    def test_classify_race_detects_congressional(self):
        race = Race(
            title="Arizona Senate election",
            office="U.S. Senate",
            candidates=make_candidates(2),
        )

        self.assertEqual(classify_race(race), "congressional")

    def test_classify_race_detects_presidential_state(self):
        race = Race(
            title="Pennsylvania presidential race",
            office="President",
            geography="PA",
            candidates=make_candidates(2),
        )

        self.assertEqual(classify_race(race), "presidential_state")

    def test_classify_race_falls_back_to_unknown(self):
        race = Race(title="Unclear political market", candidates=[])

        self.assertEqual(classify_race(race), "unknown")


if __name__ == "__main__":
    unittest.main()
