"""Forecast model foundation for Arbiter."""

from forecast.adapters import (
    adapt_binary_head_to_head,
    adapt_congressional,
    adapt_multicandidate_plurality,
    adapt_presidential_state,
    adapt_race_forecast,
    adapt_top_two_advance,
    build_verdict,
)
from forecast.calibration import CalibrationBundle, load_calibration_bundle
from forecast.classify import classify_race
from forecast.electoral import compute_electoral_college_outlook
from forecast.polling import compute_polling_average
from forecast.types import (
    Candidate,
    Forecast,
    OutcomeFundamentals,
    Poll,
    PollResult,
    PollingAverage,
    Race,
    RaceFundamentals,
    RaceType,
)

__all__ = [
    "CalibrationBundle",
    "Candidate",
    "Forecast",
    "OutcomeFundamentals",
    "Poll",
    "PollResult",
    "PollingAverage",
    "Race",
    "RaceFundamentals",
    "RaceType",
    "adapt_binary_head_to_head",
    "adapt_congressional",
    "adapt_multicandidate_plurality",
    "adapt_presidential_state",
    "adapt_race_forecast",
    "adapt_top_two_advance",
    "build_verdict",
    "classify_race",
    "compute_electoral_college_outlook",
    "compute_polling_average",
    "load_calibration_bundle",
]
