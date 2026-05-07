import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

import { getTopOpportunities } from "./dashboard-data";
import { ValidationError, parseDailyReport } from "./report-schema";

function readSampleReport(name: string): unknown {
  return JSON.parse(
    readFileSync(resolve(process.cwd(), "data", "reports", "sample", `${name}.json`), "utf8"),
  );
}

test("accepts the schema-valid sample reports", () => {
  for (const sampleName of ["no-trade-day", "political-edge-day", "portfolio-exit-day"]) {
    const report = parseDailyReport(readSampleReport(sampleName));

    assert.equal(report.reportDate.length > 0, true);
  }
});

test("rejects invalid reports with a useful path-based error message", () => {
  const invalidReport = parseDailyReport(readSampleReport("political-edge-day"));
  invalidReport.opportunities[0].action = "Trim profits";

  assert.throws(
    () => parseDailyReport(invalidReport),
    (error) =>
      error instanceof ValidationError &&
      /opportunities\[0\]\.action/.test(error.message) &&
      /RecommendationAction/.test(error.message),
  );
});

test("caps top opportunities at five highest-edge ideas", () => {
  const report = parseDailyReport(readSampleReport("political-edge-day"));

  const extendedReport = {
    ...report,
    opportunities: [
      ...report.opportunities,
      {
        ...report.opportunities[0],
        market: {
          ...report.opportunities[0].market,
          ticker: "EXTRA-LOW-EDGE-1",
          title: "Extra low edge idea 1",
        },
        title: "Extra low edge idea 1",
        edge: 2,
      },
      {
        ...report.opportunities[0],
        market: {
          ...report.opportunities[0].market,
          ticker: "EXTRA-LOW-EDGE-2",
          title: "Extra low edge idea 2",
        },
        title: "Extra low edge idea 2",
        edge: 1,
      },
    ],
  };

  const topOpportunities = getTopOpportunities(extendedReport);

  assert.equal(topOpportunities.length, 5);
  assert.deepEqual(
    topOpportunities.map((opportunity) => opportunity.market.ticker),
    [
      "HOUSE-DEM-2026",
      "SENATE-DEM-2026",
      "FEDCUT-SEP26",
      "F1-MONACO-LEC",
      "CPI-LOWER-JUL",
    ],
  );
});
