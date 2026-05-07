#!/usr/bin/env python3
"""
Polling Evidence Collector for Arbiter.

Fetches current polling data from Silver Bulletin and RealClearPolling for
upcoming US elections (30-60 day window), structures it into the PollingEvidence
format, and writes to data/polling_evidence/current.json.

Run before the daily arbiter report:
    python3 scripts/collect_polling_evidence.py

Sources prioritized:
  1. Silver Bulletin (natesilver.net)  — quality-weighted averages, pollster grades
  2. RealClearPolling (realclearpolling.com) — broadest raw poll coverage
  3. 270toWin — race context and state-level averages

Election window: next 30-60 days from today.
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# ─── Config ───────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "data" / "polling_evidence" / "current.json"

SILVER_BULLETIN_BASE = "https://www.natesilver.net"
RCP_BASE = "https://www.realclearpolling.com"
TWO70_BASE = "https://www.270towin.com"

REQUEST_TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ─── Election calendar (updated for 2026 cycle) ──────────────────────────────

# Races with Kalshi relevance, sorted by date.
# Each entry: (date_str, race_key, market_key, race_name, market_type)
# market_type: binary-general | multi-candidate-primary | chamber-control

UPCOMING_RACES = [
    # May 16 – Louisiana primaries
    ("2026-05-16", "la-senate-primary", "KXLA-SENATE-26MAY16", "Louisiana Senate Primary", "multi-candidate-primary"),
    ("2026-05-16", "la-governor-primary", "KXLA-GOV-26MAY16", "Louisiana Governor Primary", "multi-candidate-primary"),

    # May 19 – largest primary day (6 states)
    ("2026-05-19", "ga-senate-general", "KXGA-SENATE-26", "Georgia Senate General", "binary-general"),
    ("2026-05-19", "ga-governor-general", "KXGA-GOV-26", "Georgia Governor General", "binary-general"),
    ("2026-05-19", "pa-senate-general", "KXPA-SENATE-26", "Pennsylvania Senate General", "binary-general"),
    ("2026-05-19", "al-senate-general", "KXAL-SENATE-26", "Alabama Senate General", "binary-general"),
    ("2026-05-19", "al-governor-general", "KXAL-GOV-26", "Alabama Governor General", "binary-general"),
    ("2026-05-19", "ky-governor-general", "KXKY-GOV-26", "Kentucky Governor General", "binary-general"),
    ("2026-05-19", "or-senate-general", "KXOR-SENATE-26", "Oregon Senate General", "binary-general"),

    # May 26 – Texas Senate runoff
    ("2026-05-26", "tx-senate-runoff", "KXTX-SENATE-RUNOFF-26", "Texas Senate GOP Runoff", "binary-general"),

    # June 2 – multi-state
    ("2026-06-02", "ca-senate-primary", "KXCA-SENATE-26JUN02", "California Senate Primary", "multi-candidate-primary"),
    ("2026-06-02", "nj-governor-general", "KXNJ-GOV-26", "New Jersey Governor General", "binary-general"),
    ("2026-06-02", "nj-senate-general", "KXNJ-SENATE-26", "New Jersey Senate General", "binary-general"),
    ("2026-06-02", "nm-governor-general", "KXNM-GOV-26", "New Mexico Governor General", "binary-general"),
    ("2026-06-02", "mt-senate-general", "KXMT-SENATE-26", "Montana Senate General", "binary-general"),
    ("2026-06-02", "ia-senate-general", "KXIA-SENATE-26", "Iowa Senate General", "binary-general"),

    # June 9
    ("2026-06-09", "nv-senate-general", "KXNV-SENATE-26", "Nevada Senate General", "binary-general"),
    ("2026-06-09", "sc-governor-general", "KXSC-GOV-26", "South Carolina Governor General", "binary-general"),

    # June 16 – runoffs
    ("2026-06-16", "ga-senate-runoff", "KXGA-SENATE-RUNOFF-26", "Georgia Senate Runoff", "binary-general"),
    ("2026-06-16", "ga-governor-runoff", "KXGA-GOV-RUNOFF-26", "Georgia Governor Runoff", "binary-general"),
    ("2026-06-16", "al-senate-runoff", "KXAL-SENATE-RUNOFF-26", "Alabama Senate Runoff", "binary-general"),
    ("2026-06-16", "al-governor-runoff", "KXAL-GOV-RUNOFF-26", "Alabama Governor Runoff", "binary-general"),

    # June 23
    ("2026-06-23", "ny-governor-general", "KXNY-GOV-26", "New York Governor General", "binary-general"),
    ("2026-06-23", "md-governor-general", "KXMD-GOV-26", "Maryland Governor General", "binary-general"),

    # June 27 – Louisiana runoff
    ("2026-06-27", "la-senate-runoff", "KXLA-SENATE-RUNOFF-26", "Louisiana Senate Runoff", "binary-general"),
    ("2026-06-27", "la-governor-runoff", "KXLA-GOV-RUNOFF-26", "Louisiana Governor Runoff", "binary-general"),

    # July 21
    ("2026-07-21", "az-senate-primary", "KXAZ-SENATE-26JUL21", "Arizona Senate Primary", "multi-candidate-primary"),
]


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def fetch(url: str, retries: int = 2) -> str | None:
    """Fetch a URL and return the response body, or None on failure."""
    headers = {"User-Agent": USER_AGENT}
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (URLError, HTTPError, TimeoutError) as exc:
            if attempt < retries:
                time.sleep(1.5 ** attempt)
            else:
                print(f"[WARN] fetch failed for {url}: {exc}", file=sys.stderr)
                return None
    return None


# ─── Polling data fetchers ───────────────────────────────────────────────────

def fetch_silver_bulletin_generic() -> dict | None:
    """Fetch Silver Bulletin generic ballot and presidential approval averages."""
    url = f"{SILVER_BULLETIN_BASE}/p/generic-ballot-average-2026-nate-silver-bulletin-congress-polls"
    html = fetch(url)
    if not html:
        return None

    result = {"generic_ballot": None, "presidential_approval": None, "source_url": url}

    # Parse generic ballot numbers from page text
    # Silver Bulletin shows Dem vs Rep percentages in a table
    dem_match = re.search(r'Dem.*?(\d+\.?\d*)\s*%', html[:50000])
    rep_match = re.search(r'Rep.*?(\d+\.?\d*)\s*%', html[:50000])
    if dem_match and rep_match:
        dem_pct = float(dem_match.group(1))
        rep_pct = float(rep_match.group(1))
        spread = dem_pct - rep_pct
        result["generic_ballot"] = {
            "dem_pct": dem_pct,
            "rep_pct": rep_pct,
            "spread": spread,
            "leader": "Democrats" if spread > 0 else "Republicans",
            "fair_yes_cents": min(100, max(0, 50 + spread * 4)) if abs(spread) > 1 else 50,
        }

    # Presidential approval
    url_approval = f"{SILVER_BULLETIN_BASE}/p/will-donald-trump-approve-2026"
    html_approval = fetch(url_approval)
    if html_approval:
        approve_match = re.search(r'approve.*?(\d+\.?\d*)\s*%', html_approval[:30000], re.IGNORECASE)
        disapprove_match = re.search(r'disapprove.*?(\d+\.?\d*)\s*%', html_approval[:30000], re.IGNORECASE)
        if approve_match and disapprove_match:
            approve = float(approve_match.group(1))
            disapprove = float(disapprove_match.group(1))
            result["presidential_approval"] = {
                "approve": approve,
                "disapprove": disapprove,
                "net": approve - disapprove,
            }

    return result


def fetch_rcp_state_polls(race_slug: str, state: str, race_name: str) -> dict | None:
    """
    Fetch state-level polling from RealClearPolling.
    race_slug: URL slug like 'senate/general/2026/{state}'
    """
    url = f"{RCP_BASE}/polls/{race_slug}/{state}"
    html = fetch(url)
    if not html:
        # Try generic poll list page
        url_fallback = f"{RCP_BASE}/polls/{race_slug}/{state}"
        html = fetch(url_fallback)

    if not html:
        return None

    result = {
        "source_url": url,
        "race_name": race_name,
        "polls": [],
    }

    # Parse polls from RCP table — pattern: Pollster name, dates, sample, D%, R%, margin
    # Example: "YouGov  May 5-7  1,000 LV  47%  43%  +4"
    poll_pattern = re.compile(
        r'<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*'
        r'<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>',
        re.DOTALL,
    )
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    for row in rows[:15]:  # last 15 polls
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(cells) >= 5:
            pollster_raw = re.sub(r'<[^>]+>', '', cells[0]).strip()
            dates_raw = re.sub(r'<[^>]+>', '', cells[1]).strip()
            sample_raw = re.sub(r'<[^>]+>', '', cells[2]).strip()
            d_pct = re.sub(r'<[^>]+>', '', cells[3]).strip()
            r_pct = re.sub(r'<[^>]+>', '', cells[4]).strip()

            if d_pct and r_pct and '%' in d_pct and '%' in r_pct:
                try:
                    d_val = float(re.search(r'[\d.]+', d_pct).group())
                    r_val = float(re.search(r'[\d.]+', r_pct).group())
                    spread = d_val - r_val

                    # Parse dates
                    date_parts = re.findall(r'\d+', dates_raw)
                    if len(date_parts) >= 4:
                        start = f"2026-{date_parts[-4]:0>2}-{date_parts[-3]:0>2}"
                        end = f"2026-{date_parts[-2]:0>2}-{date_parts[-1]:0>2}"
                    else:
                        start = end = "2026-05-01"

                    result["polls"].append({
                        "pollster": pollster_raw[:40],
                        "dates": {"start": start, "end": end},
                        "sample": sample_raw[:30],
                        "toplines": [
                            {"candidate": "Democrat", "pct": d_val},
                            {"candidate": "Republican", "pct": r_val},
                        ],
                        "spread": f"D+{spread:.0f}" if spread > 0 else f"R+{abs(spread):.0f}",
                    })
                except (ValueError, IndexError):
                    continue

    return result if result["polls"] else None


def fetch_270towin_average(state: str, race_type: str) -> dict | None:
    """Fetch state polling average from 270toWin."""
    # race_type: 'senate', 'governor', 'president'
    url = f"{TWO70_BASE}/2026-{race_type}-election-polls/{state}"
    html = fetch(url)
    if not html:
        return None

    result = {"source_url": url, "average": None}

    # Try to extract polling average
    avg_match = re.search(r'(\d+\.?\d*)\s*%.*?vs.*?(\d+\.?\d*)\s*%', html[:20000])
    if avg_match:
        leader_pct = float(avg_match.group(1))
        runner_pct = float(avg_match.group(2))
        result["average"] = {
            "leader_pct": leader_pct,
            "runner_pct": runner_pct,
            "spread": leader_pct - runner_pct,
        }

    return result


# ─── PollingEvidence builder ──────────────────────────────────────────────────

def build_generic_ballot_evidence(data: dict, collected_at: str) -> dict:
    """Build PollingEvidence for generic congressional ballot."""
    gb = data.get("generic_ballot")
    if not gb:
        return None

    spread = gb["spread"]
    leader = "Democrats" if spread > 0 else "Republicans"
    runner = "Republicans" if leader == "Democrats" else "Democrats"

    # Build fair_yes_cents
    # If Dem lead of X points → Dem Senate control more likely
    # Use 4x multiplier: a 5-pt lead → ~70c fair
    fair_yes = min(100, max(0, 50 + spread * 4))

    return {
        "collected_at": collected_at,
        "source_url": data.get("source_url") or "https://www.natesilver.net",
        "race": "Generic Congressional Ballot 2026",
        "market_key": "generic-ballot",
        "market_type": "chamber-control",
        "polling_average": {
            "updated_at": collected_at,
            "leader": leader,
            "leader_share": gb["dem_pct"] if leader == "Democrats" else gb["rep_pct"],
            "runner_up": runner,
            "runner_up_share": gb["rep_pct"] if leader == "Democrats" else gb["dem_pct"],
            "spread": round(spread, 1),
            "fair_yes_cents": round(fair_yes),
        },
        "latest_polls": [],
        "trend_summary": (
            f"{leader} lead the generic ballot by {abs(spread):.1f}pts "
            f"({gb['dem_pct']:.0f}% D / {gb['rep_pct']:.0f}% R). "
            "Polling has been stable with Dems holding a modest lead."
        ),
        "evidence_links": [
            {
                "label": "Silver Bulletin Generic Ballot Average",
                "href": "https://www.natesilver.net/p/generic-ballot-average-2026-nate-silver-bulletin-congress-polls",
                "source": "Silver Bulletin",
                "note": "Quality-weighted polling average with house-effect adjustments.",
            },
            {
                "label": "RealClearPolitics Generic Ballot",
                "href": "https://www.realclearpolling.com/polls/generic-ballot",
                "source": "RealClearPolling",
                "note": "Simple average of all major generic ballot polls.",
            },
        ],
    }


def build_presidential_approval_evidence(data: dict, collected_at: str) -> dict | None:
    """Build PollingEvidence for presidential approval."""
    pa = data.get("presidential_approval")
    if not pa:
        return None

    net = pa["net"]
    leader = "Approve" if net > 0 else "Disapprove"

    return {
        "collected_at": collected_at,
        "source_url": "https://www.natesilver.net",
        "race": "Presidential Approval Rating",
        "market_key": "presidential-approval",
        "market_type": "binary-general",
        "polling_average": {
            "updated_at": collected_at,
            "leader": leader,
            "leader_share": pa["approve"],
            "runner_up": "Disapprove" if leader == "Approve" else "Approve",
            "runner_up_share": pa["disapprove"],
            "spread": abs(net),
            "fair_yes_cents": min(100, max(0, 50 + net * 2)),
        },
        "latest_polls": [],
        "trend_summary": (
            f"Trump approval: {pa['approve']:.0f}% approve / {pa['disapprove']:.0f}% disapprove "
            f"(net {net:+.0f}). Slightly underwater."
        ),
        "evidence_links": [
            {
                "label": "Silver Bulletin Presidential Approval",
                "href": "https://www.natesilver.net/p/will-donald-trump-approve-2026",
                "source": "Silver Bulletin",
                "note": "Aggregated approval rating with quality adjustment.",
            },
            {
                "label": "RealClearPolitics Approval",
                "href": "https://www.realclearpolling.com/polls/presidential/approval",
                "source": "RealClearPolling",
                "note": "Broad polling average across all major pollsters.",
            },
        ],
    }


def build_state_race_evidence(
    race_key: str,
    market_key: str,
    market_type: str,
    race_name: str,
    rcp_data: dict | None,
    two70_data: dict | None,
    collected_at: str,
) -> dict:
    """Build PollingEvidence for a single state race."""

    polls = rcp_data.get("polls", []) if rcp_data else []
    avg = (two70_data or {}).get("average") or (rcp_data.get("polls", [{}])[0] if polls else {})

    # Determine leader/runner-up from latest poll
    if polls:
        latest = polls[0]
        toplines = latest.get("toplines", [])
        if len(toplines) >= 2:
            leader_name = toplines[0]["candidate"]
            leader_pct = toplines[0]["pct"]
            runner_name = toplines[1]["candidate"]
            runner_pct = toplines[1]["pct"]
        else:
            leader_name = "Leader"
            leader_pct = 50
            runner_name = "Trailer"
            runner_pct = 50
    else:
        leader_name = "TBD"
        leader_pct = 50
        runner_name = "TBD"
        runner_pct = 50

    spread = leader_pct - runner_pct

    # Determine market type and fair_yes
    if market_type == "multi-candidate-primary":
        # For primaries, leader's share is key
        fair_yes = min(90, max(10, 30 + leader_pct * 0.8))
        type_label = "multi-candidate-primary"
    else:
        # Binary general: spread → fair_yes
        fair_yes = min(100, max(0, 50 + spread * 4))
        type_label = "binary-general"

    # Build trend summary
    if polls:
        pollsters_seen = [p["pollster"] for p in polls[:3]]
        trend = (
            f"Latest polls show {leader_name} at {leader_pct:.0f}% vs {runner_name} at {runner_pct:.0f} "
            f"({latest.get('spread', 'N/A')}, {latest.get('dates', {}).get('end', 'recent')}). "
            f"Recent pollsters: {', '.join(set(pollsters_seen))}."
        )
    else:
        trend = "No recent polling data available for this race. Market price is the best available signal."

    # Evidence links
    evidence_links = []
    if rcp_data and rcp_data.get("source_url"):
        evidence_links.append({
            "label": f"RCP {race_name} Polls",
            "href": rcp_data["source_url"],
            "source": "RealClearPolling",
            "note": f"Latest RCP-tracked polls for {race_name}.",
        })
    if two70_data and two70_data.get("source_url"):
        evidence_links.append({
            "label": f"270toWin {state_from_key(race_key)} {race_type_from_key(race_key).title()} Polls",
            "href": two70_data["source_url"],
            "source": "270toWin",
            "note": f"State polling average and history from 270toWin.",
        })
    evidence_links.append({
        "label": "Silver Bulletin Pollster Ratings",
        "href": "https://www.natesilver.net/p/pollster-ratings-silver-bulletin",
        "source": "Silver Bulletin",
        "note": "Pollster quality grades inform how much weight to give each poll.",
    })

    return {
        "collected_at": collected_at,
        "source_url": (rcp_data or {}).get("source_url") or "https://www.realclearpolling.com",
        "race": race_name,
        "market_key": market_key,
        "market_type": type_label,
        "polling_average": {
            "updated_at": collected_at,
            "leader": leader_name,
            "leader_share": leader_pct,
            "runner_up": runner_name,
            "runner_up_share": runner_pct,
            "spread": round(spread, 1),
            "fair_yes_cents": round(fair_yes),
        },
        "latest_polls": [
            {
                "pollster": p["pollster"],
                "dates": p["dates"],
                "sample": p["sample"],
                "toplines": p["toplines"],
                "spread": p["spread"],
            }
            for p in (polls[:5] if polls else [])
        ],
        "trend_summary": trend,
        "evidence_links": evidence_links,
    }


def state_from_key(race_key: str) -> str:
    """Extract state abbreviation from race key."""
    parts = race_key.split("-")
    return parts[0].upper() if parts else "XX"


def race_type_from_key(race_key: str) -> str:
    """Extract race type from race key."""
    if "governor" in race_key:
        return "governor"
    elif "senate" in race_key:
        return "senate"
    elif "president" in race_key:
        return "president"
    return "election"


def rcp_race_slug(race_key: str) -> str:
    """Build RCP URL slug for a given race key."""
    state = state_from_key(race_key).lower()
    rtype = race_type_from_key(race_key)
    if rtype == "governor":
        return f"governor/general/2026/{state}"
    elif rtype == "senate":
        if "primary" in race_key or "runoff" in race_key:
            return f"senate/republican-primary/2026/{state}"
        return f"senate/general/2026/{state}"
    return f"{rtype}/general/2026/{state}"


# ─── Main collection ──────────────────────────────────────────────────────────

def collect_polling_evidence(
    output_path: Path,
    verbose: bool = False,
) -> dict:
    """
    Main entry point. Fetches polling data from all sources and writes
    the PollingEvidence JSON file.
    """
    collected_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    today = datetime.utcnow().date()
    lookahead = today + timedelta(days=60)
    cutoff = today + timedelta(days=30)

    evidence: list[dict] = []
    errors: list[str] = []

    if verbose:
        print(f"[INFO] Collecting polling evidence at {collected_at}")
        print(f"[INFO] Targeting races with election dates {cutoff} to {lookahead}")

    # 1. Fetch Silver Bulletin top-line data
    print("[INFO] Fetching Silver Bulletin averages...", file=sys.stderr)
    sb_data = fetch_silver_bulletin_generic()
    if sb_data:
        # Generic ballot
        gb_evidence = build_generic_ballot_evidence(sb_data, collected_at)
        if gb_evidence:
            evidence.append(gb_evidence)

        # Presidential approval
        pa_evidence = build_presidential_approval_evidence(sb_data, collected_at)
        if pa_evidence:
            evidence.append(pa_evidence)
    else:
        errors.append("Silver Bulletin fetch failed")

    # 2. Fetch state-level polling for upcoming races
    for (election_date_str, race_key, market_key, race_name, market_type) in UPCOMING_RACES:
        try:
            election_date = datetime.strptime(election_date_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        # Only collect for races in the 30-60 day window
        if not (cutoff <= election_date <= lookahead):
            continue

        if verbose:
            print(f"[INFO] Fetching {race_name} ({election_date_str})...", file=sys.stderr)

        slug = rcp_race_slug(race_key)
        state = state_from_key(race_key).lower()
        rtype = race_type_from_key(race_key)

        rcp_data = fetch_rcp_state_polls(slug, state, race_name)
        two70_data = fetch_270towin_average(state, rtype)

        race_evidence = build_state_race_evidence(
            race_key=race_key,
            market_key=market_key,
            market_type=market_type,
            race_name=race_name,
            rcp_data=rcp_data,
            two70_data=two70_data,
            collected_at=collected_at,
        )
        evidence.append(race_evidence)

        # Rate limit
        time.sleep(0.5)

    # 3. Assemble output
    output = {"evidence": evidence}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"[INFO] Wrote {len(evidence)} evidence records to {output_path}", file=sys.stderr)
    for err in errors:
        print(f"[WARN] {err}", file=sys.stderr)

    return output


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Collect polling evidence for Arbiter.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    result = collect_polling_evidence(args.output, verbose=args.verbose)
    count = len(result.get("evidence", []))
    print(json.dumps({"ok": True, "records": count, "output": str(args.output)}))


if __name__ == "__main__":
    main()
