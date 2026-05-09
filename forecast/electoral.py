"""Lightweight Electoral College helpers for presidential state forecasts."""

from __future__ import annotations

from typing import Dict, Mapping


def _clamp_probability(value: float) -> float:
    return min(max(float(value), 0.0), 1.0)


def compute_electoral_college_outlook(
    state_probabilities: Mapping[str, Mapping[str, float]],
    *,
    target_electoral_votes: int = 270,
) -> Dict[str, float]:
    """Return an exact Electoral College summary from per-state win probabilities."""

    distribution = {0: 1.0}
    expected_electoral_votes = 0.0

    for _, values in sorted(state_probabilities.items()):
        electoral_votes = int(values["electoral_votes"])
        win_probability = _clamp_probability(values["win_probability"])
        expected_electoral_votes += electoral_votes * win_probability

        next_distribution: Dict[int, float] = {}
        for electoral_total, total_probability in distribution.items():
            next_distribution[electoral_total] = (
                next_distribution.get(electoral_total, 0.0)
                + (total_probability * (1.0 - win_probability))
            )
            next_distribution[electoral_total + electoral_votes] = (
                next_distribution.get(electoral_total + electoral_votes, 0.0)
                + (total_probability * win_probability)
            )
        distribution = next_distribution

    sorted_totals = sorted(distribution.items())
    win_probability = sum(
        probability
        for electoral_total, probability in sorted_totals
        if electoral_total >= target_electoral_votes
    )

    cumulative_probability = 0.0
    median_electoral_votes = 0
    for electoral_total, probability in sorted_totals:
        cumulative_probability += probability
        if cumulative_probability >= 0.5:
            median_electoral_votes = electoral_total
            break

    return {
        "method": "exact",
        "state_count": len(state_probabilities),
        "target_electoral_votes": int(target_electoral_votes),
        "expected_electoral_votes": expected_electoral_votes,
        "median_electoral_votes": float(median_electoral_votes),
        "win_probability": win_probability,
        "distribution_support": float(len(distribution)),
    }
