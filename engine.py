"""Arbiter Engine — polling analysis and fair value estimation."""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from forecast import Candidate, Poll, PollResult, Race, adapt_race_forecast, compute_polling_average
from state import get_pending, read_state, transition, write_state

APPROVAL_URL = (
    "https://api.votehub.com/polls?poll_type=approval&subject=donald-trump&from_date=2026-04-01"
)
GENERIC_URL = "https://api.votehub.com/polls?poll_type=generic-ballot&subject=2026"
REQUEST_DELAY = 0.5
OPENFEC_BASE = "https://api.open.fec.gov/v1"
OPENFEC_KEY = "DEMO_KEY"
OPENFEC_REQUEST_DELAY = 0.5

SIX_PCT_THRESHOLD = 6.0

# Wikipedia polling lookup
_WIKIPEDIA_BASE = "https://en.wikipedia.org/wiki"


def _wikipedia_url(race_title, event_date):
    """Construct Wikipedia article URL from race title and event date."""
    if not event_date:
        return None
    year_match = re.search(r"20\d{2}", str(event_date))
    year = year_match.group(0) if year_match else "2026"
    title_lower = (race_title or "").lower()
    if "mayor" in title_lower or "los angeles" in title_lower:
        return f"{_WIKIPEDIA_BASE}/{year}_Los_Angeles_mayoral_election"
    if "armenia" in title_lower and "parliamentary" in title_lower:
        return f"{_WIKIPEDIA_BASE}/{year}_Armenian_parliamentary_election"
    if "colombia" in title_lower and "presidential" in title_lower:
        return f"{_WIKIPEDIA_BASE}/{year}_Colombian_presidential_election"
    # UK General Election
    if any(kw in title_lower for kw in ["uk", "united kingdom", "british", "britain"]):
        if "parliament" in title_lower or "general" in title_lower:
            return f"{_WIKIPEDIA_BASE}/{year}_United_Kingdom_general_election"
    # France Presidential
    if "france" in title_lower and "president" in title_lower:
        return f"{_WIKIPEDIA_BASE}/{year}_French_presidential_election"
    # Germany Federal
    if "germany" in title_lower and ("bundestag" in title_lower or "federal" in title_lower):
        return f"{_WIKIPEDIA_BASE}/{year}_German_federal_election"
    if "parliamentary" in title_lower:
        country = re.sub(r"\b20\d{2}\b", "", title_lower).strip()
        country = re.sub(r"\s*parliamentary.*", "", country).strip()
        if country:
            return f"{_WIKIPEDIA_BASE}/{year}_{country}_parliamentary_election"
    if "presidential" in title_lower or "president" in title_lower:
        country = re.sub(r"\b20\d{2}\b", "", title_lower).strip()
        country = re.sub(r"\s*presidential.*", "", country).strip()
        country = re.sub(r"\s*president.*", "", country).strip()
        if country:
            return f"{_WIKIPEDIA_BASE}/{year}_{country}_presidential_election"
    return None


