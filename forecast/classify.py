"""Race classification helpers for the forecast model."""

from __future__ import annotations

from forecast.types import Race, RaceType


def _race_text(race: Race) -> str:
    parts = [
        race.title,
        race.office,
        race.geography,
        race.event_ticker,
        race.series_ticker,
        race.format_hint,
    ]
    return " ".join(part for part in parts if part).lower()


def classify_race(race: Race) -> RaceType:
    """Classify a race for downstream forecast adapters."""

    text = _race_text(race)
    candidate_count = len(race.candidates)

    if "president" in text and race.geography:
        return "presidential_state"

    congressional_tokens = (
        "u.s. senate",
        "senate",
        "u.s. house",
        "house district",
        "house election",
        "congress",
        "congressional",
    )
    if any(token in text for token in congressional_tokens):
        return "congressional"

    top_two_tokens = (
        "top two",
        "top-two",
        "jungle primary",
        "advance to general",
    )
    if any(token in text for token in top_two_tokens):
        return "top_two_advance"

    if candidate_count == 2:
        return "binary_head_to_head"

    if candidate_count > 2:
        return "multicandidate_plurality"

    return "unknown"
