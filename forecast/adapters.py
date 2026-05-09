"""Race-type forecast adapters built on the Phase 1/2 polling foundation."""

from __future__ import annotations

import hashlib
import math
import random
import statistics
from dataclasses import asdict
from typing import Dict, Mapping, Optional

from forecast.calibration import CalibrationBundle, load_calibration_bundle
from forecast.classify import classify_race
from forecast.types import Candidate, Forecast, PollingAverage, Race, RaceFundamentals, RaceType

Z_SCORES = {
    "p05": -1.645,
    "p25": -0.674,
    "p50": 0.0,
    "p75": 0.674,
    "p95": 1.645,
}
SUPPORTED_RACE_TYPES = {
    "binary_head_to_head",
    "multicandidate_plurality",
    "top_two_advance",
    "congressional",
    "presidential_state",
}
DEFAULT_BATCH_COUNT = 40
DEFAULT_BATCH_SIZE = 100
DEFAULT_TRADE_THRESHOLD_CENTS = 5


def _clamp_probability(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def _candidate_support(polling_average: PollingAverage, candidate_name: str) -> float:
    return float(polling_average.support_by_candidate.get(candidate_name, 0.0))


def _candidate_lead(polling_average: PollingAverage, candidate_name: str) -> float:
    candidate_support = _candidate_support(polling_average, candidate_name)
    strongest_other = max(
        (
            float(support)
            for other_name, support in polling_average.support_by_candidate.items()
            if other_name != candidate_name
        ),
        default=0.0,
    )
    return candidate_support - strongest_other


def _interval_width(
    polling_average: PollingAverage,
    *,
    data_quality: Optional[str] = None,
) -> float:
    data_quality = data_quality or polling_average.data_quality or "no_polls"
    base_width = {
        "polling_available": 0.12,
        "sparse_polling": 0.18,
        "stale_polling": 0.22,
        "no_polls": 0.28,
        "fundamentals_dominant": 0.24,
        "fundamentals_only": 0.3,
    }.get(data_quality, 0.2)

    poll_bonus = min(max(polling_average.poll_count - 2, 0), 4) * 0.01
    weight_bonus = min(polling_average.total_weight / 30.0, 0.04)
    return max(0.06, base_width - poll_bonus - weight_bonus)


def _confidence(polling_average: PollingAverage, *, interval_width: float) -> str:
    data_quality = polling_average.data_quality or "no_polls"
    if data_quality == "polling_available" and polling_average.poll_count >= 4 and interval_width <= 0.12:
        return "high"
    if data_quality == "polling_available" and interval_width <= 0.2:
        return "medium"
    if data_quality == "sparse_polling" and interval_width <= 0.16:
        return "medium"
    return "low"


def _has_fundamentals(fundamentals: Optional[RaceFundamentals]) -> bool:
    if fundamentals is None:
        return False
    if fundamentals.favored_candidate and fundamentals.baseline_margin is not None:
        return True
    return bool(fundamentals.outcome_fundamentals)


def _resolve_fundamentals_weight(
    race_type: RaceType,
    polling_average: PollingAverage,
    *,
    calibration: CalibrationBundle,
    fundamentals: Optional[RaceFundamentals],
) -> float:
    if not _has_fundamentals(fundamentals):
        return 0.0

    model_key = "state_partisanship_weight" if race_type == "presidential_state" else "fundamentals_weight"
    base_weight = float(calibration.race_models.get(race_type, {}).get(model_key, 0.35))
    data_quality = polling_average.data_quality or "no_polls"
    if data_quality == "no_polls" or not polling_average.support_by_candidate or polling_average.poll_count <= 0:
        return 1.0
    if data_quality == "sparse_polling":
        return min(0.75, base_weight + 0.3)
    if data_quality == "stale_polling":
        return min(0.6, base_weight + 0.15)
    return min(0.2, base_weight * 0.25)


def _resolve_data_quality(
    polling_average: PollingAverage,
    *,
    fundamentals_weight: float,
) -> str:
    base_quality = polling_average.data_quality or "no_polls"
    if fundamentals_weight <= 0:
        return base_quality
    if base_quality == "no_polls" or fundamentals_weight >= 0.99:
        return "fundamentals_only"
    if fundamentals_weight >= 0.5:
        return "fundamentals_dominant"
    return base_quality


def _clamp_support(value: float) -> float:
    return min(max(value, 0.0), 100.0)


def _log_money(value: Optional[float]) -> float:
    if value is None or value <= 0:
        return 0.0
    return math.log1p(value)


def _financial_score(
    fundamentals: Optional[RaceFundamentals],
    candidate_name: str,
) -> float:
    if fundamentals is None:
        return 0.0
    candidate = fundamentals.outcome_fundamentals.get(candidate_name)
    if candidate is None:
        return 0.0
    return (
        (0.45 * _log_money(candidate.receipts))
        + (0.35 * _log_money(candidate.cash_on_hand))
        + (0.15 * _log_money(candidate.outside_spend))
        - (0.15 * _log_money(candidate.disbursements))
    )


def _baseline_margin(
    fundamentals: Optional[RaceFundamentals],
    candidate_name: str,
) -> float:
    if fundamentals is None or fundamentals.favored_candidate is None or fundamentals.baseline_margin is None:
        return 0.0
    if candidate_name == fundamentals.favored_candidate:
        return float(fundamentals.baseline_margin)
    return -float(fundamentals.baseline_margin)


def _financial_margin(
    race: Race,
    fundamentals: Optional[RaceFundamentals],
    candidate_name: str,
) -> float:
    candidate_score = _financial_score(fundamentals, candidate_name)
    strongest_other = max(
        (
            _financial_score(fundamentals, candidate.name)
            for candidate in race.candidates
            if candidate.name != candidate_name
        ),
        default=0.0,
    )
    score_gap = candidate_score - strongest_other
    return 2.5 * math.tanh(score_gap / 2.5)


def _effective_binary_lead(
    race: Race,
    polling_average: PollingAverage,
    *,
    candidate_name: str,
    race_type: RaceType,
    calibration: CalibrationBundle,
    fundamentals: Optional[RaceFundamentals],
) -> Dict[str, float]:
    raw_lead = _candidate_lead(polling_average, candidate_name)
    fundamentals_weight = _resolve_fundamentals_weight(
        race_type,
        polling_average,
        calibration=calibration,
        fundamentals=fundamentals,
    )
    baseline_margin = _baseline_margin(fundamentals, candidate_name)
    financial_margin = _financial_margin(race, fundamentals, candidate_name)
    fundamentals_margin = baseline_margin + financial_margin
    effective_lead = ((1.0 - fundamentals_weight) * raw_lead) + (fundamentals_weight * fundamentals_margin)
    if fundamentals_weight >= 0.99:
        effective_lead = fundamentals_margin
    return {
        "raw_lead": raw_lead,
        "baseline_margin": baseline_margin,
        "financial_margin": financial_margin,
        "fundamentals_margin": fundamentals_margin,
        "fundamentals_weight": fundamentals_weight,
        "effective_lead": effective_lead,
        "effective_support": _clamp_support(50.0 + (effective_lead / 2.0)),
    }


def build_verdict(
    *,
    market_price: Optional[int],
    p25: float,
    p50: float,
    p75: float,
    threshold_cents: int = DEFAULT_TRADE_THRESHOLD_CENTS,
) -> Dict[str, object]:
    """Return a state-compatible verdict with an uncertainty gate."""

    resolved_market_price = int(round(float(50 if market_price is None else market_price)))
    marcus_fv = int(round(float(p50) * 100.0))
    edge = marcus_fv - resolved_market_price
    interval_low = int(round(float(p25) * 100.0))
    interval_high = int(round(float(p75) * 100.0))
    passes_edge_threshold = abs(edge) >= threshold_cents
    uncertainty_supports_trade = (
        resolved_market_price < interval_low or resolved_market_price > interval_high
    )
    verdict = "TRADE" if passes_edge_threshold and uncertainty_supports_trade else "PASS"

    return {
        "market_price": resolved_market_price,
        "marcus_fv": marcus_fv,
        "edge": edge,
        "delta": edge,
        "verdict": verdict,
        "threshold_cents": threshold_cents,
        "uncertainty_band_low": interval_low,
        "uncertainty_band_high": interval_high,
        "passes_edge_threshold": passes_edge_threshold,
        "uncertainty_supports_trade": uncertainty_supports_trade,
    }


def _binary_lead_standard_deviation(
    polling_average: PollingAverage,
    *,
    data_quality: Optional[str] = None,
) -> float:
    data_quality = data_quality or polling_average.data_quality or "no_polls"
    base_std = {
        "polling_available": 2.6,
        "sparse_polling": 3.6,
        "stale_polling": 4.3,
        "no_polls": 5.0,
        "fundamentals_dominant": 4.8,
        "fundamentals_only": 5.6,
    }.get(data_quality, 4.0)

    poll_bonus = min(max(polling_average.poll_count - 1, 0), 4) * 0.15
    weight_bonus = min(polling_average.total_weight / 40.0, 0.35)
    return max(1.4, base_std - poll_bonus - weight_bonus)


def _logistic_probability(lead: float, lead_scale: float) -> float:
    scale = lead_scale if lead_scale > 0 else 3.25
    return _clamp_probability(1.0 / (1.0 + math.exp(-(lead / scale))))


def _build_binary_intervals(
    lead: float,
    *,
    lead_scale: float,
    lead_standard_deviation: float,
) -> Dict[str, float]:
    return {
        bucket: _logistic_probability(lead + (z_score * lead_standard_deviation), lead_scale)
        for bucket, z_score in Z_SCORES.items()
    }


def _simulation_seed(race: Race, race_type: RaceType) -> int:
    parts = [
        race_type,
        race.race_id or "",
        race.event_ticker or "",
        race.title,
        race.format_hint or "",
        "|".join(candidate.contract_ticker for candidate in race.candidates),
    ]
    digest = hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _simulation_spread(
    polling_average: PollingAverage,
    *,
    base_spread: float,
) -> float:
    data_quality = polling_average.data_quality or "no_polls"
    quality_multiplier = {
        "polling_available": 1.0,
        "sparse_polling": 1.2,
        "stale_polling": 1.35,
        "no_polls": 1.5,
    }.get(data_quality, 1.25)
    spread = base_spread * quality_multiplier / math.sqrt(max(polling_average.poll_count, 1))
    if polling_average.total_weight >= 25:
        spread *= 0.9
    elif polling_average.total_weight <= 10:
        spread *= 1.1
    return max(1.0, spread)


def _simulate_batches(
    race: Race,
    polling_average: PollingAverage,
    *,
    base_spread: float,
    finish_cutoff: int,
    race_type: RaceType,
    batch_count: int = DEFAULT_BATCH_COUNT,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> Dict[str, Dict[str, float]]:
    rng = random.Random(_simulation_seed(race, race_type))
    spread = _simulation_spread(polling_average, base_spread=base_spread)
    candidate_names = [candidate.name for candidate in race.candidates]
    batch_rates = {candidate.name: [] for candidate in race.candidates}
    overall_counts = {candidate.name: 0 for candidate in race.candidates}

    for _ in range(batch_count):
        batch_counts = {candidate.name: 0 for candidate in race.candidates}
        for _ in range(batch_size):
            simulated_support = [
                (
                    _candidate_support(polling_average, candidate.name) + rng.gauss(0.0, spread),
                    candidate.name,
                )
                for candidate in race.candidates
            ]
            ranked = sorted(simulated_support, key=lambda item: (-item[0], item[1]))
            finishers = {candidate_name for _, candidate_name in ranked[:finish_cutoff]}
            for candidate_name in finishers:
                batch_counts[candidate_name] += 1
                overall_counts[candidate_name] += 1

        for candidate_name in candidate_names:
            batch_rates[candidate_name].append(batch_counts[candidate_name] / float(batch_size))

    total_simulations = float(batch_count * batch_size)
    probability_by_candidate: Dict[str, Dict[str, float]] = {}
    for candidate_name in candidate_names:
        mean_probability = overall_counts[candidate_name] / total_simulations
        deviation = statistics.pstdev(batch_rates[candidate_name]) if batch_rates[candidate_name] else 0.0
        probability_by_candidate[candidate_name] = {
            "p05": _clamp_probability(mean_probability + (Z_SCORES["p05"] * deviation)),
            "p25": _clamp_probability(mean_probability + (Z_SCORES["p25"] * deviation)),
            "p50": mean_probability,
            "p75": _clamp_probability(mean_probability + (Z_SCORES["p75"] * deviation)),
            "p95": _clamp_probability(mean_probability + (Z_SCORES["p95"] * deviation)),
        }
    return probability_by_candidate


def _forecast_inputs(
    polling_average: PollingAverage,
    *,
    threshold_cents: int,
    simulation_spread: Optional[float] = None,
) -> Dict[str, float]:
    values = {
        "poll_count": float(polling_average.poll_count),
        "total_weight": float(polling_average.total_weight),
        "threshold_cents": float(threshold_cents),
    }
    if simulation_spread is not None:
        values["simulation_spread"] = float(simulation_spread)
    return values


def _build_outcome_entry(
    candidate: Candidate,
    race_type: RaceType,
    polling_average: PollingAverage,
    probability_block: Mapping[str, float],
    calibration: CalibrationBundle,
    *,
    threshold_cents: int,
    simulation_spread: Optional[float] = None,
    support_value: Optional[float] = None,
    lead_value: Optional[float] = None,
    data_quality: Optional[str] = None,
    confidence: Optional[str] = None,
    extra_inputs: Optional[Mapping[str, float]] = None,
) -> Dict[str, object]:
    interval_width = float(probability_block["p75"]) - float(probability_block["p25"])
    resolved_confidence = confidence or _confidence(polling_average, interval_width=interval_width)
    candidate_support = (
        float(support_value)
        if support_value is not None
        else _candidate_support(polling_average, candidate.name)
    )
    candidate_lead = float(lead_value) if lead_value is not None else _candidate_lead(polling_average, candidate.name)
    resolved_data_quality = data_quality or polling_average.data_quality or "no_polls"
    inputs = _forecast_inputs(
        polling_average,
        threshold_cents=threshold_cents,
        simulation_spread=simulation_spread,
    )
    if extra_inputs:
        inputs.update({str(key): float(value) for key, value in extra_inputs.items()})
    forecast_block = asdict(
        Forecast(
            model=calibration.model_name,
            race_type=race_type,
            calibration_version=calibration.version,
            polling_average=candidate_support,
            polling_lead=candidate_lead,
            p05=float(probability_block["p05"]),
            p25=float(probability_block["p25"]),
            p50=float(probability_block["p50"]),
            p75=float(probability_block["p75"]),
            p95=float(probability_block["p95"]),
            confidence=resolved_confidence,
            data_quality=resolved_data_quality,
            inputs=inputs,
        )
    )
    verdict_details = build_verdict(
        market_price=candidate.market_price,
        p25=float(probability_block["p25"]),
        p50=float(probability_block["p50"]),
        p75=float(probability_block["p75"]),
        threshold_cents=threshold_cents,
    )
    return {
        "contract_ticker": candidate.contract_ticker,
        "candidate_name": candidate.name,
        "market_price": verdict_details["market_price"],
        "forecast": forecast_block,
        "marcus_fv": verdict_details["marcus_fv"],
        "edge": verdict_details["edge"],
        "delta": verdict_details["delta"],
        "verdict": verdict_details["verdict"],
        "verdict_details": verdict_details,
    }


def _adapt_binary_with_fundamentals(
    race: Race,
    polling_average: PollingAverage,
    *,
    race_type: RaceType,
    calibration: Optional[CalibrationBundle] = None,
    threshold_cents: int = DEFAULT_TRADE_THRESHOLD_CENTS,
    fundamentals: Optional[RaceFundamentals] = None,
) -> Dict[str, Dict[str, object]]:
    bundle = calibration or load_calibration_bundle()
    effective_data_quality = _resolve_data_quality(
        polling_average,
        fundamentals_weight=_resolve_fundamentals_weight(
            race_type,
            polling_average,
            calibration=bundle,
            fundamentals=fundamentals,
        ),
    )
    lead_scale = bundle.race_models.get("binary_head_to_head", {}).get("lead_scale", 3.25)
    lead_standard_deviation = _binary_lead_standard_deviation(
        polling_average,
        data_quality=effective_data_quality,
    )
    results: Dict[str, Dict[str, object]] = {}
    for candidate in race.candidates:
        effective = _effective_binary_lead(
            race,
            polling_average,
            candidate_name=candidate.name,
            race_type=race_type,
            calibration=bundle,
            fundamentals=fundamentals,
        )
        probability_block = _build_binary_intervals(
            effective["effective_lead"],
            lead_scale=lead_scale,
            lead_standard_deviation=lead_standard_deviation,
        )
        interval_width = float(probability_block["p75"]) - float(probability_block["p25"])
        resolved_confidence = (
            "low"
            if effective_data_quality in {"fundamentals_dominant", "fundamentals_only"}
            else _confidence(polling_average, interval_width=interval_width)
        )
        results[candidate.contract_ticker] = _build_outcome_entry(
            candidate,
            race_type,
            polling_average,
            probability_block,
            bundle,
            threshold_cents=threshold_cents,
            support_value=effective["effective_support"],
            lead_value=effective["effective_lead"],
            data_quality=effective_data_quality,
            confidence=resolved_confidence,
            extra_inputs={
                "fundamentals_weight": effective["fundamentals_weight"],
                "baseline_margin": effective["baseline_margin"],
                "financial_margin": effective["financial_margin"],
                "effective_lead": effective["effective_lead"],
            },
        )
    return results


def adapt_binary_head_to_head(
    race: Race,
    polling_average: PollingAverage,
    *,
    calibration: Optional[CalibrationBundle] = None,
    threshold_cents: int = DEFAULT_TRADE_THRESHOLD_CENTS,
    ) -> Dict[str, Dict[str, object]]:
    """Convert a binary polling lead into outcome probabilities."""

    return _adapt_binary_with_fundamentals(
        race,
        polling_average,
        race_type="binary_head_to_head",
        calibration=calibration,
        threshold_cents=threshold_cents,
    )


def adapt_presidential_state(
    race: Race,
    polling_average: PollingAverage,
    *,
    calibration: Optional[CalibrationBundle] = None,
    threshold_cents: int = DEFAULT_TRADE_THRESHOLD_CENTS,
    fundamentals: Optional[RaceFundamentals] = None,
) -> Dict[str, Dict[str, object]]:
    """Use the binary adapter path, with optional state lean when polling is thin."""

    return _adapt_binary_with_fundamentals(
        race,
        polling_average,
        race_type="presidential_state",
        calibration=calibration,
        threshold_cents=threshold_cents,
        fundamentals=fundamentals,
    )


def adapt_congressional(
    race: Race,
    polling_average: PollingAverage,
    *,
    calibration: Optional[CalibrationBundle] = None,
    threshold_cents: int = DEFAULT_TRADE_THRESHOLD_CENTS,
    fundamentals: Optional[RaceFundamentals] = None,
) -> Dict[str, Dict[str, object]]:
    """Use a conservative binary-style path with fundamentals fallbacks for sparse polling."""

    return _adapt_binary_with_fundamentals(
        race,
        polling_average,
        race_type="congressional",
        calibration=calibration,
        threshold_cents=threshold_cents,
        fundamentals=fundamentals,
    )


def adapt_multicandidate_plurality(
    race: Race,
    polling_average: PollingAverage,
    *,
    calibration: Optional[CalibrationBundle] = None,
    threshold_cents: int = DEFAULT_TRADE_THRESHOLD_CENTS,
) -> Dict[str, Dict[str, object]]:
    """Estimate plurality win probabilities via deterministic seeded simulation."""

    bundle = calibration or load_calibration_bundle()
    simulation_spread = bundle.race_models.get("multicandidate_plurality", {}).get(
        "simulation_spread",
        5.0,
    )
    probability_by_candidate = _simulate_batches(
        race,
        polling_average,
        base_spread=simulation_spread,
        finish_cutoff=1,
        race_type="multicandidate_plurality",
    )
    return {
        candidate.contract_ticker: _build_outcome_entry(
            candidate,
            "multicandidate_plurality",
            polling_average,
            probability_by_candidate[candidate.name],
            bundle,
            threshold_cents=threshold_cents,
            simulation_spread=simulation_spread,
        )
        for candidate in race.candidates
    }


def adapt_top_two_advance(
    race: Race,
    polling_average: PollingAverage,
    *,
    calibration: Optional[CalibrationBundle] = None,
    threshold_cents: int = DEFAULT_TRADE_THRESHOLD_CENTS,
) -> Dict[str, Dict[str, object]]:
    """Estimate top-two advance probabilities via deterministic seeded simulation."""

    bundle = calibration or load_calibration_bundle()
    simulation_spread = bundle.race_models.get("top_two_advance", {}).get(
        "simulation_spread",
        5.5,
    )
    probability_by_candidate = _simulate_batches(
        race,
        polling_average,
        base_spread=simulation_spread,
        finish_cutoff=min(2, len(race.candidates)),
        race_type="top_two_advance",
    )
    return {
        candidate.contract_ticker: _build_outcome_entry(
            candidate,
            "top_two_advance",
            polling_average,
            probability_by_candidate[candidate.name],
            bundle,
            threshold_cents=threshold_cents,
            simulation_spread=simulation_spread,
        )
        for candidate in race.candidates
    }


def adapt_race_forecast(
    race: Race,
    polling_average: PollingAverage,
    *,
    calibration: Optional[CalibrationBundle] = None,
    race_type: Optional[RaceType] = None,
    threshold_cents: int = DEFAULT_TRADE_THRESHOLD_CENTS,
    fundamentals: Optional[RaceFundamentals] = None,
) -> Dict[str, Dict[str, object]]:
    """Dispatch to the appropriate forecast adapter."""

    resolved_race_type = race_type or classify_race(race)
    if resolved_race_type not in SUPPORTED_RACE_TYPES:
        raise ValueError(f"Race type {resolved_race_type!r} is not supported by Phase 3 adapters.")

    bundle = calibration or load_calibration_bundle()
    if resolved_race_type == "binary_head_to_head":
        return adapt_binary_head_to_head(
            race,
            polling_average,
            calibration=bundle,
            threshold_cents=threshold_cents,
        )
    if resolved_race_type == "presidential_state":
        return adapt_presidential_state(
            race,
            polling_average,
            calibration=bundle,
            threshold_cents=threshold_cents,
            fundamentals=fundamentals,
        )
    if resolved_race_type == "congressional":
        return adapt_congressional(
            race,
            polling_average,
            calibration=bundle,
            threshold_cents=threshold_cents,
            fundamentals=fundamentals,
        )
    if resolved_race_type == "multicandidate_plurality":
        return adapt_multicandidate_plurality(
            race,
            polling_average,
            calibration=bundle,
            threshold_cents=threshold_cents,
        )
    return adapt_top_two_advance(
        race,
        polling_average,
        calibration=bundle,
        threshold_cents=threshold_cents,
    )


__all__ = [
    "adapt_binary_head_to_head",
    "adapt_congressional",
    "adapt_multicandidate_plurality",
    "adapt_presidential_state",
    "adapt_race_forecast",
    "adapt_top_two_advance",
    "build_verdict",
]