def _safe_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_recent_polls(payload):
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        for key in ("polls", "data", "results", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                rows = value
                break
        else:
            rows = []
    else:
        rows = []

    if not rows:
        return []

    def _poll_date_key(row):
        if not isinstance(row, dict):
            return datetime.min.replace(tzinfo=timezone.utc)
        for key in ("end_date", "date", "field_date", "created_at", "updated_at"):
            raw = row.get(key)
            if not raw:
                continue
            try:
                parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed
            except ValueError:
                continue
        return datetime.min.replace(tzinfo=timezone.utc)

    only_dicts = [row for row in rows if isinstance(row, dict)]
    only_dicts.sort(key=_poll_date_key, reverse=True)
    return only_dicts[:5]


def _extract_metric(poll, keys):
    def _normalize(value):
        return str(value or "").lower().replace(" ", "").replace("_", "")

    for key in keys:
        value = _safe_float(poll.get(key))
        if value is not None:
            return value

    results = poll.get("results")
    if isinstance(results, dict):
        for key in keys:
            value = _safe_float(results.get(key))
            if value is not None:
                return value
    if isinstance(results, list):
        for entry in results:
            if not isinstance(entry, dict):
                continue
            label = str(entry.get("label", "")).lower()
            candidate = str(entry.get("candidate", "")).lower()
            for key in keys:
                norm = key.lower().replace("_", "")
                if norm in label.replace(" ", "") or norm in candidate.replace(" ", ""):
                    value = _safe_float(entry.get("pct"))
                    if value is not None:
                        return value
                    value = _safe_float(entry.get("value"))
                    if value is not None:
                        return value
    for field in ("answers", "choices", "options"):
        rows = poll.get(field)
        if not isinstance(rows, list):
            continue
        for entry in rows:
            if not isinstance(entry, dict):
                continue
            choice = _normalize(entry.get("choice"))
            for key in keys:
                norm = _normalize(key)
                if norm in choice:
                    value = _safe_float(entry.get("pct"))
                    if value is not None:
                        return value
                    value = _safe_float(entry.get("value"))
                    if value is not None:
                        return value
    return None


def _parse_market_condition(title):
    text = (title or "").lower()
    between = re.search(r"between\s+(\d+(?:\.\d+)?)\s+and\s+(\d+(?:\.\d+)?)", text)
    if between:
        low = float(between.group(1))
        high = float(between.group(2))
        if low > high:
            low, high = high, low
        return {"kind": "between", "low": low, "high": high}

    above = re.search(r"above\s+(\d+(?:\.\d+)?)", text)
    if above:
        return {"kind": "above", "threshold": float(above.group(1))}

    below = re.search(r"below\s+(\d+(?:\.\d+)?)", text)
    if below:
        return {"kind": "below", "threshold": float(below.group(1))}

    return {"kind": "unknown"}


def _fv_for_above(avg_value, threshold):
    if avg_value > threshold + 2:
        return 85
    if avg_value > threshold:
        return 60
    if avg_value > threshold - 2:
        return 35
    return 10


def _fv_for_below(avg_value, threshold):
    if avg_value < threshold - 2:
        return 85
    if avg_value < threshold:
        return 60
    if avg_value < threshold + 2:
        return 35
    return 10


def _fv_for_between(avg_value, low, high, spread):
    midpoint = (low + high) / 2.0
    distance = abs(avg_value - midpoint)
    band = (high - low) / 2.0
    effective = distance - band
    if effective <= 0.2 and spread <= 1.5:
        return 85
    if effective <= 1.0 and spread <= 2.5:
        return 60
    if effective <= 2.0:
        return 35
    return 10


def _estimate_fv(avg_value, condition, spread):
    kind = condition.get("kind")
    if kind == "above":
        return _fv_for_above(avg_value, condition["threshold"])
    if kind == "below":
        return _fv_for_below(avg_value, condition["threshold"])
    if kind == "between":
        return _fv_for_between(avg_value, condition["low"], condition["high"], spread)
    return 50


def _market_type_race(ticker, series_ticker=None):
    """Return race-type string for a market ticker.

    Covers: approval, generic, mayor, senate, house, governor, international, other.
    """
    t = (ticker or "").upper()
    s = (series_ticker or "").upper()

    if "APRPOTUS" in t or "APPROVAL" in t:
        return "approval"
    if "GENERICBALLOT" in t or "VOTEHUB" in t:
        return "generic"
    if "MAYOR" in t:
        return "mayor"
    # Senate: series_ticker is KXSE, or contains SENATE, or ticker has KXSE + state code pattern
    if s == "KXSE" or "SENATE" in s or "SENATE" in t or re.search(r"KXSE[A-Z]{2}", t):
        return "senate"
    # House: series_ticker is KXHOU, or contains HOUSE, or ticker has KXHOU pattern
    if s == "KXHOU" or "HOUSE" in s or "HOUSE" in t or re.search(r"KXHOU", t):
        return "house"
    # Governor: series_ticker contains KXGOV, or ticker has KXGOV pattern
    if s == "KXGOV" or "GOV" in s or re.search(r"KXGOV", t):
        return "governor"
    if any(tag in (t + s) for tag in ("ARMENIA", "COLOMBIA", "LEBANON", "BRAZIL", "FRANCE", "GERMANY", "UK", "INTERNATIONAL")):
        return "international"
    return "other"


def _market_type(ticker):
    """Deprecated: use _market_type_race() for new code.

    Maps senate/house/governor/international → 'other' for backward compatibility.
    """
    t = (ticker or "").upper()
    if "KXAPRPOTUS" in t:
        return "approval"
    if "GENERICBALLOT" in t or "VOTEHUB" in t:
        return "generic"
    # Covers KXMAYORLA, KXLAMAYOR1R, KXMAYORLA-26JUN02, etc.
    if "MAYOR" in t:
        return "mayor"
    return "other"


def _forecast_probability_text(value):
    try:
        return f"{int(round(float(value) * 100.0))}%"
    except (TypeError, ValueError):
        return None


def _forecast_band_text(forecast):
    if not isinstance(forecast, dict):
        return None
    low = _forecast_probability_text(forecast.get("p25"))
    high = _forecast_probability_text(forecast.get("p75"))
    if not low or not high:
        return None
    return f"{low.rstrip('%')}-{high}"


def _humanize_forecast_text(value):
    text = str(value or "").strip().replace("_", " ")
    return text or None


def _forecast_summary_text(forecast, *, label="Forecast"):
    if not isinstance(forecast, dict):
        return ""

    parts = []
    median = _forecast_probability_text(forecast.get("p50"))
    band = _forecast_band_text(forecast)
    confidence = _humanize_forecast_text(forecast.get("confidence"))
    data_quality = _humanize_forecast_text(forecast.get("data_quality"))

    if median:
        parts.append(f"{median} median")
    if band:
        parts.append(f"{band} middle band")
    if confidence:
        parts.append(f"{confidence} confidence")
    if data_quality:
        parts.append(data_quality)

    if not parts:
        return ""
    return f"{label}: {', '.join(parts)}."


def _finalize_market(market, marcus_fv, context, analysis, sources, forecast=None, forecast_note=None):
    price = market.get("market_price")
    if price is None:
        price = 50
    delta = int(round(float(marcus_fv) - float(price)))
    market["marcus_fv"] = int(round(float(marcus_fv)))
    market["delta"] = delta
    market["verdict"] = "TRADE" if abs(delta) >= 5 else "PASS"
    market["context"] = context
    resolved_analysis = str(analysis or "").strip()
    if forecast:
        market["forecast"] = forecast
        note = str(forecast_note or _forecast_summary_text(forecast)).strip()
        if note:
            resolved_analysis = f"{resolved_analysis} {note}".strip()
    else:
        market.pop("forecast", None)
    market["analysis"] = resolved_analysis
    market["sources"] = sources


def _build_insufficient_note(polls_found):
    if polls_found < 2:
        return " Data quality note: fewer than two polls were available, so confidence is lower."
    return ""


def _synthetic_yes_support(metric_value, condition):
    kind = condition.get("kind")
    if kind == "above":
        signal = float(metric_value) - float(condition["threshold"])
    elif kind == "below":
        signal = float(condition["threshold"]) - float(metric_value)
    elif kind == "between":
        midpoint = (float(condition["low"]) + float(condition["high"])) / 2.0
        band = abs(float(condition["high"]) - float(condition["low"])) / 2.0
        signal = band - abs(float(metric_value) - midpoint)
    else:
        signal = 0.0
    return max(10.0, min(90.0, 50.0 + (signal * 4.0)))


def _poll_date_value(poll, *keys):
    for key in keys:
        value = poll.get(key)
        if value:
            return str(value)
    return None


def _poll_sample_size(poll):
    for key in ("sample_size", "sample", "samplesize", "n"):
        value = _safe_float(poll.get(key))
        if value is not None and value > 0:
            return int(round(value))
    return None


def _build_binary_threshold_forecast(market, measurements, condition, *, pollster_fallback):
    if not measurements or condition.get("kind") == "unknown":
        return None

    ticker = market.get("ticker") or "YES"
    yes_name = (market.get("candidate_name") or "Yes").strip() or "Yes"
    no_name = f"Not {yes_name}" if yes_name != "Yes" else "No"
    normalized_polls = []
    latest_poll_date = None

    for raw_poll, metric_value in measurements:
        yes_support = _synthetic_yes_support(metric_value, condition)
        poll_date = _poll_date_value(
            raw_poll,
            "end_date",
            "date",
            "field_date",
            "updated_at",
            "created_at",
            "start_date",
        )
        if poll_date and (latest_poll_date is None or poll_date > latest_poll_date):
            latest_poll_date = poll_date
        normalized_polls.append(
            Poll(
                pollster=str(raw_poll.get("pollster") or raw_poll.get("source") or pollster_fallback),
                results=[
                    PollResult(candidate_name=yes_name, support_pct=yes_support),
                    PollResult(candidate_name=no_name, support_pct=100.0 - yes_support),
                ],
                start_date=_poll_date_value(raw_poll, "start_date"),
                end_date=poll_date,
                sample_size=_poll_sample_size(raw_poll),
                population=raw_poll.get("population"),
                sponsor=raw_poll.get("sponsor") or raw_poll.get("source"),
                is_internal=bool(raw_poll.get("internal") or raw_poll.get("is_internal")),
            )
        )

    if not normalized_polls:
        return None

    race = Race(
        title=market.get("race_title") or market.get("title") or ticker,
        race_id=ticker,
        event_date=market.get("event_date") or market.get("election_date"),
        event_ticker=market.get("event_ticker"),
        series_ticker=market.get("series_ticker"),
        candidates=[
            Candidate(name=yes_name, contract_ticker=ticker, market_price=market.get("market_price")),
            Candidate(name=no_name, contract_ticker=f"{ticker}-NO"),
        ],
    )
    polling_average = compute_polling_average(normalized_polls, as_of_date=latest_poll_date)
    forecast = dict(adapt_race_forecast(race, polling_average, race_type="binary_head_to_head")[ticker]["forecast"])
    inputs = dict(forecast.get("inputs") or {})
    inputs["threshold_market"] = 1.0
    forecast["inputs"] = inputs
    if forecast.get("confidence") == "high":
        forecast["confidence"] = "medium"
    return forecast


def _analyze_approval_market(market, polls):
    condition = _parse_market_condition(market.get("title"))
    approve_values = []
    disapprove_values = []
    forecast_measurements = []
    for poll in polls:
        approve = _extract_metric(poll, ("approve", "approval", "approve_pct", "approval_pct"))
        disapprove = _extract_metric(
            poll, ("disapprove", "disapproval", "disapprove_pct", "disapproval_pct")
        )
        if approve is not None:
            approve_values.append(approve)
            forecast_measurements.append((poll, approve))
        if disapprove is not None:
            disapprove_values.append(disapprove)

    polls_found = min(len(approve_values), len(disapprove_values)) or max(
        len(approve_values), len(disapprove_values)
    )
    if approve_values:
        avg_approve = sum(approve_values) / len(approve_values)
        spread = max(approve_values) - min(approve_values) if len(approve_values) > 1 else 0.0
        fv = _estimate_fv(avg_approve, condition, spread)
        avg_disapprove = (
            sum(disapprove_values) / len(disapprove_values) if disapprove_values else 100.0 - avg_approve
        )
        quality_note = _build_insufficient_note(polls_found)
        context = (
            f"VoteHub approval polling (last {len(approve_values)} polls) shows average approval at "
            f"{avg_approve:.1f}% and disapproval at {avg_disapprove:.1f}%. "
            f"Recent approval readings span a {spread:.1f}-point range, indicating the current noise band."
            f"{quality_note}"
        )
        analysis = (
            f"This market resolves on a binary threshold from the listed bracket, and Marcus maps the "
            f"current polling level to an estimated fair value of {fv}¢ under the heuristic model. "
            f"Compared with the current market price of {market.get('market_price')}¢, the model signals "
            f"{'a tradable edge' if abs(fv - (market.get('market_price') or 50)) >= 5 else 'no clear edge'}."
        )
    else:
        fv = market.get("market_price") if market.get("market_price") is not None else 50
        context = (
            "VoteHub approval polling was queried, but usable approval/disapproval values were not present "
            "in the returned payload. The brief is completed with polling data unavailable for this market."
        )
        analysis = (
            "Without extractable polling values, Marcus defaults fair value to the live market price and "
            "does not flag an edge. This market is marked complete so the pipeline can continue."
        )

    sources = [
        {"label": "VoteHub approval polls", "url": APPROVAL_URL},
        {"label": "VoteHub API", "url": "https://api.votehub.com"},
    ]
    forecast = _build_binary_threshold_forecast(
        market,
        forecast_measurements,
        condition,
        pollster_fallback="VoteHub approval",
    )
    return fv, context, analysis, sources, forecast


def _analyze_generic_market(market, polls):
    condition = _parse_market_condition(market.get("title"))
    dem_values = []
    rep_values = []
    forecast_measurements = []
    for poll in polls:
        dem = _extract_metric(
            poll,
            (
                "democratic",
                "democrat",
                "dem",
                "dem_pct",
                "democratic_pct",
                "democratic_party",
            ),
        )
        rep = _extract_metric(
            poll,
            (
                "republican",
                "gop",
                "rep",
                "rep_pct",
                "republican_pct",
                "republican_party",
            ),
        )
        if dem is not None:
            dem_values.append(dem)
        if rep is not None:
            rep_values.append(rep)
        if dem is not None and rep is not None:
            forecast_measurements.append((poll, dem - rep))

    polls_found = min(len(dem_values), len(rep_values)) or max(len(dem_values), len(rep_values))
    if dem_values and rep_values:
        n = min(len(dem_values), len(rep_values))
        spreads = [dem_values[i] - rep_values[i] for i in range(n)]
        avg_dem = sum(dem_values[:n]) / n
        avg_rep = sum(rep_values[:n]) / n
        avg_spread = sum(spreads) / n
        spread_vol = max(spreads) - min(spreads) if len(spreads) > 1 else 0.0
        fv = _estimate_fv(avg_spread, condition, spread_vol)
        quality_note = _build_insufficient_note(polls_found)
        context = (
            f"VoteHub generic ballot polling (last {n} polls) shows Democrats at {avg_dem:.1f}% and "
            f"Republicans at {avg_rep:.1f}%, a Democratic spread of {avg_spread:.1f} points on average. "
            f"Recent spread readings vary by {spread_vol:.1f} points across the sample."
            f"{quality_note}"
        )
        analysis = (
            f"Marcus applies the same bracket heuristic to the Democratic spread and estimates fair value at "
            f"{fv}¢ for this binary market. Versus the current price of {market.get('market_price')}¢, "
            f"the model implies {'a tradable edge' if abs(fv - (market.get('market_price') or 50)) >= 5 else 'limited edge'}."
        )
    else:
        fv = market.get("market_price") if market.get("market_price") is not None else 50
        context = (
            "VoteHub generic ballot polling was queried, but usable Democratic/Republican values were not "
            "available in the response payload. The brief is completed with polling data unavailable."
        )
        analysis = (
            "Because spread values could not be computed, Marcus sets fair value equal to market price and "
            "flags no edge. The market remains fully documented and is marked complete."
        )

    sources = [
        {"label": "VoteHub generic ballot polls", "url": GENERIC_URL},
        {"label": "VoteHub API", "url": "https://api.votehub.com"},
    ]
    forecast = _build_binary_threshold_forecast(
        market,
        forecast_measurements,
        condition,
        pollster_fallback="VoteHub generic ballot",
    )
    return fv, context, analysis, sources, forecast


# LA Mayor 2026 race data — hardcoded from public polling
# May 1-4, 2026 — Tavern Research / Growth Machine Fund poll (n=531 LV, +/-6.1%)
# Before debate and Pratt's post-poll media surge (NBC interview, Joe Rogan, etc.)
# Memo notes: Bass ceiling ~20-25%, Raman beats Bass head-to-head, Pratt does not win any matchup
LA_MAYOR_POLLS = {
    "Karen Bass":      16,   # incumbent, May 1-4 poll
    "Nithya Raman":    12,   # city councilmember, May 1-4 poll
    "Spencer Pratt":   15,   # reality TV / conservative — RISING post-poll
    "Rae Huang":        4,   # housing advocate, May 1-4 poll
    "Adam Miller":      2,   # tech executive, May 1-4 poll
    "Other":           46,  # undecided / no first choice
}
LA_MAYOR_FUNDRAISING = {
    "Karen Bass":      28.5,
    "Adam Miller":     27.2,
    "Spencer Pratt":    5.4,
    "Nithya Raman":     5.3,
    "Rae Huang":        2.7,
}
LA_MAYOR_ELECTION_DATE = "June 2, 2026"  # 23 days away
LA_MAYOR_SOURCE_URL = "https://www.racetothewh.com/mayor/losangeles"


def _candidate_fv(market_price, candidate_name, poll_pct):
    """Estimate fair value for a mayoral candidate contract.

    This is a crowded nonpartisan mayoral field with a likely runoff, so top-choice
    support is not the same thing as win probability. The heuristic boosts viable
    top-two candidates while keeping low-polling candidates as long shots.
    """
    if poll_pct >= 25:
        base = 45
    elif poll_pct >= 20:
        base = 38
    elif poll_pct >= 15:
        base = 30
    elif poll_pct >= 10:
        base = 20
    elif poll_pct >= 5:
        base = 8
    elif poll_pct >= 1:
        base = 3
    else:
        base = 1

    # Reality check: if the market is already pricing a candidate materially above
    # their top-choice support, haircut the FV unless polling says they are clearly viable.
    if market_price is not None:
        diff = market_price - poll_pct
        if diff > 15:
            base = max(base - 7, 1)
        elif diff > 8:
            base = max(base - 4, 1)
    return base


def _analyze_mayor_race(market, all_markets_in_race):
    """Analyze a mayoral race as a group, computing per-candidate FV and race-level signal.

    Args:
        market: one of the market entries (used for context/sources only)
        all_markets_in_race: list of all markets in the same event_ticker group
    Returns:
        (race_fv, context, analysis, sources)
        race_fv is a dict keyed by ticker -> fair value
    """
    candidate_polls = dict(LA_MAYOR_POLLS)
    n_candidates = len(all_markets_in_race)

    # Build ticker -> candidate name mapping from Kalshi contract metadata
    ticker_to_candidate = {}
    for m in all_markets_in_race:
        ticker = m.get("ticker", "")
        name = (m.get("candidate_name") or "").strip()
        if not name:
            title = m.get("title", "")
            # Fallback for markets where candidate is embedded in title
            name = title
            for prefix in ("Will ", " win the LA mayoral election?", " win Los Angeles mayor?"):
                name = name.replace(prefix, "")
            name = name.strip()
        ticker_to_candidate[ticker] = name

    # Compute per-candidate FV
    race_fv = {}  # ticker -> fv cents
    for m in all_markets_in_race:
        ticker = m.get("ticker", "")
        price = m.get("market_price")
        candidate = ticker_to_candidate.get(ticker, "")
        poll_pct = candidate_polls.get(candidate, 2)
        fv = _candidate_fv(price, candidate, poll_pct)
        race_fv[ticker] = fv

    # Race-level signal
    sorted_candidates = sorted(
        [(ticker_to_candidate.get(t, t), ticker, race_fv.get(t, 5))
         for t, fv in race_fv.items()],
        key=lambda x: x[2],
        reverse=True
    )
    leading_ticker = sorted_candidates[0][1] if sorted_candidates else ""
    leading_name = sorted_candidates[0][0] if sorted_candidates else "Unknown"
    leading_fv = sorted_candidates[0][2] if sorted_candidates else 0

    # Build candidate table for context
    rows = []
    for name, ticker, fv in sorted_candidates:
        price = next((m.get("market_price") for m in all_markets_in_race if m.get("ticker") == ticker), None)
        poll = candidate_polls.get(name, "?")
        delta = fv - (price or 0) if price is not None else 0
        rows.append(f"{name}: {poll}% in polling, market at {price}¢, Marcus FV {fv}¢ (edge {delta:+.0f})")
    candidates_text = " | ".join(rows)

    context = (
        f"LA Mayor race polling (Tavern Research / Growth Machine Fund, May 1-4 2026, n=531 LV) "
        f"shows Karen Bass at {candidate_polls.get('Karen Bass', '?')}%, "
        f"Spencer Pratt at {candidate_polls.get('Spencer Pratt', '?')}%, "
        f"Nithya Raman at {candidate_polls.get('Nithya Raman', '?')}%, "
        f"with {round(candidate_polls.get('Other', 0))}% undecided. "
        f"Bass's ceiling is ~20-25% per the pollster. "
        f"Raman beats Bass in head-to-head matchups. "
        f"Pratt has done significant media (NBC interview, Joe Rogan, debates) since this poll — "
        f"his position has likely improved. "
        f"The primary is {LA_MAYOR_ELECTION_DATE} — {n_candidates} candidate contracts active. "
        f"Fundraising: Bass ${LA_MAYOR_FUNDRAISING.get('Karen Bass', '?')}M, Miller ${LA_MAYOR_FUNDRAISING.get('Adam Miller', '?')}M."
    )
    analysis = (
        f"May 1-4 poll (Tavern Research, n=531) shows Bass at her floor (~16-20%), "
        f"a dangerous position for an incumbent with near-universal name ID. "
        f"Raman leads Bass head-to-head 53-47, the only candidate who does. "
        f"Pratt is rising post-debate and post-interviews but the poll predates that surge — "
        f"his true position is likely stronger than 15%. "
        f"46% of voters are still undecided with 4 weeks to go. "
        f"Top-two runoff is the likely outcome — the race remains highly volatile."
    )
    sources = [
        {"label": "Tavern Research / Growth Machine Fund — LA Mayor Poll (May 1-4 2026)", "url": None},
        {"label": "Race to the WH — LA Mayor polling", "url": LA_MAYOR_SOURCE_URL},
    ]
    poll_results = [
        PollResult(candidate_name=name, support_pct=float(candidate_polls.get(name, 1.0)))
        for name in ticker_to_candidate.values()
    ]
    other_support = float(candidate_polls.get("Other", 0.0))
    if other_support > 0:
        poll_results.append(PollResult(candidate_name="Other", support_pct=other_support))

    race = Race(
        title=market.get("race_title") or market.get("title") or "Los Angeles mayor election",
        race_id=market.get("event_ticker") or market.get("series_ticker") or market.get("ticker"),
        office="Mayor",
        geography="Los Angeles",
        event_date=market.get("event_date") or market.get("election_date"),
        event_ticker=market.get("event_ticker"),
        series_ticker=market.get("series_ticker"),
        format_hint="top-two",
        candidates=[
            Candidate(
                name=ticker_to_candidate.get(m.get("ticker", ""), m.get("ticker", "")),
                contract_ticker=m.get("ticker", ""),
                market_price=m.get("market_price"),
            )
            for m in all_markets_in_race
        ],
    )
    polling_average = compute_polling_average(
        [
            Poll(
                pollster="Race to the WH / UCLA Luskin",
                results=poll_results,
                end_date="2026-04-15",
                sample_size=1200,
                population="likely voters",
                sponsor="Race to the WH",
            )
        ],
        as_of_date="2026-04-15",
    )
    forecast_entries = adapt_race_forecast(race, polling_average, race_type="top_two_advance")
    forecast_by_ticker = {
        ticker: dict(entry.get("forecast") or {})
        for ticker, entry in forecast_entries.items()
    }
    return race_fv, context, analysis, sources, forecast_by_ticker


class VoteHubClient:
    def __init__(self):
        self._cache = {}
        self._last_request_time = 0.0

    def fetch_recent(self, market_type):
        if market_type in self._cache:
            return self._cache[market_type]

        url = APPROVAL_URL if market_type == "approval" else GENERIC_URL
        elapsed = time.time() - self._last_request_time
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)

        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                polls = _extract_recent_polls(payload)
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
            polls = None

        self._last_request_time = time.time()
        self._cache[market_type] = polls
        return polls


