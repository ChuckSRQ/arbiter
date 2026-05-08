import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  buildDailyReport,
  classifyMarket,
  DEFAULT_OPPORTUNITY_LIMIT,
} from "../analysis/engine";
import { loadLatestDashboardReport, sampleReports } from "./dashboard-data";

function createMarket(overrides: Record<string, unknown> = {}) {
  return {
    ticker: "GENERIC-1",
    title: "Generic market",
    category: "Politics",
    close_time: "2026-05-20T12:00:00Z",
    expiration_time: "2026-05-20T12:00:00Z",
    yes_bid_cents: 44,
    yes_ask_cents: 45,
    no_bid_cents: 55,
    no_ask_cents: 56,
    yes_midpoint_cents: 45,
    no_midpoint_cents: 56,
    volume: 1000,
    open_interest: 500,
    liquidity: 300,
    rules_text: "Fixture rules.",
    ...overrides,
  };
}

function createMarketSnapshot(markets: Array<Record<string, unknown>>) {
  return {
    collected_at: "2026-05-06T20:30:00Z",
    source: {
      base_url: "https://api.elections.kalshi.com/trade-api/v2",
      endpoint: "/markets",
    },
    filters: {
      window_days: 30,
      status: "open",
      max_pages: 2,
    },
    markets,
  };
}

function createPortfolioSnapshot(positions: Array<Record<string, unknown>> = []) {
  return {
    collected_at: "2026-05-06T20:40:00Z",
    source: {
      base_url: "https://api.elections.kalshi.com/trade-api/v2",
    },
    available: true,
    balance: {
      cash_balance: 5300,
      withdrawable_balance: 5000,
      portfolio_value: 10120,
    },
    positions,
    warnings: [],
  };
}

function createPollingEvidence(overrides: Record<string, unknown> = {}) {
  return {
    collected_at: "2026-05-06T19:30:00Z",
    source_url: "https://www.realclearpolling.com/",
    race: "Ohio Senate general",
    market_key: "ohio-senate-general",
    market_type: "binary-general" as const,
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
    trend_summary: "Brown has held a narrow but steady lead across the latest RCP-tracked polls.",
    evidence_links: [
      {
        label: "RCP Ohio Senate average",
        href: "https://www.realclearpolling.com/polls/senate/general/2026/ohio/brown-vs-husted",
        source: "Polling",
        note: "Primary polling average for the Ohio Senate general market.",
      },
    ],
    ...overrides,
  };
}

test("classifies supported market groups conservatively", () => {
  // Only electoral/polling markets are in scope.
  // Politics with any political keyword → politics
  assert.equal(classifyMarket(createMarket({ category: "Politics" })), "politics");
  assert.equal(classifyMarket(createMarket({ category: "Politics", title: "Will the Senate pass a bill?" })), "politics");
  assert.equal(classifyMarket(createMarket({ category: "Politics", title: "Will the approval rating exceed 50%?" })), "politics");
  // All other categories — F1, Economics, Weather, Culture — are out of scope
  assert.equal(classifyMarket(createMarket({ ticker: "F1-MONACO-LEC", category: "Sports" })), "other/no-model");
  assert.equal(classifyMarket(createMarket({ category: "Economics", title: "Will Q3 GDP exceed 4%?" })), "other/no-model");
  assert.equal(classifyMarket(createMarket({ category: "Weather", title: "Will NYC see snow?" })), "other/no-model");
  assert.equal(classifyMarket(createMarket({ category: "Culture", title: "Will this movie win an Oscar?" })), "other/no-model");
});

