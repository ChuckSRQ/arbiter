import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";

import { loadDashboardPageData, loadLatestDashboardReport, sampleReports } from "./dashboard-data";

test("run_daily_report works in fixture mode without credentials and writes latest pointers plus archive files", () => {
  const tempRoot = mkdtempSync(join(tmpdir(), "arbiter-daily-runner-"));
  const repoRoot = process.cwd();

  try {
    const output = execFileSync(
      resolve(repoRoot, "node_modules", ".bin", "tsx"),
      [
        resolve(repoRoot, "scripts", "run_daily_report.ts"),
        "--public-fixture",
        resolve(repoRoot, "tests", "fixtures", "kalshi_public_markets_pages.json"),
        "--polling-evidence",
        resolve(repoRoot, "data", "polling_evidence", "sample.json"),
        "--report-date",
        "2026-05-06",
      ],
      {
        cwd: tempRoot,
        env: {
          ...process.env,
          KALSHI_API_KEY_ID: "",
          KALSHI_PRIVATE_KEY_PATH: "",
        },
        stdio: "pipe",
      },
    ).toString("utf8");

    const expectedFiles = [
      join(tempRoot, "data", "kalshi_snapshot", "2026-05-06.json"),
      join(tempRoot, "data", "portfolio", "2026-05-06.json"),
      join(tempRoot, "data", "reports", "generated", "2026-05-06.json"),
      join(tempRoot, "data", "reports", "generated", "2026-05-06.md"),
      join(tempRoot, "data", "reports", "generated", "latest.json"),
      join(tempRoot, "data", "reports", "generated", "latest.md"),
      join(tempRoot, "reports", "2026-05-06.json"),
      join(tempRoot, "reports", "2026-05-06.md"),
    ];

    for (const filePath of expectedFiles) {
      assert.equal(existsSync(filePath), true, `${filePath} should exist`);
    }

    const latestReport = JSON.parse(
      readFileSync(join(tempRoot, "data", "reports", "generated", "latest.json"), "utf8"),
    ) as {
      reportDate: string;
      archive: Array<{ date: string }>;
    };

    const latestMarkdown = readFileSync(join(tempRoot, "data", "reports", "generated", "latest.md"), "utf8");

    assert.equal(latestReport.reportDate, "2026-05-06");
    assert.match(latestMarkdown, /No automatic trading/i);
    assert.match(output, /"latestJson"/);
  } finally {
    rmSync(tempRoot, { recursive: true, force: true });
  }
});

test("loadLatestDashboardReport prefers the latest pointer and hydrates archive cards from report files", () => {
  const tempRoot = mkdtempSync(join(tmpdir(), "arbiter-report-archive-"));

  try {
    const generatedDir = join(tempRoot, "data", "reports", "generated");
    const archiveDir = join(tempRoot, "reports");
    mkdirSync(generatedDir, { recursive: true });
    mkdirSync(archiveDir, { recursive: true });

    writeFileSync(
      join(generatedDir, "latest.json"),
      JSON.stringify({ ...sampleReports.noTradeDay, archive: [] }, null, 2),
      "utf8",
    );
    writeFileSync(
      join(archiveDir, "2026-05-05.json"),
      JSON.stringify(
        {
          ...sampleReports.portfolioExitDay,
          reportDate: "2026-05-05",
        },
        null,
        2,
      ),
      "utf8",
    );

    const report = loadLatestDashboardReport({
      currentReportPath: join(generatedDir, "latest.json"),
      reportDirectories: [generatedDir],
      archiveDirectories: [archiveDir],
    });

    assert.equal(report?.reportLabel, "No trade day");
    assert.equal(report?.archive[0]?.date, "2026-05-05");
    assert.match(report?.archive[0]?.headline ?? "", /Portfolio cleanup/i);
  } finally {
    rmSync(tempRoot, { recursive: true, force: true });
  }
});

test("loadDashboardPageData falls back to a safe sample when the latest report is invalid", () => {
  const tempRoot = mkdtempSync(join(tmpdir(), "arbiter-report-fallback-"));

  try {
    const generatedDir = join(tempRoot, "data", "reports", "generated");
    mkdirSync(generatedDir, { recursive: true });
    writeFileSync(join(generatedDir, "latest.json"), "{not-valid-json", "utf8");

    const pageData = loadDashboardPageData({
      currentReportPath: join(generatedDir, "latest.json"),
      reportDirectories: [generatedDir],
      archiveDirectories: [],
      fallbackReport: sampleReports.noTradeDay,
    });

    assert.equal(pageData.report.reportLabel, "No trade day");
    assert.equal(pageData.reportStatus.state, "error");
    assert.match(pageData.reportStatus.label, /needs review/i);
    assert.match(pageData.reportStatus.sourceLabel, /Fallback after load error/i);
  } finally {
    rmSync(tempRoot, { recursive: true, force: true });
  }
});
