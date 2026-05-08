"""Arbiter Engine — polling analysis and fair value estimation."""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from state import get_pending, read_state, transition, write_state

APPROVAL_URL = (
    "https://api.votehub.com/polls?poll_type=approval&subject=donald-trump&from_date=2026-04-01"
)
GENERIC_URL = "https://api.votehub.com/polls?poll_type=generic-ballot&subject=2026"
REQUEST_DELAY = 0.5
OPENFEC_BASE = "https://api.open.fec.gov/v1"
OPENFEC_KEY = "DEMO_KEY"
OPENFEC_REQUEST_DELAY = 0.5


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


def _market_type(ticker):
    t = (ticker or "").upper()
    if "KXAPRPOTUS" in t:
        return "approval"
    if "GENERICBALLOT" in t or "VOTEHUB" in t:
        return "generic"
    if "KXMAYOR" in t:
        return "mayor"
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


# LA Mayor 2026 race data — hardcoded from public polling
# Poll average from racetothewh.com and UCLA Luskin (April 2026)
LA_MAYOR_POLLS = {
    "Karen Bass":      23,   # incumbent, avg of UCLA/Berkeley/Emerson
    "Nithya Raman":    13,   # city councilmember
    "Spencer Pratt":   12,   # reality TV / conservative
    "Rae Huang":        5,   # housing advocate
    "Adam Miller":      5,   # tech executive
    # remaining candidates: low single digits, treat as 1%
    "Other":           42,  # includes undecided + <1% candidates
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
        f"LA Mayor race polling (Race to the WH average, April 2026) shows Karen Bass leading "
        f"at {candidate_polls.get('Karen Bass', '?')}%, followed by Nithya Raman ({candidate_polls.get('Nithya Raman', '?')}%) "
        f"and Spencer Pratt ({candidate_polls.get('Spencer Pratt', '?')}%). "
        f"{round(candidate_polls.get('Other', 0))}% of voters remain undecided. "
        f"The primary is {LA_MAYOR_ELECTION_DATE} — {n_candidates} candidate contracts active. "
        f"Fundraising: Bass ${LA_MAYOR_FUNDRAISING.get('Karen Bass', '?')}M, Miller ${LA_MAYOR_FUNDRAISING.get('Adam Miller', '?')}M."
    )
    analysis = (
        f"Marcus evaluates the full race field. Leading candidate {leading_name} (FV {leading_fv}¢) "
        f"is still below majority support, so the model treats this as a volatile top-two/runoff race rather than a clean incumbent lock. "
        f"Contracts with large poll-to-price gaps represent edge. "
        f"Note: {round(candidate_polls.get('Other', 0))}% undecided/other voters make this race volatile — a runoff is likely (top two vote-getters advance to November)."
    )
    sources = [
        {"label": "Race to the WH — LA Mayor polling", "url": LA_MAYOR_SOURCE_URL},
        {"label": "UCLA Luskin Poll (March 2026)", "url": "https://luskin.ucla.edu/volatility-ahead-in-la-mayors-race-ucla-luskin-poll-finds-40-of-voters-undecided"},
    ]
    return race_fv, context, analysis, sources


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


def _extract_candidate_id(market):
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


def _attach_financials(market, fec_client):
    m_type = _market_type(market.get("ticker"))
    if m_type in ("approval", "generic"):
        market["financials"] = {
            "note": "National-level market — no candidate-specific financials",
            "source": "OpenFEC",
            "url": OPENFEC_BASE,
        }
        market["sources"] = _append_source(market.get("sources"), _openfec_source())
        return

    candidate_id = _extract_candidate_id(market)
    if not candidate_id:
        market["financials"] = {"error": "OpenFEC fetch failed", "source": "OpenFEC"}
        market["sources"] = _append_source(market.get("sources"), _openfec_source())
        return

    financials = fec_client.fetch_candidate_financials(candidate_id)
    if not financials:
        market["financials"] = {"error": "OpenFEC fetch failed", "source": "OpenFEC"}
    else:
        market["financials"] = financials
    market["sources"] = _append_source(market.get("sources"), _openfec_source())


def run():
    state = read_state()
    pending = get_pending(state)
    if not pending:
        print("No pending markets. Engine exiting.")
        return 0

    client = VoteHubClient()
    fec_client = OpenFECClient()
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
        race_fv, context, analysis, sources = _analyze_mayor_race(race_markets[0], race_markets)

        # Finalize every market in the race so the group has one coherent analysis
        for market in race_markets:
            ticker = market.get("ticker")
            fv = race_fv.get(ticker, 5)
            _finalize_market(market, fv, context, analysis, sources)
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

    # Process non-mayor markets (approval, generic, other) one at a time
    for market in other_pending:
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

        _attach_financials(market, fec_client)

        transition(state, ticker, "complete")
        write_state(state)
        completed += 1
        print(f"Completed {ticker}: {market.get('verdict')} (FV {market.get('marcus_fv')}¢)")

    print("Engine complete. Processed {} markets.".format(completed))
    return completed


if __name__ == "__main__":
    run()