test("uses confidence-specific thresholds for ranking and pass logic", () => {
  // Political tickers so classifyMarket returns "politics" (not "other/no-model").
  // Polling evidence must be provided for Politics markets so the early return doesn't
  // fire before modelOverrides are consulted. market_key is set to a value that
  // normalizeCompact(ticker) contains (for the findPollingEvidence substring match).
  const pollDate = new Date().toDateString();
  const report = buildDailyReport({
    reportDate: "2026-05-06",
    marketSnapshot: createMarketSnapshot([
      createMarket({ ticker: "KXPOLL-HIGH-EDGE", category: "Politics", yes_ask_cents: 45, no_ask_cents: 56 }),
      createMarket({ ticker: "KXPOLL-MEDIUM-WATCH", category: "Politics", yes_ask_cents: 45, no_ask_cents: 56 }),
      createMarket({ ticker: "KXPOLL-LOW-PASS", category: "Politics", yes_ask_cents: 44, no_ask_cents: 57 }),
    ]),
    pollingEvidence: [
      createPollingEvidence({ market_key: "pollhighedge", race: "High Edge Poll", polling_average: { updated_at: `${pollDate}T12:00:00Z` } }),
      createPollingEvidence({ market_key: "pollmediumwatch", race: "Medium Watch Poll", polling_average: { updated_at: `${pollDate}T12:00:00Z` } }),
      createPollingEvidence({ market_key: "polllowpass", race: "Low Pass Poll", polling_average: { updated_at: `${pollDate}T12:00:00Z` } }),
    ],
    portfolioSnapshot: createPortfolioSnapshot(),
    modelOverrides: {
      "KXPOLL-HIGH-EDGE": {
        fairYesCents: 50,
        confidence: "High",
        reason: "High-confidence model still shows a clean gap.",
        whatWouldChange: "A meaningfully worse entry.",
      },
      "KXPOLL-MEDIUM-WATCH": {
        fairYesCents: 52,
        confidence: "Medium",
        reason: "The setup is close but still shy of the medium-confidence bar.",
        whatWouldChange: "A cheaper price or stronger evidence.",
      },
      "KXPOLL-LOW-PASS": {
        fairYesCents: 54,
        confidence: "Low",
        reason: "Without stronger evidence the edge is not big enough to act.",
        whatWouldChange: "A much cheaper entry.",
      },
    },
  });

  assert.equal(report.opportunities[0]?.market.ticker, "KXPOLL-HIGH-EDGE");
  assert.equal(report.opportunities[0]?.action, "Buy YES");
  assert.equal(report.opportunities[1]?.market.ticker, "KXPOLL-MEDIUM-WATCH");
  assert.equal(report.opportunities[1]?.action, "Watch");
  assert.ok(report.passes?.some((entry) => entry.market.ticker === "KXPOLL-LOW-PASS"));
  assert.equal(report.passes?.find((entry) => entry.market.ticker === "KXPOLL-LOW-PASS")?.reasonCode, "low-confidence-pass");
});

test("generates a no-trade report when nothing clears the bar", () => {
  const report = buildDailyReport({
    reportDate: "2026-05-06",
    marketSnapshot: createMarketSnapshot([
      createMarket({
        ticker: "NO-MODEL-1",
        category: "Culture",
        title: "Will this movie win an Oscar?",
      }),
    ]),
    portfolioSnapshot: createPortfolioSnapshot(),
  });

  assert.equal(report.reportLabel, "No trade day");
  assert.equal(report.opportunities.length, 0);
  assert.match(report.summary, /No trade today/i);
});

test("captures pass reason codes for markets without a reliable model", () => {
  const report = buildDailyReport({
    reportDate: "2026-05-06",
    marketSnapshot: createMarketSnapshot([
      createMarket({
        ticker: "NO-MODEL-2",
        category: "Culture",
        title: "Will this movie win an Oscar?",
      }),
    ]),
    portfolioSnapshot: createPortfolioSnapshot(),
  });

  assert.equal(report.passes?.[0]?.reasonCode, "no-reliable-model");
  assert.match(report.passes?.[0]?.reason ?? "", /reliable model/i);
});

