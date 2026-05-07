import assert from "node:assert/strict";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import { getTopOpportunities, sampleReports, type DashboardReportStatus } from "./dashboard-data";
import Home from "./page";
import { fixturePortfolioSnapshot, unavailablePortfolioSnapshot } from "./portfolio-data";

const generatedReportStatus: DashboardReportStatus = {
  state: "generated",
  label: "Generated report ready",
  detail: "The latest saved brief is in place.",
  sourceLabel: "Generated brief · 2026-05-06",
};

test("renders the edge-filter shell with required report sections", () => {
  const markup = renderToStaticMarkup(
    <Home report={sampleReports.politicalEdgeDay} reportStatus={generatedReportStatus} />,
  );

  assert.match(markup, /Arbiter/);
  assert.match(markup, /edge filter, not a broad market screener/i);
  assert.match(markup, /Latest report status/i);
  assert.match(markup, /Generated report ready/i);
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
  const markup = renderToStaticMarkup(
    <Home report={sampleReports.politicalEdgeDay} reportStatus={generatedReportStatus} />,
  );

  assert.match(markup, /Kalshi price/i);
  assert.match(markup, /Marcus fair value/i);
  assert.match(markup, /Confidence/i);
  assert.match(markup, /Evidence count/i);
  assert.match(markup, /RCP generic ballot average/i);
});

test("keeps the today list focused on the top 3-5 opportunities", () => {
  const topOpportunities = getTopOpportunities(sampleReports.politicalEdgeDay);

  assert.ok(topOpportunities.length >= 3);
  assert.ok(topOpportunities.length <= 5);
  assert.equal(topOpportunities[0]?.market.ticker, "HOUSE-DEM-2026");
});

test("renders a no-trade report without opportunity cards", () => {
  const markup = renderToStaticMarkup(
    <Home report={sampleReports.noTradeDay} reportStatus={generatedReportStatus} />,
  );

  assert.match(markup, /No trade today/i);
  assert.match(markup, /0 qualified ideas/i);
  assert.match(markup, /Nothing cleared the evidence bar today/i);
  assert.match(markup, /Pass log|Evidence first/i);
});

test("renders missing evidence and portfolio exit actions gracefully", () => {
  const markup = renderToStaticMarkup(
    <Home report={sampleReports.portfolioExitDay} reportStatus={generatedReportStatus} />,
  );

  assert.match(markup, /No linked evidence yet/i);
  assert.match(markup, /Reduce/i);
  assert.match(markup, /Exit/i);
  assert.match(markup, /Open evidence shelf/i);
});

test("renders a clean portfolio unavailable state", () => {
  const markup = renderToStaticMarkup(
    <Home
      report={sampleReports.noTradeDay}
      reportStatus={generatedReportStatus}
      portfolioSnapshot={unavailablePortfolioSnapshot}
    />,
  );

  assert.match(markup, /Portfolio unavailable/i);
  assert.match(markup, /Missing Kalshi portfolio credentials/i);
  assert.match(markup, /Hold/i);
  assert.match(markup, /Review source/i);
});

test("renders fixture-backed reduce and exit recommendations", () => {
  const markup = renderToStaticMarkup(
    <Home
      report={sampleReports.noTradeDay}
      reportStatus={generatedReportStatus}
      portfolioSnapshot={fixturePortfolioSnapshot}
    />,
  );

  assert.match(markup, /Live portfolio snapshot/i);
  assert.match(markup, /OIL-ABOVE-85/i);
  assert.match(markup, /Reduce/i);
  assert.match(markup, /Exit/i);
});

test("renders polling evidence summaries and source links from the report", () => {
  const report = {
    ...sampleReports.politicalEdgeDay,
    pollingEvidence: [
      {
        collected_at: "2026-05-06T19:30:00Z",
        source_url: "https://www.realclearpolling.com/",
        race: "Ohio Senate general",
        market_key: "ohio-senate-general",
        market_type: "binary-general",
        polling_average: {
          updated_at: "2026-05-06T19:00:00Z",
          leader: "Sherrod Brown",
          leader_share: 48,
          runner_up: "Jon Husted",
          runner_up_share: 45,
          spread: 3,
          fair_yes_cents: 61,
        },
        latest_polls: [
          {
            pollster: "Marist",
            dates: {
              start: "2026-05-01",
              end: "2026-05-03",
            },
            sample: "Likely voters 912",
            toplines: [
              { candidate: "Sherrod Brown", pct: 48 },
              { candidate: "Jon Husted", pct: 45 },
            ],
            spread: "Brown +3",
          },
        ],
        trend_summary: "Brown keeps a small but stable edge in the latest public polling.",
        evidence_links: [
          {
            label: "RCP Ohio Senate average",
            href: "https://www.realclearpolling.com/polls/senate/general/2026/ohio/brown-vs-husted",
            source: "Polling",
            note: "Ohio Senate general polling average.",
          },
        ],
      },
    ],
  };

  const markup = renderToStaticMarkup(<Home report={report} reportStatus={generatedReportStatus} />);

  assert.match(markup, /Ohio Senate general/i);
  assert.match(markup, /Brown \+3/i);
  assert.match(markup, /realclearpolling/i);
});

test("renders archive status when no prior reports are archived yet", () => {
  const markup = renderToStaticMarkup(
    <Home report={{ ...sampleReports.noTradeDay, archive: [] }} reportStatus={generatedReportStatus} />,
  );

  assert.match(markup, /Archive pending/i);
  assert.match(markup, /The latest daily report is ready, but there are no prior archived briefs yet/i);
});

test("renders a static fallback report status when the feed needs review", () => {
  const markup = renderToStaticMarkup(
    <Home
      report={sampleReports.noTradeDay}
      reportStatus={{
        state: "error",
        label: "Report feed needs review",
        detail: "Saved report data could not be loaded cleanly.",
        sourceLabel: "Fallback after load error",
      }}
    />,
  );

  assert.match(markup, /Report feed needs review/i);
  assert.match(markup, /Fallback after load error/i);
});
