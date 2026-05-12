"""Arbiter Generator — renders HTML report from complete market state."""

from datetime import datetime
from html import escape
from pathlib import Path

from state import get_complete, read_state

OUTPUT_FILE = Path(__file__).parent / "output" / "index.html"


def get_complete_markets(state):
    """Return complete markets, excluding those where polling failed.

    Skips any market marked with _poll_failed=True so placeholder cards
    are never rendered.
    """
    complete = get_complete(state)
    return [m for m in complete if not m.get("_poll_failed")]


def _header_date(dt):
    return f"{dt.strftime('%A, %B')} {dt.day}, {dt.year}"


def _card_date(value):
    if not value:
        return "Unknown date"
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            return escape(text)
    return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"


def _display_date(market):
    return market.get("event_date") or market.get("election_date")


def _cents(value):
    if value is None:
        return "—"
    try:
        return f"{int(round(float(value)))}c"
    except (TypeError, ValueError):
        return "—"


def _delta_text(value):
    try:
        delta = int(round(float(value)))
    except (TypeError, ValueError):
        delta = 0
    if delta > 0:
        return f"+{delta}"
    return str(delta)


def _verdict(delta):
    return "TRADE" if delta >= 5 else "PASS"


def _source_anchor(source):
    if isinstance(source, dict):
        label = source.get("label") or source.get("url") or "Source"
        url = source.get("url") or "#"
    else:
        value = str(source or "").strip()
        label = value or "Source"
        url = value if value.startswith(("http://", "https://")) else "#"
    return (
        f'<a class="source-link" href="{escape(str(url), quote=True)}" '
        f'target="_blank" rel="noopener noreferrer">{escape(str(label))}</a>'
    )


def _humanize_forecast_text(value):
    text = str(value or "").strip().replace("_", " ")
    return text or None


def _forecast_probability_text(value):
    try:
        return f"{int(round(float(value) * 100.0))}%"
    except (TypeError, ValueError):
        return "—"


def _forecast_band_text(forecast):
    if not isinstance(forecast, dict):
        return "—"
    low = _forecast_probability_text(forecast.get("p25"))
    high = _forecast_probability_text(forecast.get("p75"))
    if low == "—" or high == "—":
        return "—"
    return f"{low.rstrip('%')}-{high}"


def _format_dollars(value):
    """Format a dollar amount as $X.XM, $X.XK, or $0."""
    if value is None:
        return "$0"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "$0"
    if v >= 1_000_000:
        return f"${v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"${v / 1_000:.0f}K"
    return "$0"


def _render_financials_block(market):
    """Render a Finances section for a single-candidate card if FV >= 5."""
    if not market.get("financials"):
        return ""
    fv = market.get("marcus_fv")
    if fv is not None and float(fv) < 5:
        return ""
    fin = market["financials"]
    receipts = _format_dollars(fin.get("receipts"))
    cash = _format_dollars(fin.get("cash_on_hand"))
    return f"""
  <div class="finances-block">
    <div class="finances-kicker">Finances</div>
    <div class="finances-row">
      <div class="finances-stat">
        <div class="finances-label">Raised</div>
        <div class="finances-value">{receipts}</div>
      </div>
      <div class="finances-stat">
        <div class="finances-label">Cash on Hand</div>
        <div class="finances-value">{cash}</div>
      </div>
    </div>
  </div>"""


def _render_forecast_block(forecast):
    if not isinstance(forecast, dict):
        return ""

    median = _forecast_probability_text(forecast.get("p50"))
    band = _forecast_band_text(forecast)
    confidence = _humanize_forecast_text(forecast.get("confidence"))
    data_quality = _humanize_forecast_text(forecast.get("data_quality"))
    meta = []
    if confidence:
        meta.append(f"{confidence.capitalize()} confidence")
    if data_quality:
        meta.append(data_quality.capitalize())
    meta_html = " · ".join(escape(item) for item in meta) if meta else "No quality label"

    return f"""
  <div class="forecast-block">
    <div class="forecast-kicker">Forecast</div>
    <div class="forecast-main">{escape(median)} median</div>
    <div class="forecast-band">{escape(band)}</div>
    <div class="forecast-meta">{meta_html}</div>
  </div>"""


