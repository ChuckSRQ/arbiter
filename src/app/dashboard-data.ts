import { type DailyReport, type Opportunity, parseDailyReport } from "./report-schema";
import { DEFAULT_OPPORTUNITY_LIMIT } from "../analysis/engine";
import { loadLatestDashboardReport, SAMPLE_REPORT_DIR } from "./report-storage";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

function loadSampleReport(name: string): DailyReport {
  const rawReport = JSON.parse(
    readFileSync(/* turbopackIgnore: true*/ resolve(/* turbopackIgnore: true*/ SAMPLE_REPORT_DIR, `${name}.json`), "utf8"),
  ) as unknown;

  return parseDailyReport(rawReport);
}

export const sampleReports = {
  noTradeDay: loadSampleReport("no-trade-day"),
  politicalEdgeDay: loadSampleReport("political-edge-day"),
  portfolioExitDay: loadSampleReport("portfolio-exit-day"),
} as const;

export { loadLatestDashboardReport };
export const mockDashboardReport = loadLatestDashboardReport() ?? sampleReports.politicalEdgeDay;

export function getTopOpportunities(report: DailyReport): Opportunity[] {
  return [...report.opportunities].sort((left, right) => right.edge - left.edge).slice(0, DEFAULT_OPPORTUNITY_LIMIT);
}