class OpenFECClient:
    def __init__(self):
        self._cache = {}
        self._last_request_time = 0.0

    def fetch_json(self, path, params=None):
        query_params = dict(params or {})
        query_params["api_key"] = OPENFEC_KEY
        query = urllib.parse.urlencode(query_params, doseq=True)
        endpoint = path.lstrip("/")
        url = "{}/{}?{}".format(OPENFEC_BASE, endpoint, query)

        if url in self._cache:
            return self._cache[url]

        elapsed = time.time() - self._last_request_time
        if elapsed < OPENFEC_REQUEST_DELAY:
            time.sleep(OPENFEC_REQUEST_DELAY - elapsed)

        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
            payload = None
        finally:
            self._last_request_time = time.time()

        self._cache[url] = payload
        return payload

    def _get(self, path, params=None):
        return self.fetch_json(path, params)

    def fetch_totals(self, candidate_id):
        payload = self.fetch_json("/candidate/{}/totals/".format(candidate_id))
        if not isinstance(payload, dict):
            return None

        results = payload.get("results")
        if isinstance(results, list) and results:
            first = results[0]
            if isinstance(first, dict):
                return {
                    "receipts": first.get("receipts"),
                    "disbursements": first.get("disbursements"),
                    "cash_on_hand_end_period": first.get("cash_on_hand_end_period"),
                }
        if all(key in payload for key in ("receipts", "disbursements", "cash_on_hand_end_period")):
            return {
                "receipts": payload.get("receipts"),
                "disbursements": payload.get("disbursements"),
                "cash_on_hand_end_period": payload.get("cash_on_hand_end_period"),
            }
        return None

    def fetch_candidate_totals(self, candidate_id):
        return self.fetch_totals(candidate_id)

    def fetch_candidate_financials(self, candidate_id):
        totals = self.fetch_totals(candidate_id)
        if not totals:
            return None

        source_url = "{}/candidate/{}/totals/?api_key={}".format(
            OPENFEC_BASE, candidate_id, OPENFEC_KEY
        )
        return {
            "receipts": _safe_float(totals.get("receipts")),
            "disbursements": _safe_float(totals.get("disbursements")),
            "cash_on_hand": _safe_float(totals.get("cash_on_hand_end_period")),
            "source": "OpenFEC",
            "source_url": source_url,
        }