test("recommends reduce and exit when fair value is below the executable exit price", () => {
  const report = buildDailyReport({
    reportDate: "2026-05-06",
    marketSnapshot: createMarketSnapshot([
      createMarket({
        ticker: "OIL-ABOVE-85",
        title: "WTI settles above $85 this month",
        category: "Economics",
        yes_bid_cents: 49,
        yes_ask_cents: 51,
        no_bid_cents: 49,
        no_ask_cents: 51,
      }),
      createMarket({
        ticker: "F1-VER-WIN",
        title: "Verstappen wins next race",
        category: "Sports",
        yes_bid_cents: 57,
        yes_ask_cents: 59,
        no_bid_cents: 41,
        no_ask_cents: 43,
      }),
    ]),
    portfolioSnapshot: createPortfolioSnapshot([
      {
        ticker: "OIL-ABOVE-85",
        market_title: "WTI settles above $85 this month",
        side: "YES",
        count: 60,
        avg_price: 52,
        current_price: 49,
        market_value: 2940,
        unrealized_pnl: -180,
        exposure: 3100,
      },
      {
        ticker: "F1-VER-WIN",
        market_title: "Verstappen wins next race",
        side: "YES",
        count: 25,
        avg_price: 63,
        current_price: 57,
        market_value: 1425,
        unrealized_pnl: -150,
        exposure: 1800,
      },
    ]),
    modelOverrides: {
      "OIL-ABOVE-85": {
        fairYesCents: 44,
        confidence: "Low",
        reason: "The price is richer than the cautious fair value.",
        whatWouldChange: "A materially lower price.",
      },
      "F1-VER-WIN": {
        fairYesCents: 48,
        confidence: "Medium",
        reason: "Current pace context does not support the exit price.",
        whatWouldChange: "Qualifying pace that materially improves the baseline.",
      },
    },
  });

  const oil = report.portfolio.positions.find((position) => position.market.ticker === "OIL-ABOVE-85");
  const verstappen = report.portfolio.positions.find((position) => position.market.ticker === "F1-VER-WIN");

  assert.equal(oil?.action, "Reduce");
  assert.equal(verstappen?.action, "Exit");
  assert.match(oil?.reason ?? "", /fair value/i);
  assert.equal(verstappen?.confidence, "Medium");
});

test("caps generated opportunities at five ideas by default", () => {
  // Uses Politics-category markets (in scope) instead of Economics (out of scope).
  const pollDate = new Date().toDateString();
  const markets = Array.from({ length: 7 }, (_, index) =>
    createMarket({
      ticker: `POLLIDEA-${index + 1}`,
      title: `Poll Idea ${index + 1}`,
      category: "Politics",
      yes_ask_cents: 30 + index,
      no_ask_cents: 70 - index,
    }),
  );

  const report = buildDailyReport({
    reportDate: "2026-05-06",
    marketSnapshot: createMarketSnapshot(markets),
    pollingEvidence: markets.map((m, i) =>
      createPollingEvidence({
        market_key: `pollidea${i + 1}`,
        race: `Poll Idea ${i + 1}`,
        polling_average: { updated_at: `${pollDate}T12:00:00Z` },
      }),
    ),
    portfolioSnapshot: createPortfolioSnapshot(),
    modelOverrides: Object.fromEntries(
      markets.map((market, index) => [
        String(market.ticker),
        {
          fairYesCents: 45 + index * 2,
          confidence: "High",
          reason: `Idea ${index + 1} still clears the bar.`,
          whatWouldChange: "A worse entry.",
        },
      ]),
    ),
  });

  assert.equal(report.opportunities.length, DEFAULT_OPPORTUNITY_LIMIT);
  assert.deepEqual(
    report.opportunities.map((opportunity) => opportunity.market.ticker),
    ["POLLIDEA-7", "POLLIDEA-6", "POLLIDEA-5", "POLLIDEA-4", "POLLIDEA-3"],
  );
});

test("political markets use polling evidence links and fair value when evidence exists", () => {
  const report = buildDailyReport({
    reportDate: "2026-05-06",
    marketSnapshot: createMarketSnapshot([
      createMarket({
        ticker: "OH-SEN-GEN-BROWN",
        title: "Ohio Senate general: Brown vs Husted",
        category: "Politics",
        yes_bid_cents: 52,
        yes_ask_cents: 54,
        no_bid_cents: 46,
        no_ask_cents: 48,
      }),
    ]),
    portfolioSnapshot: createPortfolioSnapshot(),
    pollingEvidence: [createPollingEvidence()],
  });

  const opportunity = report.opportunities[0];

  assert.equal(opportunity?.market.ticker, "OH-SEN-GEN-BROWN");
  assert.equal(opportunity?.action, "Buy YES");
  assert.equal(opportunity?.marcusFairValue, 61);
  assert.match(opportunity?.reason ?? "", /poll/i);
  assert.equal(opportunity?.evidenceLinks[0]?.href.includes("realclearpolling.com"), true);
  assert.equal(report.evidence.some((entry) => entry.href.includes("realclearpolling.com")), true);
});

