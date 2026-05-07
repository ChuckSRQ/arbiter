import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { type DailyReport, type Opportunity, parseDailyReport } from "./report-schema";

function loadSampleReport(name: string): DailyReport {
  const rawReport = JSON.parse(
    readFileSync(resolve(process.cwd(), "data", "reports", "sample", `${name}.json`), "utf8"),
  ) as unknown;

  return parseDailyReport(rawReport);
}

export const sampleReports = {
  noTradeDay: loadSampleReport("no-trade-day"),
  politicalEdgeDay: loadSampleReport("political-edge-day"),
  portfolioExitDay: loadSampleReport("portfolio-exit-day"),
} as const;

export const mockDashboardReport = sampleReports.politicalEdgeDay;

export function getTopOpportunities(report: DailyReport): Opportunity[] {
  return [...report.opportunities].sort((left, right) => right.edge - left.edge).slice(0, 5);
}
