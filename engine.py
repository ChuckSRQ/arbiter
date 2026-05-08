"""Arbiter Engine — polling analysis and fair value estimation."""

import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from state import get_pending, read_state, transition, write_state

APPROVAL_URL = (
    "https://api.votehub.com/polls?poll_type=approval&subject=donald-trump&from_date=2026-04-01"
)
GENERIC_URL = "https://api.votehub.com/polls?poll_type=generic-ballot&subject=2026"
REQUEST_DELAY = 0.5


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


def _market_type(ticker):
    t = (ticker or "").upper()
    if "KXAPRPOTUS" in t:
        return "approval"
    if "GENERICBALLOT" in t or "VOTEHUB" in t:
        return "generic"
    return "other"


def _finalize_market(market, marcus_fv, context, analysis, sources):
    price = market.get("market_price")
    if price is None:
        price = 50
    delta = int(round(float(marcus_fv) - float(price)))
    market["marcus_fv"] = int(round(float(marcus_fv)))
    market["delta"] = delta
    market["verdict"] = "TRADE" if abs(delta) >= 5 else "PASS"
    market["context"] = context
    market["analysis"] = analysis
    market["sources"] = sources


def _build_insufficient_note(polls_found):
    if polls_found < 2:
        return " Data quality note: fewer than two polls were available, so confidence is lower."
    return ""


def _analyze_approval_market(market, polls):
    condition = _parse_market_condition(market.get("title"))
    approve_values = []
    disapprove_values = []
    for poll in polls:
        approve = _extract_metric(poll, ("approve", "approval", "approve_pct", "approval_pct"))
        disapprove = _extract_metric(
            poll, ("disapprove", "disapproval", "disapprove_pct", "disapproval_pct")
        )
        if approve is not None:
            approve_values.append(approve)
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
    return fv, context, analysis, sources


def _analyze_generic_market(market, polls):
    condition = _parse_market_condition(market.get("title"))
    dem_values = []
    rep_values = []
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
    return fv, context, analysis, sources


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


def run():
    state = read_state()
    pending = get_pending(state)
    if not pending:
        print("No pending markets. Engine exiting.")
        return 0

    client = VoteHubClient()
    completed = 0

    for market in pending:
        ticker = market.get("ticker")
        if market.get("status") == "discovered":
            transition(state, ticker, "analyzing")
            write_state(state)

        m_type = _market_type(ticker)

        if m_type == "other":
            price = market.get("market_price")
            if price is None:
                price = 50
            context = (
                "This market is not yet mapped to a polling feed in the current engine configuration. "
                "Arbiter still completes the brief to keep state continuity and track coverage gaps."
            )
            analysis = (
                "Because no polling source is implemented for this contract type, Marcus sets fair value "
                "equal to current market price and marks the verdict as PASS. polling source not yet implemented."
            )
            sources = [{"label": "Arbiter engine note", "url": "local://engine.py"}]
            _finalize_market(market, price, context, analysis, sources)
        else:
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
                    "does not claim an edge. polling data unavailable."
                )
                source_url = APPROVAL_URL if m_type == "approval" else GENERIC_URL
                sources = [{"label": "VoteHub endpoint", "url": source_url}]
                _finalize_market(market, price, context, analysis, sources)
            elif m_type == "approval":
                fv, context, analysis, sources = _analyze_approval_market(market, polls)
                _finalize_market(market, fv, context, analysis, sources)
            else:
                fv, context, analysis, sources = _analyze_generic_market(market, polls)
                _finalize_market(market, fv, context, analysis, sources)

        transition(state, ticker, "complete")
        write_state(state)
        completed += 1
        print(f"Completed {ticker}: {market.get('verdict')} (FV {market.get('marcus_fv')}¢)")

    print("Engine complete. Processed {} markets.".format(completed))
    return completed


if __name__ == "__main__":
    run()
