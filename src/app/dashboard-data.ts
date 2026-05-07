import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import { type DailyReport, type Opportunity, parseDailyReport } from "./report-schema";
import { DEFAULT_OPPORTUNITY_LIMIT } from "../analysis/engine";

const DATED_REPORT_FILE = /^\d{4}-\d{2}-\d{2}\.json$/;
const SAMPLE_REPORT_DIR = resolve(/* turbopackIgnore: true*/ process.cwd(), "data", "reports", "sample");
const GENERATED_REPORT_DIR = resolve(/* turbopackIgnore: true*/ process.cwd(), "data", "reports", "generated");
const ARCHIVE_REPORT_DIR = resolve(/* turbopackIgnore: true*/ process.cwd(), "reports");

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

type DashboardReportLoaderOptions = {
  reportDirectories?: string[];
};

function latestReportPath(reportDirectories: string[]): string | null {
  const candidates = reportDirectories.flatMap((directory) => {
    try {
      return readdirSync(/* turbopackIgnore: true*/ directory)
        .filter((entry) => DATED_REPORT_FILE.test(entry))
        .map((entry) => resolve(/* turbopackIgnore: true*/ directory, entry));
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") {
        return [];
      }

      throw error;
    }
  });

  return candidates.sort().at(-1) ?? null;
}

export function loadLatestDashboardReport({
  reportDirectories = [GENERATED_REPORT_DIR, ARCHIVE_REPORT_DIR],
}: DashboardReportLoaderOptions = {}): DailyReport | null {
  const reportPath = latestReportPath(reportDirectories);
  if (!reportPath) {
    return null;
  }

  return parseDailyReport(JSON.parse(readFileSync(/* turbopackIgnore: true*/ reportPath, "utf8")) as unknown);
}

export const mockDashboardReport = loadLatestDashboardReport() ?? sampleReports.politicalEdgeDay;

export function getTopOpportunities(report: DailyReport): Opportunity[] {
  return [...report.opportunities].sort((left, right) => right.edge - left.edge).slice(0, DEFAULT_OPPORTUNITY_LIMIT);
}