def _openfec_source():
    return {"label": "OpenFEC API", "url": OPENFEC_BASE}


def _append_source(sources, source):
    out = list(sources or [])
    for existing in out:
        if (
            isinstance(existing, dict)
            and existing.get("label") == source.get("label")
            and existing.get("url") == source.get("url")
        ):
            return out
    out.append(source)
    return out


def _national_financials_note():
    return {
        "note": "National-level market — no candidate-specific financials apply",
        "source": "OpenFEC",
        "url": OPENFEC_BASE,
    }


# ─── Wikipedia Polling ──────────────────────────────────────────────────────────

_WIKIPEDIA_CANDIDATE_ALIASES = {
    "karen bass": "Karen Bass",
    "bass": "Karen Bass",
    "nithya raman": "Nithya Raman",
    "raman": "Nithya Raman",
    "spencer pratt": "Spencer Pratt",
    "pratt": "Spencer Pratt",
    "rae huang": "Rae Huang",
    "huang": "Rae Huang",
    "adam miller": "Adam Miller",
    "miller": "Adam Miller",
}


def _normalize_candidate_name(raw_name):
    """Map a raw candidate name to canonical form using aliases."""
    normalized = (raw_name or "").strip().lower()
    return _WIKIPEDIA_CANDIDATE_ALIASES.get(normalized, raw_name.strip())


def _filter_6pct(candidates_dict):
    """Return dict with candidates ≤6% removed."""
    return {
        name: pct
        for name, pct in candidates_dict.items()
        if float(pct) > SIX_PCT_THRESHOLD
    }


def _parse_wiki_poll_table_row(row_text):
    """Extract candidate name and poll percentage from a Wikipedia table row.

    Wikipedia polls use bold candidate names ('''text''') and poll numbers
    in table cells. This parses the raw text to find candidate/pct pairs.
    """
    # Bold candidate names in Wikipedia wikitext: '''Name'''
    bold_matches = re.findall(r"'''([^']+)'''", row_text)
    if not bold_matches:
        return None, None

    candidate_raw = bold_matches[0].strip()
    candidate = _normalize_candidate_name(candidate_raw)

    # Find the most recent (rightmost) poll percentage in the row
    # Polls appear as numbers like "23%" or "23.5%"
    # The last number in the row is typically the most recent poll
    pct_matches = re.findall(r"\b(\d+(?:\.\d+)?)\s*%", row_text)
    if pct_matches:
        return candidate, float(pct_matches[-1])

    return None, None


def _scrape_wiki_polls(url, candidates):
    """Fetch a Wikipedia article and parse its polling table.

    Wikipedia polls have candidate names in the TABLE HEADER row and
    percentages in subsequent DATA rows. This function handles both formats:
    1. Header-row names + data-row percentages (Wikipedia style)
    2. Same-row names + percentages (wikitext bold style)

    Args:
        url: Wikipedia article URL
        candidates: list of canonical candidate names to look for

    Returns:
        dict of {candidate_name: poll_pct} for candidates >6%, or empty dict on failure.
    """
    try:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "text/html",
                "User-Agent": "Mozilla/5.0 Arbiter/1.0 (political research bot)",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return {}

    results = {}

    # Build candidate search patterns
    candidate_lower = {c.lower() for c in candidates}
    candidate_pattern = re.compile(
        "|".join(re.escape(c.lower()) for c in candidates),
        re.IGNORECASE,
    )

    # Find all tables
    table_sections = re.findall(
        r"<table[^>]*>(.*?)</table>", html, re.DOTALL | re.IGNORECASE
    )

    for table_html in table_sections:
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL | re.IGNORECASE)
        if not rows:
            continue

        # Parse all rows: each row -> list of (raw_html, clean_text) cells
        parsed_rows = []
        for row_html in rows:
            cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row_html, re.DOTALL | re.IGNORECASE)
            parsed = []
            for cell in cells:
                clean = re.sub(r"<[^>]+>", " ", cell)
                clean = re.sub(r"\s+", " ", clean).strip()
                parsed.append(clean)
            parsed_rows.append(parsed)

        if not parsed_rows:
            continue

        # ── Strategy 1: Wikipedia header-row format ─────────────────────────────
        # Header is the first row with candidate names; data rows follow
        header_row = parsed_rows[0]
        data_rows = parsed_rows[1:]

        # Find candidate column indices from header
        candidate_col_indices = {}
        for i, cell_text in enumerate(header_row):
            cell_lower = cell_text.lower().strip()
            # Skip non-candidate header cells
            skip_terms = {
                "", "poll", "firm", "source", "date", "dates", "sample",
                "sample size", "updates", "last poll", "electoral", "margin",
                "others", "don't know", "undecided", "lead", "allied parties",
                "first candidate in list", "seats in national assembly",
                "name of party or alliance",
            }
            if cell_lower in skip_terms:
                continue
            # Skip if it's just a year or percentage
            if re.match(r"^\d{4}$", cell_lower) or re.match(r"^\d+(?:\.\d+)?\s*%$", cell_lower):
                continue
            # Check if any candidate matches this header cell
            for c in candidates:
                if c.lower() in cell_lower or cell_lower in c.lower():
                    if c not in candidate_col_indices:
                        candidate_col_indices[c] = i

        # If we found candidate columns, find the last real poll row (skip election results)
        if candidate_col_indices and data_rows:
            poll_rows = [
                row for row in data_rows
                if row and row[0].strip()  # skip empty rows; keep pollster-name rows
                and "election" not in row[0].lower()  # skip "Parl. election" rows
                and "election" not in " ".join(row).lower()  # skip rows with "election" in any cell
            ]
            last_row = poll_rows[-1] if poll_rows else data_rows[-1]  # most recent poll
            for cand, col_idx in candidate_col_indices.items():
                if col_idx < len(last_row):
                    cell_text = last_row[col_idx]
                    # Extract percentage (skip '–' dash for no result)
                    # Some Wikipedia tables store numbers without '%' symbol
                    cell_stripped = cell_text.strip()
                    if cell_stripped in ("–", "-", ""):
                        continue
                    # Try to find a percentage (with or without % symbol)
                    pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%?", cell_stripped)
                    if not pct_match:
                        continue
                    pct_str = pct_match.group(1)
                    pct = float(pct_str)
                    if pct > SIX_PCT_THRESHOLD:
                            results[cand] = pct

        # ── Strategy 2: Same-row bold wikitext pattern ────────────────────────
        # Look for candidate names and percentages in the same row text
        if not results:
            for row_html in rows:
                row_text = re.sub(r"<[^>]+>", " ", row_html)
                row_text = re.sub(r"\s+", " ", row_text).strip()
                if not row_text:
                    continue
                match = candidate_pattern.search(row_text)
                if not match:
                    continue
                pct_match = re.search(r"\b(\d+(?:\.\d+)?)\s*%\s*$", row_text)
                if not pct_match:
                    continue
                pct = float(pct_match.group(1))
                # Find which candidate matched
                for c in candidates:
                    if c.lower() in row_text.lower():
                        if c not in results or pct > results[c]:
                            results[c] = pct

    return _filter_6pct(results)


