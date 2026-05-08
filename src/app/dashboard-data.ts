import { type DailyReport, type Opportunity, parseDailyReport } from "./report-schema";
import { calculateOpportunityScore, DEFAULT_OPPORTUNITY_LIMIT } from "../analysis/engine";
import {
  type DashboardReportLoaderOptions,
  type DashboardReportSource,
  loadLatestDashboardReport,
  loadLatestDashboardReportResult,
  SAMPLE_REPORT_DIR,
} from "./report-storage";
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

export type DashboardReportState = "generated" | "archived" | "sample" | "error";

export interface DashboardReportStatus {
  state: DashboardReportState;
  label: string;
  detail: string;
  sourceLabel: string;
}

export interface DashboardPageData {
  report: DailyReport;
  reportStatus: DashboardReportStatus;
}

export interface DashboardPageDataOptions extends DashboardReportLoaderOptions {
  fallbackReport?: DailyReport;
}

function statusForLoadedReport(source: DashboardReportSource, report: DailyReport): DashboardReportStatus {
  if (source === "archive") {
    return {
      state: "archived",
      label: "Archive report loaded",
      detail:
        "No generated latest pointer was available, so Arbiter promoted the newest archived brief and kept the history shelf hydrated.",
      sourceLabel: `Archived brief · ${report.reportDate}`,
    };
  }

  return {
    state: "generated",
    label: "Generated report ready",
    detail:
      "The latest saved brief is in place, so the dashboard is rendering a real local report instead of a static sample fallback.",
    sourceLabel: `Generated brief · ${report.reportDate}`,
  };
}

export function loadDashboardPageData({
  fallbackReport = sampleReports.noTradeDay,
  ...options
}: DashboardPageDataOptions = {}): DashboardPageData {
  try {
    const loadedReport = loadLatestDashboardReportResult(options);

    if (loadedReport.report) {
      return {
        report: loadedReport.report,
        reportStatus: statusForLoadedReport(loadedReport.source, loadedReport.report),
      };
    }

    return {
      report: fallbackReport,
      reportStatus: {
        state: "sample",
        label: "Waiting for generated brief",
        detail:
          "No saved report feed was available at build time, so Arbiter is showing a safe static no-trade sample until the next local run.",
        sourceLabel: "Static fallback brief",
      },
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown report loading error.";

    return {
      report: fallbackReport,
      reportStatus: {
        state: "error",
        label: "Report feed needs review",
        detail: `Saved report data could not be loaded cleanly, so Arbiter fell back to a safe static brief. ${message}`,
        sourceLabel: "Fallback after load error",
      },
    };
  }
}

export const defaultDashboardPageData = loadDashboardPageData();

export { loadLatestDashboardReport };
export const mockDashboardReport = defaultDashboardPageData.report;
export const mockDashboardReportStatus = defaultDashboardPageData.reportStatus;

export function getTopOpportunities(report: DailyReport): Opportunity[] {
  return [...report.opportunities]
    .sort((left, right) => calculateOpportunityScore(right) - calculateOpportunityScore(left))
    .slice(0, DEFAULT_OPPORTUNITY_LIMIT);
}
