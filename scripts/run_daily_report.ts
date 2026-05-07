import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { renderDailyReportMarkdown } from "../src/app/report-markdown";
import {
  ARCHIVE_REPORT_DIR,
  GENERATED_REPORT_DIR,
  LATEST_REPORT_PATH,
  loadArchiveEntries,
  readReportFile,
} from "../src/app/report-storage";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(scriptDirectory, "..");
const publicCollectorScript = resolve(scriptDirectory, "collect_kalshi_public_snapshot.py");
const portfolioCollectorScript = resolve(scriptDirectory, "collect_kalshi_portfolio.py");
const reportGeneratorScript = resolve(scriptDirectory, "generate_daily_report.ts");
const tsxBinary = resolve(repoRoot, "node_modules", ".bin", "tsx");

function readFlag(name: string): string | undefined {
  const index = process.argv.indexOf(name);
  if (index === -1) {
    return undefined;
  }

  return process.argv[index + 1];
}

function todayDate(): string {
  return new Date().toISOString().slice(0, 10);
}

function writeTextFile(path: string, contents: string): void {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, contents, "utf8");
}

function runCommand(command: string, args: string[]): string {
  return execFileSync(command, args, {
    cwd: process.cwd(),
    stdio: "pipe",
  }).toString("utf8");
}

function defaultPollingEvidencePath(projectRoot: string): string | undefined {
  const candidates = [
    resolve(projectRoot, "data", "polling_evidence", "current.json"),
    resolve(projectRoot, "data", "polling_evidence", "sample.json"),
  ];

  return candidates.find((path) => existsSync(path));
}

function main(): void {
  const projectRoot = process.cwd();
  const reportDate = readFlag("--report-date") ?? todayDate();
  const publicFixture = readFlag("--public-fixture");
  const portfolioFixture = readFlag("--portfolio-fixture");
  const pollingEvidencePath = readFlag("--polling-evidence") ?? defaultPollingEvidencePath(projectRoot);
  const marketSnapshotPath = resolve(projectRoot, "data", "kalshi_snapshot", `${reportDate}.json`);
  const portfolioSnapshotPath = resolve(projectRoot, "data", "portfolio", `${reportDate}.json`);
  const reportJsonPath = resolve(GENERATED_REPORT_DIR, `${reportDate}.json`);
  const reportMarkdownPath = resolve(GENERATED_REPORT_DIR, `${reportDate}.md`);
  const latestMarkdownPath = resolve(GENERATED_REPORT_DIR, "latest.md");
  const archiveJsonPath = resolve(ARCHIVE_REPORT_DIR, `${reportDate}.json`);
  const archiveMarkdownPath = resolve(ARCHIVE_REPORT_DIR, `${reportDate}.md`);

  const publicCollectorArgs = [publicCollectorScript, "--output", marketSnapshotPath];
  if (publicFixture) {
    publicCollectorArgs.push("--fixture", publicFixture);
  }
  runCommand("python3", publicCollectorArgs);

  const portfolioCollectorArgs = [portfolioCollectorScript, "--output", portfolioSnapshotPath];
  if (portfolioFixture) {
    portfolioCollectorArgs.push("--fixture", portfolioFixture);
  }
  runCommand("python3", portfolioCollectorArgs);

  const reportGeneratorArgs = [
    reportGeneratorScript,
    "--market-snapshot",
    marketSnapshotPath,
    "--portfolio-snapshot",
    portfolioSnapshotPath,
    "--output",
    reportJsonPath,
    "--report-date",
    reportDate,
  ];
  if (pollingEvidencePath) {
    reportGeneratorArgs.push("--polling-evidence", pollingEvidencePath);
  }
  runCommand(tsxBinary, reportGeneratorArgs);

  const report = readReportFile(reportJsonPath);
  const archive = loadArchiveEntries({
    archiveDirectories: [ARCHIVE_REPORT_DIR],
    excludeDates: [report.reportDate],
  });
  const hydratedReport = {
    ...report,
    archive: archive.length > 0 ? archive : report.archive,
  };
  const markdown = renderDailyReportMarkdown(hydratedReport);
  const serializedReport = `${JSON.stringify(hydratedReport, null, 2)}\n`;

  writeTextFile(reportJsonPath, serializedReport);
  writeTextFile(reportMarkdownPath, `${markdown}\n`);
  writeTextFile(LATEST_REPORT_PATH, serializedReport);
  writeTextFile(latestMarkdownPath, `${markdown}\n`);
  writeTextFile(archiveJsonPath, serializedReport);
  writeTextFile(archiveMarkdownPath, `${markdown}\n`);

  process.stdout.write(
    `${JSON.stringify({
      marketSnapshot: marketSnapshotPath,
      portfolioSnapshot: portfolioSnapshotPath,
      reportJson: reportJsonPath,
      reportMarkdown: reportMarkdownPath,
      latestJson: LATEST_REPORT_PATH,
      latestMarkdown: latestMarkdownPath,
      archiveJson: archiveJsonPath,
      archiveMarkdown: archiveMarkdownPath,
      pollingEvidence: pollingEvidencePath ?? null,
      suggestedHermesCommand: `cd ${projectRoot} && npm run run:daily-report`,
    })}\n`,
  );
}

main();
