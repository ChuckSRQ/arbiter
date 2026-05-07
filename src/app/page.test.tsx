import assert from "node:assert/strict";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import { getTopOpportunities, sampleReports } from "./dashboard-data";
import Home from "./page";
import { fixturePortfolioSnapshot, unavailablePortfolioSnapshot } from "./portfolio-data";

test("renders the edge-filter shell with required report sections", () => {
  const markup = renderToStaticMarkup(<Home report={sampleReports.politicalEdgeDay} />);

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
  const markup = renderToStaticMarkup(<Home report={sampleReports.politicalEdgeDay} />);

  assert.match(markup, /Kalshi price/i);
  assert.match(markup, /Marcus fair value/i);
  assert.match(markup, /Confidence/i);
  assert.match(markup, /Evidence count/i);
});

test("keeps the today list focused on the top 3-5 opportunities", () => {
  const topOpportunities = getTopOpportunities(sampleReports.politicalEdgeDay);

  assert.ok(topOpportunities.length >= 3);
  assert.ok(topOpportunities.length <= 5);
  assert.equal(topOpportunities[0]?.market.ticker, "HOUSE-DEM-2026");
});

test("renders a no-trade report without opportunity cards", () => {
  const markup = renderToStaticMarkup(<Home report={sampleReports.noTradeDay} />);

  assert.match(markup, /No trade today/i);
  assert.match(markup, /0 qualified ideas/i);
  assert.match(markup, /No new opportunities cleared the evidence bar today/i);
});

test("renders missing evidence and portfolio exit actions gracefully", () => {
  const markup = renderToStaticMarkup(<Home report={sampleReports.portfolioExitDay} />);

  assert.match(markup, /No linked evidence yet/i);
  assert.match(markup, /Reduce/i);
  assert.match(markup, /Exit/i);
});

test("renders a clean portfolio unavailable state", () => {
  const markup = renderToStaticMarkup(
    <Home report={sampleReports.noTradeDay} portfolioSnapshot={unavailablePortfolioSnapshot} />,
  );

  assert.match(markup, /Portfolio unavailable/i);
  assert.match(markup, /Missing Kalshi portfolio credentials/i);
  assert.match(markup, /Hold/i);
});

test("renders fixture-backed reduce and exit recommendations", () => {
  const markup = renderToStaticMarkup(
    <Home report={sampleReports.noTradeDay} portfolioSnapshot={fixturePortfolioSnapshot} />,
  );

  assert.match(markup, /Live portfolio snapshot/i);
  assert.match(markup, /OIL-ABOVE-85/i);
  assert.match(markup, /Reduce/i);
  assert.match(markup, /Exit/i);
});
