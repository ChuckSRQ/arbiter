"""Shared forecast data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

RaceType = Literal[
    "binary_head_to_head",
    "multicandidate_plurality",
    "top_two_advance",
    "congressional",
    "presidential_state",
    "unknown",
]


@dataclass(frozen=True)
class Candidate:
    """One Kalshi candidate outcome/contract within a race."""

    name: str
    contract_ticker: str
    party: Optional[str] = None
    market_price: Optional[int] = None


@dataclass(frozen=True)
class PollResult:
    """One candidate's support inside a poll."""

    candidate_name: str
    support_pct: float


@dataclass(frozen=True)
class Poll:
    """Normalized poll input for later weighting/calibration phases."""

    pollster: str
    results: List[PollResult]
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    sample_size: Optional[int] = None
    population: Optional[str] = None
    sponsor: Optional[str] = None
    pollster_rating: Optional[float] = None
    notes: Optional[str] = None
    is_internal: bool = False


@dataclass(frozen=True)
class Race:
    """One election race that can contain one or more candidate outcomes."""

    title: str
    candidates: List[Candidate] = field(default_factory=list)
    race_id: Optional[str] = None
    office: Optional[str] = None
    geography: Optional[str] = None
    event_date: Optional[str] = None
    event_ticker: Optional[str] = None
    series_ticker: Optional[str] = None
    format_hint: Optional[str] = None


@dataclass(frozen=True)
class OutcomeFundamentals:
    """Lightweight per-outcome fundamentals used when polling is thin."""

    receipts: Optional[float] = None
    disbursements: Optional[float] = None
    cash_on_hand: Optional[float] = None
    outside_spend: Optional[float] = None


@dataclass(frozen=True)
class RaceFundamentals:
    """Race-level fundamentals inputs for sparse-poll readiness."""

    favored_candidate: Optional[str] = None
    baseline_margin: Optional[float] = None
    outcome_fundamentals: Dict[str, OutcomeFundamentals] = field(default_factory=dict)


@dataclass(frozen=True)
class Forecast:
    """Forecast payload shape planned for state entries."""

    model: str
    race_type: RaceType
    calibration_version: str
    polling_average: Optional[float] = None
    polling_lead: Optional[float] = None
    p05: Optional[float] = None
    p25: Optional[float] = None
    p50: Optional[float] = None
    p75: Optional[float] = None
    p95: Optional[float] = None
    confidence: Optional[str] = None
    data_quality: Optional[str] = None
    inputs: Dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class PollingAverage:
    """Weighted polling average plus lightweight metadata for later forecast phases."""

    support_by_candidate: Dict[str, float] = field(default_factory=dict)
    leading_candidate: Optional[str] = None
    leading_support: Optional[float] = None
    runner_up_candidate: Optional[str] = None
    runner_up_support: Optional[float] = None
    lead_margin: Optional[float] = None
    poll_count: int = 0
    as_of_date: Optional[str] = None
    data_quality: Optional[str] = None
    total_weight: float = 0.0