def _render_candidate_forecast(forecast):
    if not isinstance(forecast, dict):
        return '<div class="candidate-forecast-empty">—</div>'

    median = _forecast_probability_text(forecast.get("p50"))
    band = _forecast_band_text(forecast)
    confidence = _humanize_forecast_text(forecast.get("confidence"))
    data_quality = _humanize_forecast_text(forecast.get("data_quality"))
    meta_parts = []
    if confidence:
        meta_parts.append(confidence.capitalize())
    if data_quality:
        meta_parts.append(data_quality.capitalize())
    meta_html = " · ".join(escape(part) for part in meta_parts) if meta_parts else "No label"

    return (
        '<div class="candidate-forecast">'
        f'<div class="candidate-forecast-main">{escape(median)} median</div>'
        f'<div class="candidate-forecast-band">{escape(band)}</div>'
        f'<div class="candidate-forecast-meta">{meta_html}</div>'
        "</div>"
    )


def _render_card(market):
    try:
        delta = int(round(float(market.get("delta") or 0)))
    except (TypeError, ValueError):
        delta = 0
    verdict = market.get("verdict") or ("TRADE" if abs(delta) >= 5 else "PASS")
    verdict_class = "verdict-trade" if verdict == "TRADE" else "verdict-pass"
    delta_style = "" if abs(delta) >= 5 else ' style="color:#9CA3AF"'
    sources = market.get("sources") or []
    source_links = "\n    ".join(_source_anchor(source) for source in sources)
    if source_links:
        source_block = f'\n  <div style="margin-top:10px">\n    {source_links}\n  </div>'
    else:
        source_block = '\n  <div style="margin-top:10px"></div>'

    return f"""<div class="card">
  <div class="kalshi-badge">{escape((market.get("ticker") or "").upper())}</div>
  <div class="race-header">
    <div class="race-title">{escape(market.get("race_title") or market.get("title") or "Untitled Market")}</div>
    <div class="election-date">{_card_date(_display_date(market))}</div>
    <div class="verdict-tag {verdict_class}">{verdict}</div>
  </div>

  <div class="context">
    {escape(market.get("context") or "")}
  </div>

  <div class="price-row">
    <div class="price-box market-box">
      <div class="price-label">Market</div>
      <div class="price-value market">{_cents(market.get("market_price"))}</div>
    </div>
    <div class="delta-box">
      <div class="delta-label">Edge</div>
      <div class="delta-value"{delta_style}>{_delta_text(market.get("delta"))}</div>
    </div>
    <div class="price-box marcus-box">
      <div class="price-label">Marcus</div>
      <div class="price-value marcus">{_cents(market.get("marcus_fv"))}</div>
    </div>
  </div>{_render_forecast_block(market.get("forecast"))}

  <div class="reason-label">Analysis</div>
  <div class="reason-text">
    {escape(market.get("analysis") or "")}
  </div>
  {_render_financials_block(market)}{source_block}
</div>"""


def _group_by_race(markets):
    """Group markets by race_key for mayor races, otherwise return individual cards.

    Mayor races (those with a race_key) are grouped into a single race-level card.
    Non-mayor markets are returned one-per-group (individual card mode).
    Returns list of groups; each group is a dict:
      {'type': 'race', 'race_key': ..., 'markets': [...]} or
      {'type': 'market', 'market': ...}
    """
    groups = []
    seen_race_keys = {}

    for market in markets:
        race_key = market.get("race_key")
        if race_key:
            if race_key not in seen_race_keys:
                seen_race_keys[race_key] = {
                    "type": "race",
                    "race_key": race_key,
                    "markets": [],
                }
                groups.append(seen_race_keys[race_key])
            seen_race_keys[race_key]["markets"].append(market)
        else:
            groups.append({"type": "market", "market": market})

    return groups