class WikipediaPoller:
    """Poll Wikipedia for election polling data when other sources are unavailable.

    Wikipedia coverage priority:
      - LA Mayor → 2026 Los Angeles mayoral election
      - Armenia parliamentary → 2026 Armenian parliamentary election
      - Colombia presidential → 2026 Colombian presidential election

    Candidates ≤6% are excluded from the returned dict.
    Returns empty dict on failure (no page, no table, no match).
    """

    def __init__(self):
        self._cache = {}

    def poll(self, race_title, event_date, candidates):
        """Fetch Wikipedia polling for the given race.

        Args:
            race_title: Title of the race (e.g. "Los Angeles Mayoral Primary")
            event_date: Election date string (e.g. "2026-06-02")
            candidates: list of candidate names to look for

        Returns:
            dict of {candidate_name: poll_pct} (candidates >6% only), or {} on failure.
        """
        cache_key = (race_title, tuple(sorted(candidates)))
        if cache_key in self._cache:
            return self._cache[cache_key]

        url = _wikipedia_url(race_title, event_date)
        if not url:
            return {}

        candidates_clean = [c.strip() for c in candidates if c.strip()]

        polls = _scrape_wiki_polls(url, candidates_clean)
        self._cache[cache_key] = polls
        return polls

    def poll_with_meta(self, race_title, event_date, candidates):
        """Like poll() but returns (polls_dict, metadata_dict)."""
        polls = self.poll(race_title, event_date, candidates)
        url = _wikipedia_url(race_title, event_date)
        meta = {
            "source_label": "Wikipedia polling",
            "source_url": url or "unknown",
            "poll_date": None,
            "pollster": None,
            "as_of_date": datetime.now().strftime("%Y-%m-%d"),
            "data_quality": "sparse" if polls else "no_polls",
        }
        return polls, meta


# ─── Ballotpedia Polling ───────────────────────────────────────────────────────


class BallotpediaPoller:
    """Fetch polling data from Ballotpedia via web_extract.

    Ballotpedia pages are structured and scrapeable:
      - https://ballotpedia.org/2026_United_States_Senate_elections — Senate overview
      - https://ballotpedia.org/2026_United_States_House_of_Representatives_elections — House
      - https://ballotpedia.org/2026_gubernatorial_elections — Governor overview
      - Specific race: https://ballotpedia.org/{state}_Senate_election,_2026

    Candidates ≤6% are excluded from returned dict.
    Returns empty dict on failure.
    """

    BASE_URL = "https://ballotpedia.org"

    # Overview page URL templates by race type
    OVERVIEW_URLS = {
        "senate": "https://ballotpedia.org/2026_United_States_Senate_elections",
        "house": "https://ballotpedia.org/2026_United_States_House_of_Representatives_elections",
        "governor": "https://ballotpedia.org/2026_gubernatorial_elections",
    }

    # State name to Ballotpedia URL slug mapping
    STATE_SLUGS = {
        "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
        "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
        "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
        "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
        "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
        "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
        "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
        "NH": "New_Hampshire", "NJ": "New_Jersey", "NM": "New_Mexico", "NY": "New_York",
        "NC": "North_Carolina", "ND": "North_Dakota", "OH": "Ohio", "OK": "Oklahoma",
        "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode_Island", "SC": "South_Carolina",
        "SD": "South_Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
        "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West_Virginia",
        "WI": "Wisconsin", "WY": "Wyoming",
    }

    def __init__(self):
        self._cache = {}

    def _race_url(self, state, race_type):
        """Build the specific race page URL."""
        state_name = self.STATE_SLUGS.get(state.upper())
        if not state_name:
            return None
        if race_type == "senate":
            return f"{self.BASE_URL}/{state_name}_Senate_election,_2026"
        if race_type == "house":
            # House races use district notation
            return f"{self.BASE_URL}/{state_name}_House_election,_2026"
        if race_type == "governor":
            return f"{self.BASE_URL}/{state_name}_gubernatorial_election,_2026"
        return None

    def poll(self, race_title, state, race_type):
        """Fetch polling for a specific race.

        Args:
            race_title: e.g. "California Senate 2026"
            state: two-letter state code, e.g. "CA"
            race_type: "senate", "house", or "governor"

        Returns:
            dict of {candidate_name: poll_pct}, or {} on failure.
        """
        cache_key = (race_title, state.upper(), race_type)
        if cache_key in self._cache:
            return self._cache[cache_key]

        results = {}

        # 1. Try race-specific page first
        race_url = self._race_url(state, race_type)
        if race_url:
            results = self._fetch_and_parse(race_url)

        # 2. Fall back to overview page
        if not results:
            overview_url = self.OVERVIEW_URLS.get(race_type)
            if overview_url:
                results = self._fetch_and_parse(overview_url)

        # Filter candidates ≤6%
        results = _filter_6pct(results)
        self._cache[cache_key] = results
        return results

    def _fetch_and_parse(self, url):
        """Fetch a Ballotpedia URL via urllib and parse polling data.

        Uses standard library only — works in subprocess/cron context.
        Ballotpedia pages are static HTML server-side rendered.
        Ballotpedia uses '''bold''' wikitext for candidate names.

        Falls back to plain HTML table parsing for Wikipedia-style articles
        that use <th>/<td> cells instead of wikitext bold.
        """
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "Accept": "text/html",
                    "User-Agent": "Mozilla/5.0 Arbiter/1.0 (political research bot)",
                },
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="replace")
        except Exception:
            return {}

        results = {}

        # Strategy 1: Ballotpedia-style wikitext parsing ('''bold''' names)
        results = self._parse_ballotpedia_wikitext(html)
        if results:
            return results

        # Strategy 2: Wikipedia-style HTML table parsing (<th>/<td> cells)
        results = self._parse_html_table(html)
        return results

    def _parse_ballotpedia_wikitext(self, html):
        """Parse bold candidate names and percentages from wikitext HTML."""
        # Strip HTML tags to get visible text
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()

        rows = text.split("\n")
        current_candidate = None
        results = {}
        for row in rows:
            row = row.strip()
            if not row:
                continue
            # Check for bold candidate name pattern
            bold_in_row = re.findall(r"'''([^']+)'''", row)
            if bold_in_row:
                current_candidate = bold_in_row[0].strip()
            # Look for percentage in this row
            if current_candidate:
                pcts_in_row = re.findall(r"\b(\d+(?:\.\d+)?)\s*%", row)
                if pcts_in_row:
                    pct = float(pcts_in_row[-1])  # rightmost = most recent
                    results[current_candidate] = pct
                    current_candidate = None

        # Fallback: simple bold+pct association
        if not results:
            bold_matches = re.findall(r"'''([^']+)'''", text)
            pct_matches = re.findall(r"\b(\d+(?:\.\d+)?)\s*%", text)
            if bold_matches and pct_matches:
                for name in bold_matches[:len(pct_matches)]:
                    name = name.strip()
                    if name and len(name) > 1:
                        try:
                            results[name] = float(pct_matches.pop(0))
                        except (ValueError, IndexError):
                            pass
        return results

    def _parse_html_table(self, html):
        """Parse polling data from Wikipedia-style HTML tables with <th>/<td> cells.

        Looks for table rows where the first cell is a pollster/firm name and
        subsequent cells contain candidate percentages.
        """
        tables = re.findall(r"<table[^>]*>(.*?)</table>", html, re.DOTALL | re.IGNORECASE)
        results = {}
        for table_html in tables:
            rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL | re.IGNORECASE)

            # Identify header row to get candidate column indices
            header_cells = []
            for row in rows[:2]:  # Check first 2 rows for header
                cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.DOTALL | re.IGNORECASE)
                if cells:
                    clean_cells = []
                    for cell in cells:
                        cell_text = re.sub(r"<[^>]+>", " ", cell)
                        cell_text = re.sub(r"\s+", " ", cell_text).strip()
                        clean_cells.append(cell_text)
                    header_cells = clean_cells
                    break

            # Find candidate column indices (skip pollster, dates, sample size)
            candidate_cols = []
            for i, cell in enumerate(header_cells):
                cell_lower = cell.lower().strip()
                # Skip non-candidate columns
                if cell_lower in ("", "poll", "firm", "source", "dates", "date", "sample", "sample size",
                                  "updates", "last poll", "electoral", "margin", "others",
                                  "don't know", "undecided", "lead"):
                    continue
                # Skip if cell is just a year or percentage
                if re.match(r"^\d{4}$", cell.strip()) or re.match(r"^\d+(?:\.\d+)?\s*%$", cell.strip()):
                    continue
                candidate_cols.append(i)

            if not candidate_cols:
                continue

            # Parse data rows
            for row in rows:
                cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.DOTALL | re.IGNORECASE)
                if len(cells) < 2:
                    continue

                # Get candidate values from their columns
                row_results = {}
                for col_idx in candidate_cols:
                    if col_idx < len(cells):
                        cell = cells[col_idx]
                        cell_text = re.sub(r"<[^>]+>", " ", cell)
                        cell_text = re.sub(r"\s+", " ", cell_text).strip()
                        # Check if this cell contains a percentage
                        pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", cell_text)
                        if pct_match:
                            pct = float(pct_match.group(1))
                            # Get candidate name from header
                            if col_idx < len(header_cells):
                                name = header_cells[col_idx].strip()
                                if name and len(name) > 1:
                                    row_results[name] = pct

                # If we found candidate values, take the last (most recent) row's values
                if row_results and not results:
                    results = row_results

        return results


