"""State management for Arbiter.

Single source of truth: state/analysis.json
All scripts (collector, engine, generator) read/write through this module.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

STATE_FILE = Path(__file__).parent / "state" / "analysis.json"

# State machine: valid transitions
TRANSITIONS = {
    "discovered": {"analyzing"},
    "analyzing": {"complete"},
    "complete": {"stale"},
    "stale": {"analyzing"},
}


def _empty_state():
    return {"last_run": None, "markets": []}


def read_state():
    """Load state from disk. Returns empty structure if file missing or corrupt."""
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
        if "markets" not in data:
            data["markets"] = []
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        return _empty_state()


def write_state(data):
    """Write state to disk. Atomic-ish — writes full file each time."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def upsert_market(state, market):
    """Add or update a market by ticker.

    New markets enter as 'discovered' with null analysis fields.
    Existing markets are updated (preserves any analysis already done).
    """
    ticker = market["ticker"]
    for i, m in enumerate(state["markets"]):
        if m["ticker"] == ticker:
            # Update only fields present in the incoming market
            for key, value in market.items():
                if value is not None:
                    state["markets"][i][key] = value
            return state["markets"][i]

    # New market — set defaults
    entry = {
        "ticker": ticker,
        "title": market.get("title"),
        "race_title": market.get("race_title"),
        "candidate_name": market.get("candidate_name"),
        "event_ticker": market.get("event_ticker"),
        "election_date": market.get("election_date"),
        "series_ticker": market.get("series_ticker"),
        "status": "discovered",
        "market_price": market.get("market_price"),
        "marcus_fv": None,
        "delta": None,
        "verdict": None,
        "context": None,
        "analysis": None,
        "sources": [],
        "financials": None,
        "no_market_reason": None,
    }
    state["markets"].append(entry)
    return entry


def get_pending(state):
    """Return markets with status 'discovered' or 'analyzing'."""
    return [m for m in state["markets"] if m["status"] in ("discovered", "analyzing")]


def get_complete(state):
    """Return markets with status 'complete', sorted by absolute delta descending."""
    complete = [m for m in state["markets"] if m["status"] == "complete"]
    return sorted(complete, key=lambda m: abs(m.get("delta") or 0), reverse=True)


def transition(state, ticker, new_status):
    """Move a market to a new status. Raises ValueError on invalid transition."""
    for m in state["markets"]:
        if m["ticker"] == ticker:
            current = m["status"]
            if new_status not in TRANSITIONS.get(current, set()):
                raise ValueError(
                    f"Invalid transition: {current} -> {new_status} for {ticker}"
                )
            m["status"] = new_status
            return m
    raise KeyError(f"Market not found: {ticker}")


def touch_last_run(state):
    """Update last_run timestamp to now (Eastern-equivalent UTC)."""
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    return state