def _render_race_card(race_key, markets):
    """Render a race-level card showing all candidate contracts."""
    if not markets:
        return ""

    ref = markets[0]
    context = ref.get("context") or ""
    analysis = ref.get("analysis") or ""
    sources = ref.get("sources") or []

    sorted_markets = sorted(markets, key=lambda m: m.get("market_price") or 0, reverse=True)

    rows_html = ""
    for rank, m in enumerate(sorted_markets, 1):
        ticker = m.get("ticker", "")
        title = m.get("title", "")
        candidate_name = (m.get("candidate_name") or "").strip()
        if not candidate_name:
            candidate_name = title
            for prefix in ("Will ", " win the LA mayoral election?", " win Los Angeles mayor?"):
                candidate_name = candidate_name.replace(prefix, "")
            candidate_name = candidate_name.strip()
        if not candidate_name:
            candidate_name = ticker

        price = m.get("market_price")
        delta = m.get("delta")
        fv = m.get("marcus_fv")
        verdict = m.get("verdict") or "PASS"

        price_str = f"{price}c" if price is not None else "—"
        delta_int = int(round(delta)) if delta is not None else 0
        delta_str = f"+{delta_int}" if delta_int > 0 else str(delta_int)
        fv_str = f"{fv}c" if fv is not None else "—"
        forecast_html = _render_candidate_forecast(m.get("forecast"))

        verdict_class = "verdict-trade" if verdict == "TRADE" else "verdict-pass"
        delta_style = "" if abs(delta_int) >= 5 else ' style="color:#9CA3AF"'

        fv_int = int(fv) if fv is not None else 0
        if fv_int < 5:
            finances_html = '<span style="color:#475569">—</span>'
        else:
            fin = m.get("financials")
            if fin and "error" not in fin:
                raised = _format_dollars(fin.get("receipts"))
                cash = _format_dollars(fin.get("cash_on_hand"))
                finances_html = (
                    f'<div class="candidate-finances-block">'
                    f'<div class="candidate-finances-raised">Raised: {raised}</div>'
                    f'<div class="candidate-finances-cash">Cash: {cash}</div>'
                    f'</div>'
                )
            else:
                finances_html = '<span style="color:#475569">N/A</span>'

        rows_html += f"""      <tr class="candidate-row">
        <td class="candidate-rank">{rank}</td>
        <td class="candidate-name">{escape(candidate_name)}</td>
        <td class="candidate-price">{price_str}</td>
        <td class="candidate-delta"{delta_style}>{delta_str}</td>
        <td class="candidate-fv-cell"><div class="candidate-fv">{fv_str}</div><div class="candidate-signal"><span class="verdict-tag {verdict_class} verdict-sm">{verdict}</span></div></td>
        <td class="candidate-forecast-cell">{forecast_html}</td>
        <td class="candidate-finances-cell">{finances_html}</td>
      </tr>"""

    source_links = "\n    ".join(_source_anchor(src) for src in sources)
    source_block = (
        f'\n  <div style="margin-top:10px">\n    {source_links}\n  </div>'
        if source_links
        else '\n  <div style="margin-top:10px"></div>'
    )

    display_date = _display_date(markets[0])
    date_str = _card_date(display_date) if display_date else "Election date TBD"

    top_market = sorted_markets[0] if sorted_markets else None
    if top_market:
        top_title = top_market.get("title", "")
        top_name = (top_market.get("candidate_name") or "").strip()
        if not top_name:
            top_name = top_title
            for prefix in ("Will ", " win the LA mayoral election?", " win Los Angeles mayor?"):
                top_name = top_name.replace(prefix, "")
            top_name = top_name.strip()
        if not top_name:
            top_name = top_market.get("ticker", "Unknown")
        top_price = top_market.get("market_price", 0)
        top_delta = top_market.get("delta", 0)
        leading_signal = (
            f"Leading: {top_name} at {top_price}c "
            f"({'+' if top_delta >= 0 else ''}{int(round(top_delta))} edge)"
        )
    else:
        leading_signal = ""

    return f"""<div class="card race-card">
  <div class="kalshi-badge">{escape(race_key.upper())}</div>
  <div class="race-header">
    <div class="race-title">{escape(ref.get("race_title") or ref.get("title", "Mayoral Race"))}</div>
    <div class="election-date">{date_str} &nbsp;·&nbsp; {len(markets)} candidates</div>
    <div class="leading-signal">{escape(leading_signal)}</div>
  </div>

  <div class="context">
    {escape(context)}
  </div>

  <table class="candidates-table">
    <thead>
      <tr>
        <th>#</th>
        <th>Candidate</th>
        <th>Price</th>
        <th>Edge</th>
        <th>Marcus</th>
        <th>Forecast</th>
        <th>Finances</th>
      </tr>
    </thead>
    <tbody>
{rows_html}
    </tbody>
  </table>

  <div class="reason-label">Analysis</div>
  <div class="reason-text">
    {escape(analysis)}
  </div>{source_block}
</div>"""