class RaceToTheWHPoller:
    """Fetch polling averages from RaceToTheWH via web search.

    Uses web_search as the primary method (works in subprocess/cron context).
    Browser automation (browser_navigate + browser_snapshot) is available as
    a future enhancement when engine.py runs in an agent context with MCP tools.

    RaceToTheWH pages:
      - https://racetothewh.com/senate/{state} — Senate race
      - https://racetothewh.com/house/{state} — House race
      - https://racetothewh.com/governor/{state} — Governor race

    Candidates ≤6% are excluded from returned dict.
    Returns empty dict on failure.
    """

    BASE_URL = "https://racetothewh.com"

    RACE_TYPE_PATHS = {
        "senate": "senate",
        "house": "house",
        "governor": "governor",
    }

    def __init__(self):
        self._cache = {}

    def _race_url(self, state, race_type):
        """Build the specific race page URL."""
        path = self.RACE_TYPE_PATHS.get(race_type)
        if not path:
            return None
        return f"{self.BASE_URL}/{path}/{state.lower()}"

    def poll(self, race_title, state, race_type):
        """Fetch polling for a specific race via web search.

        Args:
            race_title: e.g. "Texas Senate 2026"
            state: two-letter state code
            race_type: "senate", "house", or "governor"

        Returns:
            dict of {candidate_name: poll_pct}, or {} on failure.
        """
        cache_key = (race_title, state.upper(), race_type)
        if cache_key in self._cache:
            return self._cache[cache_key]

        results = {}

        # Method 1: Try web_search for the race page
        search_url = self._race_url(state, race_type)
        if search_url:
            results = self._search_polls(race_title, search_url)

        # Method 2: Try direct web_search for the state race
        if not results:
            search_query = f"{state} {race_type} 2026 polling {race_title} site:racetothewh.com"
            results = self._search_polls(race_title, search_query)

        # Filter candidates ≤6%
        results = _filter_6pct(results)
        self._cache[cache_key] = results
        return results

    def _search_polls(self, race_title, url_or_query):
        """Fetch polling data. url_or_query can be a URL or a search query.

        Uses urllib for direct URL fetching (subprocess-safe).
        For search queries, uses DuckDuckGo HTML endpoint (no API key needed).
        """
        try:
            if url_or_query.startswith("http"):
                return self._fetch_url(url_or_query)
            else:
                # Search query → try DuckDuckGo HTML
                return self._search_duckduckgo(url_or_query)
        except Exception:
            return {}

    def _fetch_url(self, url):
        """Fetch a URL directly via urllib and parse polling data."""
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "Accept": "text/html",
                    "User-Agent": "Mozilla/5.0 Arbiter/1.0 (political research bot)",
                },
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            return self._parse_content(html)
        except Exception:
            return {}

    def _search_duckduckgo(self, query):
        """Search via DuckDuckGo HTML and extract racetothewh.com results."""
        try:
            search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            req = urllib.request.Request(
                search_url,
                headers={
                    "Accept": "text/html",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                },
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            # Extract racetothewh.com URLs from search results
            urls = re.findall(r'href="(https://racetothewh\.com[^"]+)"', html)
            for url in urls[:3]:  # Try up to 3 results
                result = self._fetch_url(url)
                if result:
                    return result
        except Exception:
            pass
        return {}

    def _parse_content(self, content):
        """Parse candidate + percentage pairs from page content.

        RaceToTheWH shows polling data with candidate names and percentages.
        Pattern: "Candidate Name  52%" or "Candidate Name — 52%"
        """
        if not content:
            return {}

        results = {}
        text = str(content)

        # Pattern: Title Case name followed by NN% or NN.N%
        # Examples: "Karen Bass  42%", "John Smith  —  38%"
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Find percentage at end of candidate info
            pct_match = re.search(r"\b(\d+(?:\.\d+)?)\s*%\s*$", line)
            if not pct_match:
                continue
            pct = float(pct_match.group(1))
            # Remove the percentage from line to isolate candidate name
            name_part = re.sub(r"\b(\d+(?:\.\d+)?)\s*%\s*$", "", line).strip()
            # Clean up separators
            name_part = re.sub(r"\s*[—–\-:]\s*$", "", name_part).strip()
            if name_part and 1 < len(name_part) < 50:
                results[name_part] = pct

        return results


def _build_wiki_sources(url, poll_date=None):
    """Build sources list entry for a Wikipedia poll."""
    return {
        "label": f"Wikipedia polling" + (f" ({poll_date})" if poll_date else ""),
        "url": url,
    }


def _extract_candidate_id(market):
    """Extract FEC candidate ID from market data."""
    for key in ("candidate_id", "fec_candidate_id"):
        candidate_id = market.get(key)
        if isinstance(candidate_id, str):
            clean = candidate_id.strip().upper()
            if re.match(r"^[HSP]\d{5,8}$", clean):
                return clean

    for key in ("ticker", "title", "race_title"):
        raw = market.get(key)
        if not raw:
            continue
        match = re.search(r"\b([HSP]\d{5,8})\b", str(raw).upper())
        if match:
            return match.group(1)

    return None


def _extract_state_from_ticker(ticker):
    """Extract two-letter state code from a ticker string.

    Examples:
        KXSEN-TX-26 → TX
        KXSENCA-26 → CA
        KXGOV-TX-26 → TX
        KXGOVTX-26 → TX
        KXMAYORLA-26 → LA
        KXHOU-26 → None (House generic - no state)
    """
    if not ticker:
        return None
    t = ticker.upper()

    # House generic: no state to extract (KXHOU is House generic, not KXHOU + state)
    if re.match(r"KXHOU$", t):
        return None

    # Senate: KXSEN followed by 2-letter state code (may have intervening chars)
    # e.g. KXSEN-TX, KXSENCA (KXSE + N + CA), KXSEN-TX-26
    sen_match = re.search(r"KXSE[A-Z]*([A-Z]{2})(?:-\d+)?$", t)
    if sen_match:
        return sen_match.group(1)

    # Governor: KXGOV followed by 2-letter state code
    # e.g. KXGOVTX, KXGOV-TX
    gov_match = re.search(r"KXGOV[A-Z]*([A-Z]{2})(?:-\d+)?$", t)
    if gov_match:
        return gov_match.group(1)

    # Mayor: KXMAYOR followed by 2-letter state code
    # e.g. KXMAYORLA
    mayor_match = re.search(r"KXMAYOR[A-Z]*([A-Z]{2})(?:-\d+)?$", t)
    if mayor_match:
        return mayor_match.group(1)

    # Generic pattern: 2 letters before dash-digit (e.g. TX-26, CA-26)
    # Only match if it's clearly a state code pattern (not just any 2 letters)
    generic_match = re.search(r"([A-Z]{2})-\d", t)
    if generic_match:
        state = generic_match.group(1)
        # Only return if the 2-letter code looks like a known US state
        known_states = {"AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
                        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
                        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
                        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
                        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"}
        if state in known_states:
            return state

    return None


def _search_fec_candidate_by_name(name, state=None):
    """Search OpenFEC for a candidate by name, return candidate_id or None."""
    if not name:
        return None

    fec_client = OpenFECClient()
    params = {
        "api_key": OPENFEC_KEY,
        "q": name,
        "per_page": 10,
    }
    if state:
        params["state"] = state.upper()
    payload = fec_client._get("/candidate/search", params)
    if not isinstance(payload, dict):
        return None
    results = payload.get("results", [])
    if results and isinstance(results, list):
        # Return first match with a valid FEC ID
        for r in results:
            cid = r.get("candidate_id")
            if cid and re.match(r"^[HPS]\d{5,8}$", str(cid)):
                return cid
    return None


def _attach_financials(market, fec_client):
    m_type = _market_type_race(market.get("ticker"), market.get("series_ticker"))
    if m_type in ("approval", "generic", "international"):
        market["financials"] = {
            "note": "No US FEC data for this race type",
            "source": "OpenFEC",
            "url": OPENFEC_BASE,
        }
        market["sources"] = _append_source(market.get("sources"), _openfec_source())
        return

    candidate_id = _extract_candidate_id(market)
    if not candidate_id:
        # Try FEC name search
        candidate_name = (market.get("candidate_name") or "").strip()
        if candidate_name:
            state = _extract_state_from_ticker(market.get("ticker") or "")
            candidate_id = _search_fec_candidate_by_name(candidate_name, state)

    if not candidate_id:
        market["financials"] = {"note": "Could not find FEC candidate ID", "source": "OpenFEC"}
        market["sources"] = _append_source(market.get("sources"), _openfec_source())
        return

    financials = fec_client.fetch_candidate_financials(candidate_id)
    if not financials:
        market["financials"] = {"error": "OpenFEC fetch failed", "source": "OpenFEC"}
    else:
        market["financials"] = financials
    market["sources"] = _append_source(market.get("sources"), _openfec_source())


class WikipediaFederalPolls:
    """Fetch national generic ballot data from Wikipedia's Senate/House overview pages.

    Wikipedia's 2026 Senate overview page (2026_United_States_Senate_elections) contains
    a table of national generic ballot polling averages. This is the most reliable
    publicly available signal for the national political environment heading into the midterms.

    Parses the "Average" row in the polling table to extract the Democratic margin.

    Cached at class level — fetched once per pipeline run.
    """

    SENATE_URL = "https://en.wikipedia.org/wiki/2026_United_States_Senate_elections"
    HOUSE_URL = "https://en.wikipedia.org/wiki/2026_United_States_House_of_Representatives_elections"

    # Class-level cache: {url: (lean_float, source_label, date)}
    _cache = {}

    def get_generic_ballot_lean(self):
        """Return the national generic ballot Democratic margin, or None on failure.

        Returns:
            float: Democratic margin in points (positive = D leads), or None
        """
        for url, label in [(self.SENATE_URL, "2026 Senate overview"), (self.HOUSE_URL, "2026 House overview")]:
            if url in self._cache:
                cached = self._cache[url]
                if cached is not None:
                    print(f"  Wikipedia generic ballot: D+{cached[0]:.1f} (cached from {label})")
                    return cached[0]

            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "Accept": "text/html",
                        "User-Agent": "Mozilla/5.0 Arbiter/1.0 (political research bot)",
                    },
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    html = resp.read().decode("utf-8", errors="replace")

                lean = self._parse_generic_ballot(html)
                if lean is not None:
                    self._cache[url] = (lean, label, datetime.now().strftime("%Y-%m-%d"))
                    print(f"  Wikipedia generic ballot: D+{lean:.1f} from {label}")
                    return lean
                else:
                    self._cache[url] = None
            except Exception as e:
                print(f"  Wikipedia generic ballot fetch failed for {label}: {e}")
                self._cache[url] = None

        return None

    def _parse_generic_ballot(self, html):
        """Parse the generic ballot average from Wikipedia Senate/House overview HTML.

        The polling table has an 'Average' row with columns:
        Source | Dates | Updated | Republicans | Democrats | Other | Margin

        We look for the 'Average' row and extract the Margin column (e.g., "Democrats +6.3%")
        """
        tables = re.findall(r"<table[^>]*>(.*?)</table>", html, re.DOTALL | re.IGNORECASE)
        for table_html in tables:
            rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL | re.IGNORECASE)
            for row in rows:
                # Clean the row text
                row_text = re.sub(r"<[^>]+>", " ", row)
                row_text = re.sub(r"\s+", " ", row_text).strip()

                # Look for the Average row with a Margin column
                if row_text.lower().startswith("average"):
                    # Extract the margin value
                    # Format: "Average ... Democrats +6.3%" or "Democrats +6.3%"
                    margin_match = re.search(r"Democrats\s*\+?(-?\d+(?:\.\d+)?)\s*%", row_text, re.IGNORECASE)
                    if margin_match:
                        return float(margin_match.group(1))

                    # Try Republican margin
                    margin_match = re.search(r"Republicans\s*\+?(-?\d+(?:\.\d+)?)\s*%", row_text, re.IGNORECASE)
                    if margin_match:
                        return -float(margin_match.group(1))

                    # Try generic "Margin" field
                    margin_match = re.search(r"Margin\s+[Dd]emocrats?\s+\+?(-?\d+(?:\.\d+)?)\s*%", row_text)
                    if margin_match:
                        return float(margin_match.group(1))

        return None


