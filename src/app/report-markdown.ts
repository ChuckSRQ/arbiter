import type { DailyReport, EvidenceLink, PositionReview } from "./report-schema";

function renderOpportunityLine(report: DailyReport): string[] {
  if (report.opportunities.length === 0) {
    return ["No trade today.", "", `${report.summary}`];
  }

  return report.opportunities.map(
    (opportunity) =>
      `- **${opportunity.action}** ${opportunity.market.ticker} - ${opportunity.title} (${opportunity.market.yesAskCents}c vs ${opportunity.marcusFairValue}c fair value, ${opportunity.edge} pt edge, ${opportunity.confidence} confidence). ${opportunity.reason}`,
  );
}

function renderPortfolioLine(position: PositionReview): string {
  return `- **${position.action}** ${position.market.ticker} - ${position.title} ($${position.exposure.toLocaleString()} exposure, ${position.pnl >= 0 ? "+" : "-"}$${Math.abs(position.pnl).toLocaleString()} P/L). ${position.reason ?? position.note}`;
}

function renderEvidenceLine(link: EvidenceLink): string {
  return `- [${link.label}](${link.href}) - ${link.source}. ${link.note}`;
}

export function renderDailyReportMarkdown(report: DailyReport): string {
  const portfolioLines =
    report.portfolio.positions.length > 0
      ? report.portfolio.positions.map((position) => renderPortfolioLine(position))
      : ["- No live positions were available for review."];
  const evidenceLines =
    report.evidence.length > 0
      ? report.evidence.map((link) => renderEvidenceLine(link))
      : ["- Evidence refresh pending."];

  return [
    "# Arbiter Daily Report",
    "",
    `- **Report date:** ${report.reportDate}`,
    `- **Generated:** ${report.generatedAt}`,
    `- **Label:** ${report.reportLabel}`,
    "",
    "## Executive summary",
    "",
    report.summary,
    "",
    "## Top opportunities",
    "",
    ...renderOpportunityLine(report),
    "",
    "## Portfolio actions",
    "",
    ...portfolioLines,
    "",
    "## Evidence links",
    "",
    ...evidenceLines,
    "",
    "## Caveats",
    "",
    `- ${report.noTradePolicy}`,
    "- No automatic trading. Use this brief for manual review only.",
    "",
  ].join("\n");
}
