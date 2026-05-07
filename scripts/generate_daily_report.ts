import { mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

import {
  type PortfolioSnapshotInput,
  type PublicMarketSnapshotFile,
  buildDailyReport,
} from "../src/analysis/engine";
import { parsePollingEvidenceFile } from "../src/analysis/polling-evidence";
import { parseDailyReport } from "../src/app/report-schema";

const DATED_JSON_FILE = /^\d{4}-\d{2}-\d{2}\.json$/;

function readFlag(name: string): string | undefined {
  const index = process.argv.indexOf(name);
  if (index === -1) {
    return undefined;
  }

  return process.argv[index + 1];
}

function latestDatedFile(directory: string): string {
  const fileName = readdirSync(directory)
    .filter((entry) => DATED_JSON_FILE.test(entry))
    .sort()
    .at(-1);

  if (!fileName) {
    throw new Error(`No dated JSON snapshots were found in ${directory}.`);
  }

  return resolve(directory, fileName);
}

function readJsonFile<T>(path: string): T {
  return JSON.parse(readFileSync(path, "utf8")) as T;
}

function reportDateFromPath(path: string): string {
  const match = path.match(/(\d{4}-\d{2}-\d{2})\.json$/);
  if (!match) {
    throw new Error(`Could not infer a report date from ${path}.`);
  }

  return match[1];
}

function main(): void {
  const cwd = process.cwd();
  const marketSnapshotPath =
    readFlag("--market-snapshot") ?? latestDatedFile(resolve(cwd, "data", "kalshi_snapshot"));
  const portfolioSnapshotPath =
    readFlag("--portfolio-snapshot") ?? resolve(cwd, "data", "portfolio", `${reportDateFromPath(marketSnapshotPath)}.json`);
  const reportDate = readFlag("--report-date") ?? reportDateFromPath(marketSnapshotPath);
  const outputPath =
    readFlag("--output") ?? resolve(cwd, "data", "reports", "generated", `${reportDate}.json`);
  const pollingEvidencePath = readFlag("--polling-evidence");

  const marketSnapshot = readJsonFile<PublicMarketSnapshotFile>(marketSnapshotPath);
  const portfolioSnapshot = readJsonFile<PortfolioSnapshotInput>(portfolioSnapshotPath);
  const pollingEvidence = pollingEvidencePath
    ? parsePollingEvidenceFile(readJsonFile<unknown>(pollingEvidencePath)).evidence
    : undefined;
  const report = buildDailyReport({
    reportDate,
    marketSnapshot,
    portfolioSnapshot,
    pollingEvidence,
  });

  parseDailyReport(report);
  mkdirSync(dirname(outputPath), { recursive: true });
  writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");

  process.stdout.write(
    `${JSON.stringify({
      output: outputPath,
      opportunities: report.opportunities.length,
      positionActions: report.portfolio.positions.filter((position) => position.action !== "Hold").length,
    })}\n`,
  );
}

main();
