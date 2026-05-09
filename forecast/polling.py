"""Weighted polling averages for the fast forecast engine."""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Dict, Iterable, Optional

from forecast.calibration import CalibrationBundle, load_calibration_bundle
from forecast.types import Poll, PollingAverage


def _parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None

    normalized = value.replace("Z", "+00:00")
    try:
        if "T" in normalized:
            return datetime.fromisoformat(normalized).date()
        return date.fromisoformat(normalized)
    except ValueError:
        return None


def _resolve_as_of_date(as_of_date: Optional[str]) -> date:
    if as_of_date:
        parsed = _parse_iso_date(as_of_date)
        if parsed is None:
            raise ValueError(f"Invalid as_of_date: {as_of_date}")
        return parsed
    return datetime.utcnow().date()


def _population_weight(poll: Poll, weights: Dict[str, float]) -> float:
    population = (poll.population or "").strip().lower()

    if population in {"lv", "likely voter", "likely voters"} or population.startswith("likely"):
        return weights.get("likely_voter_weight", 1.0)
    if population in {"rv", "registered voter", "registered voters"} or population.startswith(
        "registered"
    ):
        return weights.get("registered_voter_weight", 0.92)
    if population in {"a", "adult", "adults"} or population.startswith("adult"):
        return weights.get("adult_weight", 0.85)
    return 1.0


def _normalize_pollster_rating(raw_rating: Optional[float]) -> float:
    if raw_rating is None:
        return 1.0
    if raw_rating <= 1.0:
        return max(0.0, raw_rating)
    if raw_rating <= 5.0:
        return raw_rating / 5.0
    if raw_rating <= 100.0:
        return raw_rating / 100.0
    return 1.0


def _quality_weight(poll: Poll, weights: Dict[str, float]) -> float:
    floor = weights.get("pollster_quality_floor", 0.8)
    normalized_rating = _normalize_pollster_rating(poll.pollster_rating)
    return floor + ((1.0 - floor) * normalized_rating)


def _has_sponsor_discount(poll: Poll) -> bool:
    sponsor = (poll.sponsor or "").strip().lower()
    pollster = poll.pollster.strip().lower()
    return poll.is_internal or (bool(sponsor) and sponsor != pollster)


def _recency_weight(poll: Poll, as_of: date, weights: Dict[str, float]) -> float:
    half_life_days = weights.get("recency_half_life_days", 14.0)
    if half_life_days <= 0:
        return 1.0

    poll_date = _parse_iso_date(poll.end_date) or _parse_iso_date(poll.start_date)
    if poll_date is None:
        return 1.0

    age_days = max((as_of - poll_date).days, 0)
    return math.pow(0.5, age_days / half_life_days)


def poll_weight(
    poll: Poll,
    *,
    as_of_date: Optional[str] = None,
    calibration: Optional[CalibrationBundle] = None,
) -> float:
    """Return the configured weight for one normalized poll."""

    bundle = calibration or load_calibration_bundle()
    weights = bundle.polling_weights
    as_of = _resolve_as_of_date(as_of_date)

    sample_size = max(poll.sample_size or 1, 1)
    sample_exponent = weights.get("sample_size_exponent", 0.5)
    base_weight = math.pow(sample_size, sample_exponent)
    base_weight *= _population_weight(poll, weights)
    base_weight *= _quality_weight(poll, weights)
    base_weight *= _recency_weight(poll, as_of, weights)

    if _has_sponsor_discount(poll):
        base_weight *= weights.get("internal_poll_discount", 0.9)

    return base_weight


def _data_quality(
    polls: Iterable[Poll],
    *,
    total_weight: float,
    as_of: date,
    weights: Dict[str, float],
) -> str:
    polls = list(polls)
    if not polls or total_weight <= 0:
        return "no_polls"

    freshest_poll_date = max(
        (
            poll_date
            for poll in polls
            for poll_date in [_parse_iso_date(poll.end_date) or _parse_iso_date(poll.start_date)]
            if poll_date is not None
        ),
        default=None,
    )
    if freshest_poll_date is not None:
        half_life_days = weights.get("recency_half_life_days", 14.0)
        if half_life_days > 0 and (as_of - freshest_poll_date).days > (half_life_days * 2):
            return "stale_polling"

    if len(polls) == 1:
        return "sparse_polling"

    return "polling_available"


def compute_polling_average(
    polls: Iterable[Poll],
    *,
    as_of_date: Optional[str] = None,
    calibration: Optional[CalibrationBundle] = None,
) -> PollingAverage:
    """Compute a weighted polling average from normalized poll inputs."""

    bundle = calibration or load_calibration_bundle()
    as_of = _resolve_as_of_date(as_of_date)
    poll_list = list(polls)

    if not poll_list:
        return PollingAverage(
            poll_count=0,
            as_of_date=as_of.isoformat(),
            data_quality="no_polls",
            total_weight=0.0,
        )

    weighted_support: Dict[str, float] = {}
    candidate_weight: Dict[str, float] = {}
    total_weight = 0.0

    for poll in poll_list:
        weight = poll_weight(poll, as_of_date=as_of.isoformat(), calibration=bundle)
        if weight <= 0:
            continue

        total_weight += weight
        for result in poll.results:
            weighted_support[result.candidate_name] = (
                weighted_support.get(result.candidate_name, 0.0) + (result.support_pct * weight)
            )
            candidate_weight[result.candidate_name] = candidate_weight.get(result.candidate_name, 0.0) + weight

    if not weighted_support:
        return PollingAverage(
            poll_count=len(poll_list),
            as_of_date=as_of.isoformat(),
            data_quality="no_polls",
            total_weight=0.0,
        )

    support_by_candidate = {
        candidate_name: weighted_support[candidate_name] / candidate_weight[candidate_name]
        for candidate_name in weighted_support
        if candidate_weight[candidate_name] > 0
    }
    ranked_candidates = sorted(
        support_by_candidate.items(),
        key=lambda item: (-item[1], item[0]),
    )

    leading_candidate, leading_support = ranked_candidates[0]
    runner_up_candidate = None
    runner_up_support = None
    lead_margin = None
    if len(ranked_candidates) > 1:
        runner_up_candidate, runner_up_support = ranked_candidates[1]
        lead_margin = leading_support - runner_up_support

    return PollingAverage(
        support_by_candidate=support_by_candidate,
        leading_candidate=leading_candidate,
        leading_support=leading_support,
        runner_up_candidate=runner_up_candidate,
        runner_up_support=runner_up_support,
        lead_margin=lead_margin,
        poll_count=len(poll_list),
        as_of_date=as_of.isoformat(),
        data_quality=_data_quality(
            poll_list,
            total_weight=total_weight,
            as_of=as_of,
            weights=bundle.polling_weights,
        ),
        total_weight=total_weight,
    )
