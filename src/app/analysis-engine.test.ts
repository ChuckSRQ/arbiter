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

test("classifies supported market groups conservatively", () => {
  assert.equal(classifyMarket(createMarket({ category: "Politics" })), "politics");
  assert.equal(classifyMarket(createMarket({ ticker: "F1-MONACO-LEC", category: "Sports" })), "F1");
  assert.equal(classifyMarket(createMarket({ category: "Economics", title: "Will Q3 GDP exceed 4%?" })), "economics");
  assert.equal(classifyMarket(createMarket({ category: "Weather", title: "Will NYC see snow?" })), "weather");
  assert.equal(classifyMarket(createMarket({ category: "Culture", title: "Will this movie win an Oscar?" })), "other/no-model");
});

test("uses confidence-specific thresholds for ranking and pass logic", () => {
  const report = buildDailyReport({
    reportDate: "2026-05-06",
    marketSnapshot: createMarketSnapshot([
      createMarket({ ticker: "HIGH-EDGE", yes_ask_cents: 45, no_ask_cents: 56 }),
      createMarket({ ticker: "MEDIUM-WATCH", yes_ask_cents: 45, no_ask_cents: 56 }),
      createMarket({ ticker: "LOW-PASS", yes_ask_cents: 44, no_ask_cents: 57 }),
    ]),
    portfolioSnapshot: createPortfolioSnapshot(),
    modelOverrides: {
      "HIGH-EDGE": {
        fairYesCents: 50,
        confidence: "High",
        reason: "High-confidence model still shows a clean gap.",
        whatWouldChange: "A meaningfully worse entry.",
      },
      "MEDIUM-WATCH": {
        fairYesCents: 52,
        confidence: "Medium",
        reason: "The setup is close but still shy of the medium-confidence bar.",
        whatWouldChange: "A cheaper price or stronger evidence.",
      },
      "LOW-PASS": {
        fairYesCents: 54,
        confidence: "Low",
        reason: "Without stronger evidence the edge is not big enough to act.",
        whatWouldChange: "A much cheaper entry.",
      },
    },
  });

  assert.equal(report.opportunities[0]?.market.ticker, "HIGH-EDGE");
  assert.equal(report.opportunities[0]?.action, "Buy YES");
  assert.equal(report.opportunities[1]?.market.ticker, "MEDIUM-WATCH");
  assert.equal(report.opportunities[1]?.action, "Watch");
  assert.ok(report.passes?.some((entry) => entry.market.ticker === "LOW-PASS"));
  assert.equal(report.passes?.find((entry) => entry.market.ticker === "LOW-PASS")?.reasonCode, "low-confidence-pass");
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
  const markets = Array.from({ length: 7 }, (_, index) =>
    createMarket({
      ticker: `IDEA-${index + 1}`,
      title: `Idea ${index + 1}`,
      category: "Economics",
      yes_ask_cents: 30 + index,
      no_ask_cents: 70 - index,
    }),
  );

  const report = buildDailyReport({
    reportDate: "2026-05-06",
    marketSnapshot: createMarketSnapshot(markets),
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
    ["IDEA-7", "IDEA-6", "IDEA-5", "IDEA-4", "IDEA-3"],
  );
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
