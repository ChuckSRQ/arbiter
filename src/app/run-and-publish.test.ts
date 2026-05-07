import assert from "node:assert/strict";
import test from "node:test";

import { sampleReports } from "./dashboard-data";
import { buildPublishSummary, revalidateDashboard } from "../../scripts/run_and_publish.ts";

test("buildPublishSummary reports counts and a concise publish summary", () => {
  const report = {
    ...sampleReports.politicalEdgeDay,
    opportunities: sampleReports.politicalEdgeDay.opportunities.slice(0, 3),
    portfolio: {
      ...sampleReports.politicalEdgeDay.portfolio,
      positions: sampleReports.politicalEdgeDay.portfolio.positions.slice(0, 2),
    },
  };

  assert.deepEqual(buildPublishSummary(report, "ok"), {
    reportDate: "2026-05-06",
    reportLabel: "Political edge brief",
    opportunitiesCount: 3,
    positionActionsCount: 1,
    summary: "3 trade ideas, 1 position action",
    revalidateStatus: "ok",
  });
});

test("revalidateDashboard returns failed when the cache bust request rejects", async () => {
  const status = await revalidateDashboard(async () => {
    throw new Error("connect ECONNREFUSED");
  });

  assert.equal(status, "failed");
});
