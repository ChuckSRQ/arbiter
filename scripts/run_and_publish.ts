import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { type DailyReport } from "../src/app/report-schema";
import { readReportFile } from "../src/app/report-storage";

export type RevalidateStatus = "ok" | "failed";

export interface PublishSummary {
  reportDate: string;
  reportLabel: string;
  opportunitiesCount: number;
  positionActionsCount: number;
  summary: string;
  revalidateStatus: RevalidateStatus;
}

function buildActionSummary(opportunitiesCount: number, positionActionsCount: number): string {
  if (opportunitiesCount === 0 && positionActionsCount === 0) {
    return "No trade today";
  }

  if (opportunitiesCount === 0) {
    return `${positionActionsCount} position action${positionActionsCount === 1 ? "" : "s"}`;
  }

  if (positionActionsCount === 0) {
    return `${opportunitiesCount} trade idea${opportunitiesCount === 1 ? "" : "s"}`;
  }

  return `${opportunitiesCount} trade idea${opportunitiesCount === 1 ? "" : "s"}, ${positionActionsCount} position action${positionActionsCount === 1 ? "" : "s"}`;
}

function runDailyReportPipeline(projectRoot: string): void {
  execFileSync(process.execPath, ["--import", "tsx", resolve(projectRoot, "scripts", "run_daily_report.ts")], {
    cwd: projectRoot,
    stdio: "pipe",
  });
}

export function buildPublishSummary(
  report: DailyReport,
  revalidateStatus: RevalidateStatus,
): PublishSummary {
  const opportunitiesCount = report.opportunities.length;
  const positionActionsCount = report.portfolio.positions.filter((position) => position.action !== "Hold").length;

  return {
    reportDate: report.reportDate,
    reportLabel: report.reportLabel,
    opportunitiesCount,
    positionActionsCount,
    summary: buildActionSummary(opportunitiesCount, positionActionsCount),
    revalidateStatus,
  };
}

export async function revalidateDashboard(
  fetchImpl: typeof fetch = fetch,
): Promise<RevalidateStatus> {
  try {
    const response = await fetchImpl("http://localhost:4000/api/revalidate", {
      method: "POST",
    });

    return response.ok ? "ok" : "failed";
  } catch {
    return "failed";
  }
}

export async function main(): Promise<void> {
  const projectRoot = process.cwd();

  runDailyReportPipeline(projectRoot);

  const report = readReportFile(resolve(projectRoot, "data", "reports", "generated", "latest.json"));
  const revalidateStatus = await revalidateDashboard();

  process.stdout.write(`${JSON.stringify(buildPublishSummary(report, revalidateStatus))}\n`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  void main().catch((error: unknown) => {
    const message = error instanceof Error ? error.stack ?? error.message : String(error);
    process.stderr.write(`${message}\n`);
    process.exitCode = 1;
  });
}
