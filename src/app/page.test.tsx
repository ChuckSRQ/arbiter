import assert from "node:assert/strict";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import { getTopOpportunities, mockDashboardReport } from "./dashboard-data";
import Home from "./page";

test("renders the edge-filter shell with required report sections", () => {
  const markup = renderToStaticMarkup(<Home />);

  assert.match(markup, /Arbiter/);
  assert.match(markup, /edge filter, not a broad market screener/i);
  assert.match(markup, /Today/);
  assert.match(markup, /Opportunities/);
  assert.match(markup, /Portfolio/);
  assert.match(markup, /Evidence/);
  assert.match(markup, /Archive/);
  assert.match(markup, /No trade today/i);
  assert.match(markup, /Gross exposure/i);
  assert.match(markup, /Polling/i);
  assert.match(markup, /Archived brief/i);
});

test("renders mocked market details for recommendation cards", () => {
  const markup = renderToStaticMarkup(<Home />);

  assert.match(markup, /Kalshi price/i);
  assert.match(markup, /Marcus fair value/i);
  assert.match(markup, /Confidence/i);
  assert.match(markup, /Evidence count/i);
});

test("keeps the today list focused on the top 3-5 opportunities", () => {
  const topOpportunities = getTopOpportunities(mockDashboardReport);

  assert.ok(topOpportunities.length >= 3);
  assert.ok(topOpportunities.length <= 5);
  assert.equal(topOpportunities[0]?.ticker, "FEDCUT-SEP26");
});
