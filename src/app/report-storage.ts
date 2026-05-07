import { existsSync, readdirSync, readFileSync } from "node:fs";
import { resolve, sep } from "node:path";

import { type ArchiveEntry, type DailyReport, parseDailyReport } from "./report-schema";

export const DATED_REPORT_FILE = /^\d{4}-\d{2}-\d{2}\.json$/;
export const SAMPLE_REPORT_DIR = resolve(/* turbopackIgnore: true*/ process.cwd(), "data", "reports", "sample");
export const GENERATED_REPORT_DIR = resolve(/* turbopackIgnore: true*/ process.cwd(), "data", "reports", "generated");
export const ARCHIVE_REPORT_DIR = resolve(/* turbopackIgnore: true*/ process.cwd(), "reports");
export const LATEST_REPORT_PATH = resolve(/* turbopackIgnore: true*/ GENERATED_REPORT_DIR, "latest.json");

export interface DashboardReportLoaderOptions {
  currentReportPath?: string | null;
  reportDirectories?: string[];
  archiveDirectories?: string[];
  archiveLimit?: number;
}

export type DashboardReportSource = "generated" | "archive" | "none";

export interface DashboardReportLoadResult {
  report: DailyReport | null;
  reportPath: string | null;
  source: DashboardReportSource;
}

function reportActionSummary(report: DailyReport): string {
  const positionActions = report.portfolio.positions.filter((position) => position.action !== "Hold").length;

  if (report.opportunities.length === 0 && positionActions === 0) {
    return "No trade today";
  }

  if (report.opportunities.length === 0) {
    return `${positionActions} position action${positionActions === 1 ? "" : "s"}`;
  }

  if (positionActions === 0) {
    return `${report.opportunities.length} trade idea${report.opportunities.length === 1 ? "" : "s"}`;
  }

  return `${report.opportunities.length} trade idea${report.opportunities.length === 1 ? "" : "s"}, ${positionActions} position action${positionActions === 1 ? "" : "s"}`;
}

export function readReportFile(path: string): DailyReport {
  return parseDailyReport(JSON.parse(readFileSync(/* turbopackIgnore: true*/ path, "utf8")) as unknown);
}

export function reportToArchiveEntry(report: DailyReport): ArchiveEntry {
  return {
    date: report.reportDate,
    headline: report.reportLabel.startsWith("Archived brief")
      ? report.reportLabel
      : `Archived brief · ${report.reportLabel}`,
    summary: report.summary,
    verdict: reportActionSummary(report),
  };
}

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

function pathBelongsToDirectory(path: string, directory: string): boolean {
  const normalizedPath = resolve(/* turbopackIgnore: true*/ path);
  const normalizedDirectory = resolve(/* turbopackIgnore: true*/ directory);

  return normalizedPath === normalizedDirectory || normalizedPath.startsWith(`${normalizedDirectory}${sep}`);
}

function reportSourceForPath(reportPath: string | null, archiveDirectories: string[]): DashboardReportSource {
  if (!reportPath) {
    return "none";
  }

  return archiveDirectories.some((directory) => pathBelongsToDirectory(reportPath, directory))
    ? "archive"
    : "generated";
}

export function loadArchiveEntries({
  archiveDirectories = [ARCHIVE_REPORT_DIR],
  excludeDates = [],
  limit = 6,
}: {
  archiveDirectories?: string[];
  excludeDates?: string[];
  limit?: number;
} = {}): ArchiveEntry[] {
  return archiveDirectories
    .flatMap((directory) => {
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
    })
    .sort()
    .reverse()
    .map((path) => readReportFile(path))
    .filter((report) => !excludeDates.includes(report.reportDate))
    .slice(0, limit)
    .map((report) => reportToArchiveEntry(report));
}

export function loadLatestDashboardReport({
  currentReportPath,
  reportDirectories = [GENERATED_REPORT_DIR, ARCHIVE_REPORT_DIR],
  archiveDirectories = [ARCHIVE_REPORT_DIR],
  archiveLimit = 6,
}: DashboardReportLoaderOptions = {}): DailyReport | null {
  return loadLatestDashboardReportResult({
    currentReportPath,
    reportDirectories,
    archiveDirectories,
    archiveLimit,
  }).report;
}

export function loadLatestDashboardReportResult({
  currentReportPath,
  reportDirectories = [GENERATED_REPORT_DIR, ARCHIVE_REPORT_DIR],
  archiveDirectories = [ARCHIVE_REPORT_DIR],
  archiveLimit = 6,
}: DashboardReportLoaderOptions = {}): DashboardReportLoadResult {
  const resolvedCurrentReportPath =
    currentReportPath !== undefined
      ? currentReportPath
      : reportDirectories.includes(GENERATED_REPORT_DIR)
        ? LATEST_REPORT_PATH
        : null;
  const reportPath =
    resolvedCurrentReportPath && existsSync(resolvedCurrentReportPath)
      ? resolvedCurrentReportPath
      : latestReportPath(reportDirectories);
  const report = reportPath ? readReportFile(reportPath) : null;

  if (!report) {
    return {
      report: null,
      reportPath: null,
      source: "none",
    };
  }

  const archive = loadArchiveEntries({
    archiveDirectories,
    excludeDates: [report.reportDate],
    limit: archiveLimit,
  });

  return {
    report: {
      ...report,
      archive: archive.length > 0 ? archive : report.archive,
    },
    reportPath,
    source: reportSourceForPath(reportPath, archiveDirectories),
  };
}
