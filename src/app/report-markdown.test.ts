import assert from "node:assert/strict";
import test from "node:test";

import { sampleReports } from "./dashboard-data";
import { renderDailyReportMarkdown } from "./report-markdown";

test("renders a no-trade markdown brief with hold guidance and trading caveats", () => {
  const markdown = renderDailyReportMarkdown(sampleReports.noTradeDay);

  assert.match(markdown, /^# Arbiter Daily Report/m);
  assert.match(markdown, /No trade today/i);
  assert.match(markdown, /## Executive summary/);
  assert.match(markdown, /## Top opportunities/);
  assert.match(markdown, /No trade today\./);
  assert.match(markdown, /## Portfolio actions/);
  assert.match(markdown, /Hold/);
  assert.match(markdown, /## Caveats/);
  assert.match(markdown, /No automatic trading/i);
});

test("renders markdown with opportunities, position actions, and evidence links", () => {
  const markdown = renderDailyReportMarkdown(sampleReports.politicalEdgeDay);

  assert.match(markdown, /## Top opportunities/);
  assert.match(markdown, /Buy YES/);
  assert.match(markdown, /Watch/);
  assert.match(markdown, /## Portfolio actions/);
  assert.match(markdown, /Reduce/);
  assert.match(markdown, /Exit/);
  assert.match(markdown, /## Evidence links/);
  assert.match(markdown, /\[RCP generic ballot average\]\(https:\/\/www\.realclearpolling\.com\/\)/);
  assert.match(markdown, /\[F1ReplayTiming Monaco pace notes\]\(https:\/\/f1replaytiming\.com\/\)/);
});