def _fundamentals_fv(market, generic_ballot_lean=None):
    """Estimate FV from structural/fundamental factors when no polling is available.

    Args:
        market: market dict
        generic_ballot_lean: Democratic margin on generic ballot (positive = D lean)

    Returns:
        (fv_cents, analysis_text, confidence)
    """
    ticker = market.get("ticker", "")
    m_type = _market_type_race(ticker, market.get("series_ticker"))

    # Incumbency: federal incumbents get +8c baseline advantage
    incumbent_bonus = 0
    if m_type in ("senate", "house", "governor"):
        title = (market.get("title") or "").lower()
        if "incumbent" in title or "inc" in title:
            incumbent_bonus = 8

    # National environment adjustment
    env_adjustment = 0
    if generic_ballot_lean is not None:
        # Generic ballot lean: each point D lean → +1c for D candidates
        # This is a directional signal only
        env_adjustment = int(generic_ballot_lean * 0.5)  # half-weight

    base_fv = 50 + incumbent_bonus + env_adjustment
    base_fv = max(5, min(95, base_fv))  # clamp

    confidence = "low" if (not incumbent_bonus and not env_adjustment) else "medium"

    analysis = (
        f"No live polling is available for this race. "
        f"Fundamentals-based estimate is {base_fv}¢ using incumbency ({incumbent_bonus:+d}) "
        f"and national environment adjustment ({env_adjustment:+d}). "
        f"Confidence is {confidence} — this estimate should be treated as a directional placeholder."
    )
    return base_fv, analysis, confidence