test("political markets missing polling pass with missing-or-stale-polling", () => {
  const report = buildDailyReport({
    reportDate: "2026-05-06",
    marketSnapshot: createMarketSnapshot([
      createMarket({
        ticker: "PA-SEN-GEN",
        title: "Pennsylvania Senate general",
        category: "Politics",
      }),
    ]),
    portfolioSnapshot: createPortfolioSnapshot(),
  });

  assert.equal(report.opportunities.length, 0);
  assert.equal(report.passes?.[0]?.reasonCode, "missing-or-stale-polling");
  assert.match(report.passes?.[0]?.reason ?? "", /missing-or-stale-polling/i);
});

test("primary polling evidence includes a plurality and fragmentation warning", () => {
  const report = buildDailyReport({
    reportDate: "2026-05-06",
    marketSnapshot: createMarketSnapshot([
      createMarket({
        ticker: "LA-SEN-GOP-FLEMING",
        title: "Louisiana Senate GOP primary: Fleming vs Letlow vs Cassidy",
        category: "Politics",
        yes_bid_cents: 48,
        yes_ask_cents: 50,
        no_bid_cents: 50,
        no_ask_cents: 52,
      }),
    ]),
    portfolioSnapshot: createPortfolioSnapshot(),
    pollingEvidence: [
      createPollingEvidence({
        race: "Louisiana Senate GOP primary",
        market_key: "louisiana-senate-gop-primary",
        market_type: "multi-candidate-primary" as const,
        polling_average: {
          updated_at: "2026-05-06T19:00:00Z",
          leader: "John Fleming",
          leader_share: 32,
          runner_up: "Julia Letlow",
          runner_up_share: 28,
          spread: 4,
          fair_yes_cents: 58,
        },
        latest_polls: [
          {
            pollster: "WPA Intelligence",
            dates: {
              start: "2026-04-27",
              end: "2026-04-29",
            },
            sample: "Likely GOP primary voters 640",
            toplines: [
              { candidate: "John Fleming", pct: 32 },
              { candidate: "Julia Letlow", pct: 28 },
              { candidate: "Bill Cassidy", pct: 20 },
            ],
            spread: "Fleming +4",
          },
        ],
        trend_summary: "Fleming still leads, but the field remains fragmented and plurality dynamics matter more than raw vote share.",
        evidence_links: [
          {
            label: "RCP Louisiana GOP primary average",
            href: "https://www.realclearpolling.com/polls/senate/republican-primary/2026/louisiana/fleming-vs-letlow-vs-cassidy",
            source: "Polling",
            note: "RCP table for the Louisiana Senate GOP primary.",
          },
        ],
      }),
    ],
  });

  assert.equal(report.opportunities[0]?.market.ticker, "LA-SEN-GOP-FLEMING");
  assert.match(report.opportunities[0]?.reason ?? "", /plurality|fragment/i);
});

test("prefers the latest generated report when one is present", () => {
  const tempRoot = mkdtempSync(join(tmpdir(), "arbiter-report-loader-"));

  try {
    const generatedDir = join(tempRoot, "data", "reports", "generated");
    mkdirSync(generatedDir, { recursive: true });
    writeFileSync(join(generatedDir, "2026-05-05.json"), JSON.stringify(sampleReports.noTradeDay), "utf8");
    writeFileSync(join(generatedDir, "2026-05-06.json"), JSON.stringify(sampleReports.portfolioExitDay), "utf8");

    const report = loadLatestDashboardReport({
      reportDirectories: [generatedDir],
    });

    assert.equal(report?.reportLabel, "Portfolio cleanup brief");
  } finally {
    rmSync(tempRoot, { recursive: true, force: true });
  }
});
