"""Arbiter Generator — renders HTML report from complete market state."""

from datetime import datetime
from html import escape
from pathlib import Path

from state import get_complete, read_state

OUTPUT_FILE = Path(__file__).parent / "output" / "index.html"


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


def _render_card(market):
    try:
        delta = int(round(float(market.get("delta") or 0)))
    except (TypeError, ValueError):
        delta = 0
    verdict = _verdict(delta)
    verdict_class = "verdict-trade" if verdict == "TRADE" else "verdict-pass"
    delta_style = "" if delta >= 5 else ' style="color:#9CA3AF"'
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
    <div class="election-date">{_card_date(market.get("election_date"))}</div>
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
  </div>

  <div class="reason-label">Analysis</div>
  <div class="reason-text">
    {escape(market.get("analysis") or "")}
  </div>{source_block}
</div>"""


def generate():
    state = read_state()
    markets = get_complete(state)
    today = datetime.now()

    cards_html = "\n\n".join(_render_card(market) for market in markets)
    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=450, height=800">
<title>Arbiter — Political Briefing</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    max-width: 1200px;
    margin: 0 auto;
    background: #0D0F1A;
    color: #E8E4DC;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 16px;
    overflow-y: auto;
  }}

  .card {{
    background: linear-gradient(160deg, #141828 0%, #0D0F1A 60%);
    border: 1px solid rgba(59, 130, 246, 0.18);
    border-radius: 20px;
    padding: 18px;
    margin: 12px;
  }}

  .card + .card {{ margin-top: 0; }}

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
</style>
</head>
<body>

<div class="header-bar">
  <div class="header-title">Arbiter Political Briefing <span class="watch-indicator">● Live</span></div>
  <div class="header-date">{escape(_header_date(today))} &nbsp;·&nbsp; {len(markets)} elections tracked</div>
</div>

{cards_html}

<div class="footer">Arbiter &nbsp;·&nbsp; Not financial advice &nbsp;·&nbsp; cr: {today.strftime('%Y-%m-%d')}</div>

</body>
</html>
"""

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(html_doc, encoding="utf-8")
    return OUTPUT_FILE


if __name__ == "__main__":
    path = generate()
    print(f"Generated {path}")