def _chunked(items, size):
    return [items[index : index + size] for index in range(0, len(items), size)]


def generate():
    state = read_state()
    markets = get_complete_markets(state)
    groups = _group_by_race(markets)
    today = datetime.now()

    def to_card(g):
        if g["type"] == "race":
            return _render_race_card(g["race_key"], g["markets"])
        return _render_card(g["market"])

    card_count = sum(1 for g in groups if g["type"] == "market") + len([g for g in groups if g["type"] == "race"])
    market_pages = _chunked(groups, 3)
    if not market_pages:
        market_pages = [[]]

    page_count = len(market_pages)
    tabs_html = ""
    if page_count > 1:
        tab_buttons = []
        for index in range(page_count):
            page_num = index + 1
            is_active = "true" if index == 0 else "false"
            tab_buttons.append(
                f'<button class="brief-tab{" is-active" if index == 0 else ""}" '
                f'type="button" role="tab" id="tab-page-{page_num}" '
                f'aria-controls="panel-page-{page_num}" aria-selected="{is_active}" '
                f'data-tab-target="panel-page-{page_num}">Page {page_num}</button>'
            )
        tabs_html = (
            '<div class="brief-tabs" role="tablist" aria-label="Political brief pages">\n    '
            + "\n    ".join(tab_buttons)
            + "\n  </div>"
        )

    page_blocks = []
    for index, page in enumerate(market_pages):
        page_num = index + 1
        cards_html = "\n        ".join(to_card(g) for g in page)
        if not cards_html:
            cards_html = '<div class="empty-state">No complete briefs available.</div>'
        page_blocks.append(
            f'<section class="brief-page{" is-active" if index == 0 else ""}" '
            f'id="panel-page-{page_num}" role="tabpanel" '
            f'aria-labelledby="tab-page-{page_num}"{" hidden" if index != 0 else ""}>\n'
            f'      <div class="cards-grid">\n        {cards_html}\n      </div>\n'
            f'    </section>'
        )
    pages_html = "\n    ".join(page_blocks)

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=450, height=800">
<title>Arbiter — Political Briefing</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    background: #0D0F1A;
    color: #E8E4DC;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 16px;
    overflow-y: auto;
  }}

  .report-shell {{
    max-width: 1460px;
    margin: 0 auto;
    padding: 0 12px 12px;
  }}

  .brief-tabs {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    margin: 16px 0 10px;
    flex-wrap: wrap;
  }}

  .brief-tab {{
    border: 1px solid rgba(59, 130, 246, 0.35);
    background: rgba(59, 130, 246, 0.08);
    color: #93C5FD;
    border-radius: 999px;
    padding: 5px 12px;
    font-size: 11px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    cursor: pointer;
  }}

  .brief-tab.is-active {{
    border-color: rgba(251, 191, 36, 0.5);
    background: rgba(251, 191, 36, 0.12);
    color: #FCD34D;
  }}

  .brief-page {{
    margin-top: 12px;
  }}

  .cards-grid {{
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 400px));
    gap: 18px;
    justify-content: center;
    justify-items: center;
  }}

  .card {{
    background: linear-gradient(160deg, #141828 0%, #0D0F1A 60%);
    border: 1px solid rgba(59, 130, 246, 0.18);
    border-radius: 20px;
    padding: 18px;
    width: min(100%, 400px);
    margin: 0;
  }}

  .empty-state {{
    font-size: 14px;
    color: #94A3B8;
    text-align: center;
    padding: 20px;
    border: 1px dashed rgba(59, 130, 246, 0.2);
    border-radius: 12px;
    width: min(100%, 400px);
  }}

  @media (max-width: 1260px) {{
    .cards-grid {{
      grid-template-columns: repeat(2, minmax(0, 400px));
    }}
  }}

  @media (max-width: 860px) {{
    .cards-grid {{
      grid-template-columns: minmax(0, 400px);
    }}
  }}

  .section-label {{
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.28em;
    text-transform: uppercase;
    color: #60A5FA;
    margin-bottom: 10px;
  }}

  .race-header {{
    margin-bottom: 12px;
  }}

  .race-title {{
    font-size: 22px;
    font-weight: 700;
    color: #F1F5F9;
    line-height: 1.25;
    margin-bottom: 4px;
  }}

  .election-date {{
    font-size: 13px;
    color: #60A5FA;
    font-weight: 500;
    letter-spacing: 0.04em;
  }}

  .verdict-tag {{
    display: inline-block;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    border-radius: 20px;
    padding: 3px 10px;
    margin-top: 4px;
  }}
  .verdict-trade {{
    color: #FCD34D;
    background: rgba(251, 191, 36, 0.12);
    border: 1px solid rgba(251, 191, 36, 0.35);
  }}
  .verdict-pass {{
    color: #9CA3AF;
    background: rgba(156, 163, 175, 0.12);
    border: 1px solid rgba(156, 163, 175, 0.35);
  }}

  .context {{
    font-size: 15px;
    line-height: 1.7;
    color: #CBD5E1;
    margin-bottom: 16px;
  }}

  .price-row {{
    display: flex;
    gap: 10px;
    margin-bottom: 14px;
    align-items: stretch;
  }}

  .price-box {{
    flex: 1;
    background: rgba(5, 10, 25, 0.95);
    border-radius: 12px;
    padding: 12px 10px;
    text-align: center;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    gap: 4px;
  }}

  .price-box.market-box {{
    border: 1px solid rgba(59, 130, 246, 0.55);
    box-shadow: 0 0 14px rgba(59, 130, 246, 0.12), inset 0 0 8px rgba(59, 130, 246, 0.06);
  }}

  .price-box.marcus-box {{
    border: 1px solid rgba(251, 191, 36, 0.55);
    box-shadow: 0 0 14px rgba(251, 191, 36, 0.12), inset 0 0 8px rgba(251, 191, 36, 0.06);
  }}

  .price-label {{
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: #94A3B8;
  }}

  .price-value {{
    font-size: 26px;
    font-weight: 700;
    color: #F1F5F9;
  }}

  .price-value.market {{ color: #93C5FD; }}
  .price-value.marcus {{ color: #FDE68A; }}

  .delta-box {{
    flex: 0 0 auto;
    background: rgba(5, 10, 25, 0.95);
    border: 1px solid rgba(251, 191, 36, 0.6);
    border-radius: 12px;
    padding: 14px 18px;
    text-align: center;
    align-self: center;
    box-shadow: 0 0 18px rgba(251, 191, 36, 0.18), inset 0 0 10px rgba(251, 191, 36, 0.08);
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    gap: 6px;
    min-width: 72px;
  }}

  .forecast-block {{
    background: rgba(5, 10, 25, 0.92);
    border: 1px solid rgba(59, 130, 246, 0.22);
    border-radius: 14px;
    padding: 12px 14px;
    margin: -2px 0 14px;
  }}

  .forecast-kicker {{
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: #60A5FA;
    margin-bottom: 5px;
  }}

  .forecast-main {{
    font-size: 17px;
    font-weight: 700;
    color: #FDE68A;
  }}

  .forecast-band {{
    font-size: 13px;
    color: #E2E8F0;
    margin-top: 2px;
  }}

  .forecast-meta {{
    font-size: 12px;
    color: #93C5FD;
    margin-top: 4px;
    line-height: 1.5;
  }}

  .delta-label {{
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: #FCD34D;
  }}

  .delta-value {{
    font-size: 22px;
    font-weight: 700;
    color: #FDE68A;
  }}

  .reason-label {{
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: #FCD34D;
    margin-bottom: 6px;
  }}

  .reason-text {{
    font-size: 15px;
    line-height: 1.65;
    color: #CBD5E1;
    margin-bottom: 10px;
  }}

  .source-link {{
    display: inline-block;
    font-size: 12px;
    color: #60A5FA;
    text-decoration: none;
    background: rgba(59, 130, 246, 0.08);
    border: 1px solid rgba(59, 130, 246, 0.2);
    border-radius: 6px;
    padding: 5px 12px;
    margin-right: 6px;
    margin-bottom: 4px;
  }}

  .kalshi-badge {{
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: rgba(59, 130, 246, 0.1);
    border: 1px solid rgba(59, 130, 246, 0.2);
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 11px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #93C5FD;
    margin-bottom: 10px;
  }}

  .header-bar {{
    background: linear-gradient(90deg, #0D0F1A 0%, #141828 100%);
    border-bottom: 1px solid rgba(59, 130, 246, 0.15);
    padding: 18px 18px 16px;
    position: sticky;
    top: 0;
    z-index: 10;
    backdrop-filter: blur(8px);
  }}

  .header-title {{
    font-size: 16px;
    font-weight: 700;
    color: #F1F5F9;
    letter-spacing: 0.06em;
  }}

  .header-date {{
    font-size: 13px;
    color: #64748B;
    margin-top: 2px;
  }}

  .watch-indicator {{
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: rgba(251, 191, 36, 0.08);
    border: 1px solid rgba(251, 191, 36, 0.2);
    border-radius: 20px;
    padding: 2px 9px;
    font-size: 9px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #FCD34D;
    margin-left: 8px;
  }}

  .footer {{
    text-align: center;
    padding: 16px;
    font-size: 10px;
    color: #334155;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }}

  .race-card {{
    width: min(100%, 460px);
  }}

  .leading-signal {{
    font-size: 12px;
    color: #FCD34D;
    font-weight: 600;
    margin-top: 4px;
    letter-spacing: 0.03em;
  }}

  .candidates-table {{
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0 14px;
    font-size: 14px;
  }}

  .candidates-table th {{
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: #64748B;
    padding: 4px 6px;
    text-align: left;
    border-bottom: 1px solid rgba(59, 130, 246, 0.15);
  }}

  .candidates-table th:nth-child(3),
  .candidates-table th:nth-child(4),
  .candidates-table th:nth-child(5) {{
    text-align: right;
  }}

  .candidate-row td {{
    padding: 6px 6px;
    border-bottom: 1px solid rgba(59, 130, 246, 0.08);
    color: #CBD5E1;
  }}

  .candidate-row:last-child td {{
    border-bottom: none;
  }}

  .candidate-rank {{
    color: #475569;
    font-weight: 600;
    font-size: 12px;
    width: 20px;
  }}

  .candidate-name {{
    font-weight: 600;
    color: #E2E8F0;
  }}

  .candidate-price {{
    text-align: right;
    color: #93C5FD;
    font-weight: 700;
  }}

  .candidate-delta {{
    text-align: right;
    color: #FDE68A;
    font-weight: 700;
  }}

  .candidate-fv {{
    color: #94A3B8;
    text-align: right;
  }}

  .candidate-fv-cell {{
    text-align: right;
  }}

  .candidate-signal {{
    margin-top: 4px;
  }}

  .candidate-forecast-cell {{
    min-width: 116px;
  }}

  .candidate-forecast {{
    text-align: left;
  }}

  .candidate-forecast-main {{
    color: #FDE68A;
    font-weight: 700;
    font-size: 12px;
  }}

  .candidate-forecast-band {{
    color: #E2E8F0;
    font-size: 11px;
    margin-top: 2px;
  }}

  .candidate-forecast-meta,
  .candidate-forecast-empty {{
    color: #93C5FD;
    font-size: 10px;
    margin-top: 3px;
    line-height: 1.4;
  }}

.verdict-sm {{
    font-size: 9px;
    padding: 2px 7px;
  }}

  .finances-block {{
    margin: 10px 0 6px 0;
    padding: 8px 10px;
    background: #151825;
    border-radius: 6px;
    border-left: 2px solid #60A5FA;
  }}
  .finances-kicker {{
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #60A5FA;
    margin-bottom: 5px;
  }}
  .finances-row {{
    display: flex;
    gap: 20px;
  }}
  .finances-stat {{}}
  .finances-label {{
    font-size: 10px;
    color: #9CA3AF;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}
  .finances-value {{
    font-size: 13px;
    font-weight: 600;
    color: #FCD34D;
  }}
  .candidate-finances-cell {{
    text-align: left;
  }}
  .candidate-finances-block {{
    display: flex;
    flex-direction: column;
    gap: 2px;
  }}
  .candidate-finances-raised,
  .candidate-finances-cash {{
    font-size: 10px;
    color: #FCD34D;
  }}
</style>
</head>
<body>

<div class="header-bar">
  <div class="header-title">Arbiter Political Briefing <span class="watch-indicator">● Live</span></div>
  <div class="header-date">{escape(_header_date(today))} &nbsp;·&nbsp; {card_count} races tracked</div>
</div>

<main class="report-shell">
  {tabs_html}
  {pages_html}
</main>

<div class="footer">Arbiter &nbsp;·&nbsp; Not financial advice &nbsp;·&nbsp; cr: {today.strftime('%Y-%m-%d')}</div>

<script>
(() => {{
  const tabs = Array.from(document.querySelectorAll('.brief-tab'));
  const panels = Array.from(document.querySelectorAll('.brief-page'));
  if (!tabs.length || tabs.length < 2) return;

  const activate = (tab) => {{
    const targetId = tab.getAttribute('data-tab-target');
    tabs.forEach((item) => {{
      const isActive = item === tab;
      item.classList.toggle('is-active', isActive);
      item.setAttribute('aria-selected', isActive ? 'true' : 'false');
    }});
    panels.forEach((panel) => {{
      const isActive = panel.id === targetId;
      panel.classList.toggle('is-active', isActive);
      panel.hidden = !isActive;
    }});
  }};

  tabs.forEach((tab) => {{
    tab.addEventListener('click', () => activate(tab));
  }});
}})();
</script>

</body>
</html>
"""

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(html_doc, encoding="utf-8")
    return OUTPUT_FILE


if __name__ == "__main__":
    try:
        path = generate()
        print(f"Generated {path}")
        print("Done")
    except Exception as e:
        print(f"ERROR: generator failed — {e}")
        raise SystemExit(1)
