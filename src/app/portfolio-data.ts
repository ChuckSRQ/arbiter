import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import type { DailyReport, EvidenceLink, RecommendationAction } from "./report-schema";

const DEFAULT_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2";
const PORTFOLIO_DIR = resolve(/* turbopackIgnore: true*/ process.cwd(), "data", "portfolio");
const DATED_PORTFOLIO_FILE = /^\d{4}-\d{2}-\d{2}\.json$/;
const DEFAULT_WARNING =
  "Missing Kalshi portfolio credentials. Add KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH locally to enable the live reader.";

type PortfolioAction = Extract<RecommendationAction, "Hold" | "Reduce" | "Exit">;

export interface PortfolioBalanceSnapshot {
  cashBalance: number | null;
  withdrawableBalance: number | null;
  portfolioValue: number | null;
}

export interface PortfolioPositionSnapshot {
  ticker: string;
  marketTitle: string;
  side: string;
  count: number;
  avgPrice: number | null;
  currentPrice: number | null;
  marketValue: number | null;
  unrealizedPnl: number | null;
  exposure: number | null;
  recommendation: string | null;
}

export interface PortfolioSnapshot {
  collectedAt: string;
  source: {
    baseUrl: string;
  };
  available: boolean;
  balance?: PortfolioBalanceSnapshot;
  positions: PortfolioPositionSnapshot[];
  warnings: string[];
}

export interface PortfolioReviewCard {
  ticker: string;
  title: string;
  action: PortfolioAction;
  exposure: number;
  pnl: number;
  note: string;
  evidenceLinks: EvidenceLink[];
  sourceLabel: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function parseBalance(value: unknown): PortfolioBalanceSnapshot | undefined {
  if (!isRecord(value)) {
    return undefined;
  }

  return {
    cashBalance: asNumber(value.cash_balance),
    withdrawableBalance: asNumber(value.withdrawable_balance),
    portfolioValue: asNumber(value.portfolio_value),
  };
}

function parsePosition(value: unknown): PortfolioPositionSnapshot {
  if (!isRecord(value)) {
    throw new Error("Portfolio position must be an object.");
  }

  return {
    ticker: asString(value.ticker, "UNKNOWN"),
    marketTitle: asString(value.market_title, "Unknown market"),
    side: asString(value.side, "UNKNOWN"),
    count: asNumber(value.count) ?? 0,
    avgPrice: asNumber(value.avg_price),
    currentPrice: asNumber(value.current_price),
    marketValue: asNumber(value.market_value),
    unrealizedPnl: asNumber(value.unrealized_pnl),
    exposure: asNumber(value.exposure),
    recommendation: typeof value.recommendation === "string" ? value.recommendation : null,
  };
}

function parsePortfolioSnapshot(value: unknown): PortfolioSnapshot {
  if (!isRecord(value)) {
    throw new Error("Portfolio snapshot must be an object.");
  }

  return {
    collectedAt: asString(value.collected_at),
    source: {
      baseUrl: isRecord(value.source) ? asString(value.source.base_url, DEFAULT_BASE_URL) : DEFAULT_BASE_URL,
    },
    available: value.available === true,
    balance: parseBalance(value.balance),
    positions: Array.isArray(value.positions) ? value.positions.map((position) => parsePosition(position)) : [],
    warnings: Array.isArray(value.warnings)
      ? value.warnings.filter((warning): warning is string => typeof warning === "string")
      : [],
  };
}

function latestPortfolioSnapshotPath(): string | null {
  try {
    const fileName = readdirSync(PORTFOLIO_DIR)
      .filter((entry) => DATED_PORTFOLIO_FILE.test(entry))
      .sort()
      .at(-1);

    return fileName ? resolve(PORTFOLIO_DIR, fileName) : null;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      return null;
    }

    throw error;
  }
}

export const unavailablePortfolioSnapshot: PortfolioSnapshot = {
  collectedAt: "",
  source: { baseUrl: DEFAULT_BASE_URL },
  available: false,
  positions: [],
  warnings: [DEFAULT_WARNING],
};

export const fixturePortfolioSnapshot: PortfolioSnapshot = {
  collectedAt: "2026-05-06T20:30:00Z",
  source: { baseUrl: DEFAULT_BASE_URL },
  available: true,
  balance: {
    cashBalance: 5300,
    withdrawableBalance: 5000,
    portfolioValue: 10120,
  },
  positions: [
    {
      ticker: "OIL-ABOVE-85",
      marketTitle: "WTI settles above $85 this month",
      side: "YES",
      count: 60,
      avgPrice: 52,
      currentPrice: 49,
      marketValue: 2940,
      unrealizedPnl: -180,
      exposure: 3100,
      recommendation: "Reduce candidate",
    },
    {
      ticker: "F1-VER-WIN",
      marketTitle: "Verstappen wins next race",
      side: "YES",
      count: 25,
      avgPrice: 63,
      currentPrice: 57,
      marketValue: 1425,
      unrealizedPnl: -150,
      exposure: 1800,
      recommendation: "Exit candidate",
    },
  ],
  warnings: [],
};

export function loadLatestPortfolioSnapshot(): PortfolioSnapshot {
  const snapshotPath = latestPortfolioSnapshotPath();
  if (!snapshotPath) {
    return unavailablePortfolioSnapshot;
  }

  return parsePortfolioSnapshot(JSON.parse(readFileSync(/* turbopackIgnore: true*/ snapshotPath, "utf8")) as unknown);
}

export const defaultPortfolioSnapshot = loadLatestPortfolioSnapshot();

function recommendationAction(recommendation: string | null): PortfolioAction {
  if (recommendation === "Exit candidate") {
    return "Exit";
  }

  if (recommendation === "Reduce candidate") {
    return "Reduce";
  }

  return "Hold";
}

function livePositionNote(position: PortfolioPositionSnapshot): string {
  const fragments = [`${position.side} · ${position.count.toLocaleString()} contracts`];

  if (position.avgPrice !== null) {
    fragments.push(`avg ${position.avgPrice}c`);
  }

  if (position.currentPrice !== null) {
    fragments.push(`mark ${position.currentPrice}c`);
  }

  if (position.recommendation) {
    fragments.push(position.recommendation);
  }

  return fragments.join(" · ");
}

export function getPortfolioReviewCards(
  report: DailyReport,
  portfolioSnapshot: PortfolioSnapshot,
): PortfolioReviewCard[] {
  if (!portfolioSnapshot.available) {
    return report.portfolio.positions.map((position) => ({
      ticker: position.market.ticker,
      title: position.title,
      action: position.action,
      exposure: position.exposure,
      pnl: position.pnl,
      note: position.note,
      evidenceLinks: position.evidenceLinks,
      sourceLabel: "Report brief",
    }));
  }

  return portfolioSnapshot.positions.map((position) => ({
    ticker: position.ticker,
    title: position.marketTitle,
    action: recommendationAction(position.recommendation),
    exposure: position.exposure ?? 0,
    pnl: position.unrealizedPnl ?? 0,
    note: livePositionNote(position),
    evidenceLinks: [],
    sourceLabel: "Live snapshot",
  }));
}