def run():
    state = read_state()
    pending = get_pending(state)
    if not pending:
        print("No pending markets. Engine exiting.")
        return 0

    client = VoteHubClient()
    fec_client = OpenFECClient()

    # Fetch national generic ballot environment signal once (for federal race fundamentals)
    wikipedia_federal = WikipediaFederalPolls()
    generic_ballot_lean = wikipedia_federal.get_generic_ballot_lean()

    completed = 0

    # Group mayor markets by event_ticker so we process the full race at once
    mayor_pending = [m for m in pending if _market_type(m.get("ticker")) == "mayor"]
    other_pending = [m for m in pending if _market_type(m.get("ticker")) != "mayor"]

    # Process mayor races — group pending markets, but analyze against every contract
    # in that race so one new/pending candidate cannot be evaluated in isolation.
    mayor_by_race = {}
    for m in mayor_pending:
        race_key = m.get("event_ticker") or m.get("race_key") or m.get("series_ticker") or m.get("ticker")
        if race_key not in mayor_by_race:
            mayor_by_race[race_key] = []
        mayor_by_race[race_key].append(m)

    for race_key, pending_race_markets in mayor_by_race.items():
        race_markets = [
            m for m in state.get("markets", [])
            if _market_type(m.get("ticker")) == "mayor"
            and (m.get("event_ticker") or m.get("race_key") or m.get("series_ticker") or m.get("ticker")) == race_key
        ]
        if not race_markets:
            race_markets = pending_race_markets

        # Transition pending members to analyzing; complete members remain complete
        for market in pending_race_markets:
            ticker = market.get("ticker")
            if market.get("status") == "discovered":
                transition(state, ticker, "analyzing")
        write_state(state)

        # Analyze the full race
        race_fv, context, analysis, sources, forecast_by_ticker = _analyze_mayor_race(
            race_markets[0],
            race_markets,
        )

        # Finalize every market in the race so the group has one coherent analysis
        for market in race_markets:
            ticker = market.get("ticker")
            fv = race_fv.get(ticker, 5)
            forecast = forecast_by_ticker.get(ticker)
            candidate_name = (market.get("candidate_name") or ticker or "this candidate").strip()
            forecast_note = _forecast_summary_text(
                forecast,
                label=f"Top-two forecast for {candidate_name}",
            )
            _finalize_market(
                market,
                fv,
                context,
                analysis,
                sources,
                forecast=forecast,
                forecast_note=forecast_note,
            )
            market["race_key"] = race_key  # used by generator to group
            _attach_financials(market, fec_client)
            if market.get("status") == "analyzing":
                transition(state, ticker, "complete")
            elif market.get("status") == "discovered":
                transition(state, ticker, "analyzing")
                transition(state, ticker, "complete")
            else:
                market["status"] = "complete"
            write_state(state)
            completed += 1
            print(f"Completed {ticker}: {market.get('verdict')} (FV {fv}¢)")

    # Process non-mayor markets (approval, generic, senate, house, governor, international) one at a time
    for market in other_pending:
        ticker = market.get("ticker")
        if market.get("status") == "discovered":
            transition(state, ticker, "analyzing")
            write_state(state)

        m_type = _market_type_race(ticker, market.get("series_ticker"))

        # ── Approval / Generic: VoteHub ─────────────────────────────────────
        if m_type in ("approval", "generic"):
            polls = client.fetch_recent(m_type)
            if polls is None:
                price = market.get("market_price")
                if price is None:
                    price = 50
                context = (
                    "VoteHub polling fetch failed for this market type during this run. "
                    "The market is still completed so the daily pipeline can proceed without blocking."
                )
                analysis = (
                    "With polling data unavailable, Marcus uses market price as provisional fair value and "
                    "does not claim an edge."
                )
                source_url = APPROVAL_URL if m_type == "approval" else GENERIC_URL
                sources = [{"label": "VoteHub endpoint", "url": source_url}]
                _finalize_market(market, price, context, analysis, sources)
            elif m_type == "approval":
                fv, context, analysis, sources, forecast = _analyze_approval_market(market, polls)
                _finalize_market(market, fv, context, analysis, sources, forecast=forecast)
            else:
                fv, context, analysis, sources, forecast = _analyze_generic_market(market, polls)
                _finalize_market(market, fv, context, analysis, sources, forecast=forecast)

            _attach_financials(market, fec_client)
            transition(state, ticker, "complete")
            write_state(state)
            completed += 1
            print(f"Completed {ticker}: {market.get('verdict')} (FV {market.get('marcus_fv')}¢)")
            continue

        # ── Senate / House / Governor: Ballotpedia → RaceToTheWH → Wikipedia → Fundamentals ──
        if m_type in ("senate", "house", "governor"):
            race_title = market.get("race_title") or market.get("title") or ""
            event_date = market.get("event_date") or market.get("election_date")
            state_abbr = _extract_state_from_ticker(ticker)
            candidates = [(market.get("candidate_name") or "").strip()]
            if not candidates or not candidates[0]:
                title = market.get("title", "")
                candidates = []

            # Priority 1: Ballotpedia
            bp = BallotpediaPoller()
            bp_polls = bp.poll(race_title, state_abbr, m_type) if state_abbr else {}

            if bp_polls:
                # Use Ballotpedia polling
                poll_values = list(bp_polls.values())
                avg_poll = sum(poll_values) / len(poll_values)
                price = market.get("market_price")
                fv = int(round(min(avg_poll * 2.0, 95))) if price is not None else 50
                delta = fv - int(price) if price is not None else 0
                context = (
                    f"Ballotpedia polling for {race_title} shows: "
                    + ", ".join(f"{k}: {v}%" for k, v in bp_polls.items())
                )
                analysis = (
                    f"Marcus uses Ballotpedia polling data to set fair value at {fv}¢ "
                    f"for this market. "
                    f"{'The market price is ' + str(price) + '¢, giving an edge of ' + str(delta) + '¢.' if price is not None else ''}"
                    f"Candidates polling ≤6% are excluded from analysis."
                )
                sources = [{"label": "Ballotpedia polling", "url": bp.BASE_URL}]
                _finalize_market(market, fv, context, analysis, sources)
            else:
                # Priority 2: RaceToTheWH
                rtwh = RaceToTheWHPoller()
                rtwh_polls = rtwh.poll(race_title, state_abbr, m_type) if state_abbr else {}

                if rtwh_polls:
                    poll_values = list(rtwh_polls.values())
                    avg_poll = sum(poll_values) / len(poll_values)
                    price = market.get("market_price")
                    fv = int(round(min(avg_poll * 2.0, 95))) if price is not None else 50
                    delta = fv - int(price) if price is not None else 0
                    context = (
                        f"RaceToTheWH polling averages for {race_title} show: "
                        + ", ".join(f"{k}: {v}%" for k, v in rtwh_polls.items())
                    )
                    analysis = (
                        f"Marcus uses RaceToTheWH polling averages to set fair value at {fv}¢ "
                        f"for this market. "
                        f"{'The market price is ' + str(price) + '¢, giving an edge of ' + str(delta) + '¢.' if price is not None else ''}"
                        f"Candidates polling ≤6% are excluded from analysis."
                    )
                    sources = [{"label": "RaceToTheWH", "url": rtwh.BASE_URL}]
                    _finalize_market(market, fv, context, analysis, sources)
                else:
                    # Priority 3: Wikipedia fallback
                    wiki = WikipediaPoller()
                    wiki_polls, wiki_meta = wiki.poll_with_meta(race_title, event_date, candidates)

                    if wiki_polls:
                        poll_values = list(wiki_polls.values())
                        avg_poll = sum(poll_values) / len(poll_values)
                        price = market.get("market_price")
                        fv = int(round(min(avg_poll * 2.0, 95))) if price is not None else 50
                        delta = fv - int(price) if price is not None else 0
                        market["_wiki_polls"] = wiki_polls
                        context = (
                            f"Wikipedia polling for {race_title} shows: "
                            + ", ".join(f"{k}: {v}%" for k, v in wiki_polls.items())
                        )
                        analysis = (
                            f"Marcus uses Wikipedia polling data to set fair value at {fv}¢ "
                            f"for this market. "
                            f"{'The market price is ' + str(price) + '¢, giving an edge of ' + str(delta) + '¢.' if price is not None else ''}"
                            f"Candidates polling ≤6% are excluded from analysis."
                        )
                        sources = [_build_wiki_sources(wiki_meta["source_url"])]
                        _finalize_market(market, fv, context, analysis, sources)
                    else:
                        # Priority 4: Fundamentals as last resort
                        # Check if this is a multicandidate race — if so, skip rather than
                        # assigning the same FV to every candidate (misleading for primaries)
                        race_key = market.get("event_ticker") or market.get("series_ticker") or ticker
                        same_race = [
                            m for m in state.get("markets", [])
                            if (m.get("event_ticker") or m.get("series_ticker") or m.get("ticker", "")) == race_key
                        ]
                        is_multicandidate = len(same_race) > 1
                        if is_multicandidate:
                            # Can't produce meaningful per-candidate FV without polling — skip
                            market["_poll_failed"] = True
                            print(f"Skipped {ticker}: multicandidate race with no polling, cannot assign uniform FV")
                            _attach_financials(market, fec_client)
                            transition(state, ticker, "complete")
                            write_state(state)
                            completed += 1
                            continue

                        fv, analysis, confidence = _fundamentals_fv(market, generic_ballot_lean)
                        if confidence != "low":
                            # We had some structural info — use it
                            price = market.get("market_price")
                            delta = fv - int(price) if price is not None else 0
                            context = "Fundamentals-based estimate — no live polling available."
                            sources = [{"label": "Fundamentals model", "url": None}]
                            _finalize_market(market, fv, context, analysis, sources)
                            market["_fundamentals_used"] = True
                        else:
                            # True no-data state — skip the card entirely
                            market["_poll_failed"] = True
                            print(f"Skipped {ticker}: all polling sources failed, no fundamentals signal")
                            _attach_financials(market, fec_client)
                            transition(state, ticker, "complete")
                            write_state(state)
                            completed += 1
                            continue  # don't re-attach financials or transition again

            _attach_financials(market, fec_client)
            transition(state, ticker, "complete")
            write_state(state)
            completed += 1
            print(f"Completed {ticker}: {market.get('verdict')} (FV {market.get('marcus_fv')}¢)")
            continue

        # ── International / Other: Wikipedia polling → market price fallback ──
        # Try Wikipedia polling for international/unsupported races
        wiki = WikipediaPoller()
        race_title = market.get("race_title") or market.get("title") or ""
        event_date = market.get("event_date") or market.get("election_date")
        candidates = [
            (market.get("candidate_name") or "").strip(),
        ]
        if not candidates or not candidates[0]:
            title = market.get("title", "")
            candidates = []

        wiki_polls, wiki_meta = wiki.poll_with_meta(race_title, event_date, candidates)

        if wiki_polls:
            # Wikipedia has polling — compute FV from poll percentages
            price = market.get("market_price")
            poll_values = list(wiki_polls.values())
            if poll_values:
                avg_poll = sum(poll_values) / len(poll_values)
                fv = int(round(min(avg_poll * 2.0, 95)))  # rough heuristic
                if price is not None:
                    delta = fv - int(price)
                else:
                    delta = 0
                market["_wiki_polls"] = wiki_polls  # store for reference

                context = (
                    f"Wikipedia polling for {race_title} shows: "
                    + ", ".join(f"{k}: {v}%" for k, v in wiki_polls.items())
                )
                analysis = (
                    f"Marcus uses Wikipedia polling data to set fair value at {fv}¢ "
                    f"for this market. "
                    f"{'The market price is ' + str(price) + '¢, giving an edge of ' + str(delta) + '¢.' if price is not None else ''}"
                    f"Candidates polling ≤6% are excluded from analysis."
                )
                sources = [_build_wiki_sources(wiki_meta["source_url"])]
                _finalize_market(market, fv, context, analysis, sources)
            else:
                # Wikipedia found but no usable polls — use fundamentals
                fv, analysis, confidence = _fundamentals_fv(market)
                price = market.get("market_price")
                if price is not None:
                    delta = fv - int(price)
                else:
                    delta = 0
                context = (
                    f"Wikipedia article for {race_title} was found but contained no "
                    f"extractable polling data for the candidates in this market."
                )
                sources = [_build_wiki_sources(_wikipedia_url(race_title, event_date) or "https://en.wikipedia.org/")]
                _finalize_market(market, fv, context, analysis, sources)
                market["_fundamentals_used"] = True
        else:
            # No Wikipedia polling — try fundamentals (pass national generic ballot lean if available)
            fv, analysis, confidence = _fundamentals_fv(market, generic_ballot_lean)
            price = market.get("market_price")
            url = _wikipedia_url(race_title, event_date)
            if price is None:
                price = 50
            if confidence != "low":
                context = "Fundamentals-based estimate — no live polling available."
                sources = [{"label": "Fundamentals model", "url": url}]
                _finalize_market(market, fv, context, analysis, sources)
                market["_fundamentals_used"] = True
            else:
                # True no-data state for international — use market price, mark complete but note
                context = (
                    "This market is not yet mapped to a polling feed in the current engine configuration. "
                    "Arbiter still completes the brief to keep state continuity and track coverage gaps."
                )
                analysis = (
                    "Because no polling source is available for this contract type, Marcus sets fair value "
                    "equal to current market price and marks the verdict as PASS."
                )
                wiki_url = url or "local://engine.py"
                sources = [{"label": "Arbiter engine note", "url": wiki_url}]
                _finalize_market(market, price, context, analysis, sources)
                market["_poll_failed"] = True

        _attach_financials(market, fec_client)

        transition(state, ticker, "complete")
        write_state(state)
        completed += 1
        print(f"Completed {ticker}: {market.get('verdict')} (FV {market.get('marcus_fv')}¢)")

    print("Engine complete. Processed {} markets.".format(completed))
    return completed


if __name__ == "__main__":
    run()
