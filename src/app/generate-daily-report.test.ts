import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

test("generate_daily_report accepts polling evidence input and keeps evidence links in the report", () => {
  const tempRoot = mkdtempSync(join(tmpdir(), "arbiter-generate-report-"));

  try {
    const dataDir = join(tempRoot, "data");
    const marketSnapshotPath = join(dataDir, "kalshi_snapshot", "2026-05-06.json");
    const portfolioSnapshotPath = join(dataDir, "portfolio", "2026-05-06.json");
    const pollingEvidencePath = join(dataDir, "polling_evidence", "sample.json");
    const outputPath = join(dataDir, "reports", "generated", "2026-05-06.json");

    mkdirSync(join(dataDir, "kalshi_snapshot"), { recursive: true });
    mkdirSync(join(dataDir, "portfolio"), { recursive: true });
    mkdirSync(join(dataDir, "polling_evidence"), { recursive: true });

    writeFileSync(
      marketSnapshotPath,
      `${JSON.stringify({
        collected_at: "2026-05-06T20:30:00Z",
        source: {
          base_url: "https://api.elections.kalshi.com/trade-api/v2",
          endpoint: "/markets",
        },
        markets: [
          {
            ticker: "OH-SEN-GEN-BROWN",
            title: "Ohio Senate general: Brown vs Husted",
            category: "Politics",
            close_time: "2026-11-03T05:00:00Z",
            expiration_time: "2026-11-03T05:00:00Z",
            yes_bid_cents: 52,
            yes_ask_cents: 54,
            no_bid_cents: 46,
            no_ask_cents: 48,
          },
        ],
      }, null, 2)}\n`,
      "utf8",
    );
    writeFileSync(
      portfolioSnapshotPath,
      `${JSON.stringify({
        collected_at: "2026-05-06T20:40:00Z",
        source: {
          base_url: "https://api.elections.kalshi.com/trade-api/v2",
        },
        available: true,
        balance: {
          cash_balance: 5300,
          withdrawable_balance: 5000,
          portfolio_value: 10120,
        },
        positions: [],
        warnings: [],
      }, null, 2)}\n`,
      "utf8",
    );
    writeFileSync(
      pollingEvidencePath,
      `${JSON.stringify({
        evidence: [
          {
            collected_at: "2026-05-06T19:30:00Z",
            source_url: "https://www.realclearpolling.com/",
            race: "Ohio Senate general",
            market_key: "ohio-senate-general",
            market_type: "binary-general",
            polling_average: {
              updated_at: "2026-05-06T19:00:00Z",
              leader: "Sherrod Brown",
              leader_share: 48,
              runner_up: "Jon Husted",
              runner_up_share: 45,
              spread: 3,
              fair_yes_cents: 61,
            },
            latest_polls: [
              {
                pollster: "Marist",
                dates: {
                  start: "2026-05-01",
                  end: "2026-05-03",
                },
                sample: "Likely voters 912",
                toplines: [
                  { candidate: "Sherrod Brown", pct: 48 },
                  { candidate: "Jon Husted", pct: 45 },
                ],
                spread: "Brown +3",
              },
            ],
            trend_summary: "Brown still holds a narrow lead in the latest public polling.",
            evidence_links: [
              {
                label: "RCP Ohio Senate average",
                href: "https://www.realclearpolling.com/polls/senate/general/2026/ohio/brown-vs-husted",
                source: "Polling",
                note: "Ohio Senate general polling average.",
              },
            ],
          },
        ],
      }, null, 2)}\n`,
      "utf8",
    );

    execFileSync(
      "node",
      [
        "--import",
        "tsx",
        "scripts/generate_daily_report.ts",
        "--market-snapshot",
        marketSnapshotPath,
        "--portfolio-snapshot",
        portfolioSnapshotPath,
        "--polling-evidence",
        pollingEvidencePath,
        "--output",
        outputPath,
      ],
      {
        cwd: process.cwd(),
        stdio: "pipe",
      },
    );

    const report = JSON.parse(readFileSync(outputPath, "utf8")) as {
      evidence: Array<{ href: string }>;
      opportunities: Array<{ evidenceLinks: Array<{ href: string }> }>;
      pollingEvidence?: Array<{ market_key: string }>;
    };

    assert.equal(report.opportunities[0]?.evidenceLinks[0]?.href.includes("realclearpolling.com"), true);
    assert.equal(report.evidence.some((entry) => entry.href.includes("realclearpolling.com")), true);
    assert.equal(report.pollingEvidence?.[0]?.market_key, "ohio-senate-general");
  } finally {
    rmSync(tempRoot, { recursive: true, force: true });
  }
});
