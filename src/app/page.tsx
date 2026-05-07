import {
  getTopOpportunities,
  mockDashboardReport,
  mockDashboardReportStatus,
  type DashboardReportStatus,
} from "./dashboard-data";
import type { DailyReport } from "./report-schema";
import {
  defaultPortfolioSnapshot,
  getPortfolioReviewCards,
  type PortfolioSnapshot,
} from "./portfolio-data";

const sectionLinks = [
  { href: "#today", label: "Today" },
  { href: "#opportunities", label: "Opportunities" },
  { href: "#portfolio", label: "Portfolio" },
  { href: "#evidence", label: "Evidence" },
  { href: "#archive", label: "Archive" },
];

const actionStyles = {
  "Buy YES": "border-[#6EE7B7]/45 bg-[#0E3A2D] text-[#BBF7D0]",
  "Buy NO": "border-[#F6C76B]/45 bg-[#4B3512] text-[#FCE7A8]",
  Hold: "border-[#3B82C4]/45 bg-[#132B63] text-[#CFE7FF]",
  Reduce: "border-[#F6C76B]/45 bg-[#4B3512] text-[#FCE7A8]",
  Exit: "border-[#FB7185]/45 bg-[#4A1222] text-[#FFD0D8]",
  Watch: "border-[#3B82C4]/45 bg-[#132B63] text-[#CFE7FF]",
  Pass: "border-[#3B82C4]/30 bg-[#121739] text-[#D7EAFE]",
} as const;

const reportStatusStyles = {
  generated: {
    shell: "border-[#6EE7B7]/28 bg-[linear-gradient(135deg,rgba(14,58,45,0.48),rgba(14,18,51,0.94))]",
    kicker: "text-[#A7F3D0]",
    badge: "border-[#6EE7B7]/30 bg-[#0A1E1A]/70 text-[#D8FFF0]",
  },
  archived: {
    shell: "border-[#3B82C4]/28 bg-[linear-gradient(135deg,rgba(19,43,99,0.45),rgba(14,18,51,0.94))]",
    kicker: "text-[#9ED4FF]",
    badge: "border-[#3B82C4]/30 bg-[#0A1538]/70 text-[#D7EDFF]",
  },
  sample: {
    shell: "border-[#F6C76B]/28 bg-[linear-gradient(135deg,rgba(75,53,18,0.48),rgba(14,18,51,0.94))]",
    kicker: "text-[#FCE7A8]",
    badge: "border-[#F6C76B]/30 bg-[#241806]/70 text-[#FCE7A8]",
  },
  error: {
    shell: "border-[#FB7185]/28 bg-[linear-gradient(135deg,rgba(74,18,34,0.5),rgba(14,18,51,0.94))]",
    kicker: "text-[#FFD0D8]",
    badge: "border-[#FB7185]/30 bg-[#2B0C17]/70 text-[#FFE2E8]",
  },
} as const;

function formatSignedCurrency(value: number): string {
  const sign = value >= 0 ? "+" : "-";

  return `${sign}$${Math.abs(value).toLocaleString()}`;
}

function formatPollingMarketType(value: string): string {
  switch (value) {
    case "binary-general":
      return "Binary general";
    case "multi-candidate-primary":
      return "Multi-candidate primary";
    case "top-two":
      return "Top-two";
    case "chamber-control":
      return "Chamber control";
    default:
      return "Unknown";
  }
}

type HomeProps = {
  report?: DailyReport;
  reportStatus?: DashboardReportStatus;
  portfolioSnapshot?: PortfolioSnapshot;
};

export default function Home({
  report = mockDashboardReport,
  reportStatus = mockDashboardReportStatus,
  portfolioSnapshot = defaultPortfolioSnapshot,
}: HomeProps) {
  const topOpportunities = getTopOpportunities(report);
  const portfolioCards = getPortfolioReviewCards(report, portfolioSnapshot);
  const pollingEvidence = report.pollingEvidence ?? [];
  const grossExposure = portfolioSnapshot.available
    ? portfolioSnapshot.positions.reduce((total, position) => total + (position.exposure ?? 0), 0)
    : report.portfolio.grossExposure;
  const unrealizedPnl = portfolioSnapshot.available
    ? portfolioSnapshot.positions.reduce((total, position) => total + (position.unrealizedPnl ?? 0), 0)
    : report.portfolio.unrealizedPnl;
  const cashAvailable = portfolioSnapshot.available
    ? (portfolioSnapshot.balance?.cashBalance ?? 0)
    : report.portfolio.cashAvailable;
  const riskPosture = portfolioSnapshot.available
    ? `Live portfolio snapshot${portfolioSnapshot.collectedAt ? ` · ${portfolioSnapshot.collectedAt}` : ""}`
    : report.portfolio.riskPosture;
  const reportStatusStyle = reportStatusStyles[reportStatus.state];
  const passCount = report.passes?.length ?? 0;

  return (
    <main className="min-h-[100dvh] bg-[radial-gradient(circle_at_top,#1E245F_0%,#0A0D2A_55%,#070819_100%)] px-5 py-8 text-[#F7F1E6] md:px-10 md:py-10">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <header className="overflow-hidden rounded-[32px] border border-[#3B82C4]/30 bg-[#0E1233]/92 shadow-[0_30px_80px_rgba(3,6,24,0.5)]">
          <div className="flex flex-col gap-8 px-6 py-6 md:px-8">
            <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
              <div className="max-w-3xl">
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[#9ED4FF]">
                  Arbiter private terminal
                </p>
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <h1 className="text-4xl font-semibold tracking-[-0.05em] text-white md:text-6xl">
                    Arbiter
                  </h1>
                  <span className="rounded-full border border-[#3B82C4]/40 bg-[#101947] px-3 py-1 text-xs font-medium uppercase tracking-[0.22em] text-[#D7EDFF]">
                    {report.reportLabel}
                  </span>
                </div>
                <p className="mt-5 max-w-2xl text-lg leading-8 text-[#EADFCB] md:text-xl">
                  Judge Kalshi prices against disciplined fair value, portfolio risk, and evidence
                  before risking capital.
                </p>
                <p className="mt-3 max-w-2xl text-base leading-7 text-[#CFE7FF]">
                  {report.thesis} The brief only surfaces the few setups worth attention and leaves
                  room for a clean pass.
                </p>
              </div>

              <div className="flex w-full max-w-[32rem] flex-col gap-3">
                <article className={`rounded-[26px] border p-5 ${reportStatusStyle.shell}`}>
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div className="max-w-lg">
                      <p
                        className={`text-xs font-semibold uppercase tracking-[0.24em] ${reportStatusStyle.kicker}`}
                      >
                        Latest report status
                      </p>
                      <h2 className="mt-2 text-2xl font-semibold text-white">{reportStatus.label}</h2>
                      <p className="mt-3 text-sm leading-6 text-[#F7F1E6]">{reportStatus.detail}</p>
                    </div>
                    <div className={`rounded-2xl border px-4 py-3 ${reportStatusStyle.badge}`}>
                      <p className="text-[11px] uppercase tracking-[0.2em] text-[#CFE7FF]">Source</p>
                      <p className="mt-2 text-sm font-semibold text-white">{reportStatus.sourceLabel}</p>
                      <p className="mt-2 text-xs uppercase tracking-[0.16em] text-[#CFE7FF]">
                        Report date {report.reportDate}
                      </p>
                    </div>
                  </div>
                </article>

                <div className="grid gap-3 sm:grid-cols-3">
                  {[
                    ["Generated", report.generatedAt],
                    ["Today list", `${topOpportunities.length} qualified ideas`],
                    [
                      "Portfolio feed",
                      portfolioSnapshot.available ? "Live portfolio snapshot" : "Portfolio unavailable",
                    ],
                  ].map(([label, value]) => (
                    <div
                      key={label}
                      className="rounded-2xl border border-[#3B82C4]/25 bg-[#11163D]/95 p-4"
                    >
                      <p className="text-xs uppercase tracking-[0.22em] text-[#9ED4FF]">{label}</p>
                      <p className="mt-2 text-sm leading-6 text-[#F7F1E6]">{value}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <nav className="flex flex-wrap gap-3">
              {sectionLinks.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  className="rounded-full border border-[#3B82C4]/35 bg-[#101947]/85 px-4 py-2 text-sm font-medium text-[#D7EDFF] transition hover:border-[#3B82C4] hover:text-white"
                >
                  {link.label}
                </a>
              ))}
            </nav>
          </div>
        </header>

        <section className="grid gap-4 md:grid-cols-4">
          {[
            ["Focus", "Top 3-5 opportunities only"],
            ["Discipline", "No trade today remains a valid output"],
            ["Venue", "Kalshi first, outside sources only as evidence"],
            [
              "Report feed",
              reportStatus.state === "generated" ? "Generated brief live" : reportStatus.label,
            ],
          ].map(([label, value]) => (
            <div key={label} className="rounded-2xl border border-[#3B82C4]/20 bg-[#10153A]/88 p-4">
              <p className="text-xs uppercase tracking-[0.2em] text-[#9ED4FF]">{label}</p>
              <p className="mt-2 text-sm leading-6 text-[#F0E6D3]">{value}</p>
            </div>
          ))}
        </section>

        <section id="today" className="grid gap-6 xl:grid-cols-[1.6fr_0.8fr]">
          <div className="rounded-[28px] border border-[#3B82C4]/25 bg-[#0E1233]/92 p-6">
            <div className="flex flex-col gap-3 border-b border-[#3B82C4]/20 pb-5 md:flex-row md:items-end md:justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.24em] text-[#9ED4FF]">Today</p>
                <h2 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-white">
                  Edge report
                </h2>
              </div>
              <p className="max-w-2xl text-sm leading-6 text-[#D7EAFE]">
                Arbiter is an edge filter, not a broad market screener. Every trade call needs a
                price gap, evidence, and a clear reason to act now.
              </p>
            </div>

            <div className="mt-6 grid gap-4 xl:grid-cols-2">
              {topOpportunities.length > 0 ? (
                topOpportunities.map((opportunity) => (
                  <article
                    key={opportunity.market.ticker}
                    className="rounded-[24px] border border-[#3B82C4]/22 bg-[#111741]/88 p-5"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-xs uppercase tracking-[0.22em] text-[#8FC5F4]">
                          {opportunity.market.ticker}
                        </p>
                        <h3 className="mt-2 text-xl font-semibold text-white">{opportunity.title}</h3>
                      </div>
                      <span
                        className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${
                          actionStyles[opportunity.action]
                        }`}
                      >
                        {opportunity.action}
                      </span>
                    </div>

                    <div className="mt-5 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                      <div className="rounded-2xl bg-[#0A0F2E] p-3">
                        <p className="text-xs uppercase tracking-[0.16em] text-[#8FC5F4]">
                          Kalshi price
                        </p>
                        <p className="mt-2 text-lg font-semibold text-[#F7F1E6]">
                          {opportunity.market.yesAskCents}c
                        </p>
                      </div>
                      <div className="rounded-2xl bg-[#0A0F2E] p-3">
                        <p className="text-xs uppercase tracking-[0.16em] text-[#8FC5F4]">
                          Marcus fair value
                        </p>
                        <p className="mt-2 text-lg font-semibold text-[#F7F1E6]">
                          {opportunity.marcusFairValue}c
                        </p>
                      </div>
                      <div className="rounded-2xl bg-[#0A0F2E] p-3">
                        <p className="text-xs uppercase tracking-[0.16em] text-[#8FC5F4]">Edge</p>
                        <p className="mt-2 text-lg font-semibold text-[#6EE7B7]">
                          +{opportunity.edge} pts
                        </p>
                      </div>
                      <div className="rounded-2xl bg-[#0A0F2E] p-3">
                        <p className="text-xs uppercase tracking-[0.16em] text-[#8FC5F4]">
                          Confidence
                        </p>
                        <p className="mt-2 text-lg font-semibold text-[#F7F1E6]">
                          {opportunity.confidence}
                        </p>
                      </div>
                    </div>

                    <div className="mt-5 grid gap-4 md:grid-cols-[1fr_auto]">
                      <div>
                        <p className="text-xs uppercase tracking-[0.18em] text-[#8FC5F4]">Reason</p>
                        <p className="mt-2 text-sm leading-6 text-[#EADFCB]">{opportunity.reason}</p>
                      </div>
                      <div className="rounded-2xl border border-[#3B82C4]/20 bg-[#0A0F2E] px-4 py-3 text-right">
                        <p className="text-xs uppercase tracking-[0.16em] text-[#8FC5F4]">
                          Evidence count
                        </p>
                        <p className="mt-2 text-2xl font-semibold text-white">
                          {opportunity.evidenceLinks.length}
                        </p>
                      </div>
                    </div>

                    <div className="mt-4 rounded-2xl border border-[#3B82C4]/20 bg-[#0A0F2E] p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-xs uppercase tracking-[0.16em] text-[#8FC5F4]">
                          Linked evidence
                        </p>
                        <p className="text-xs uppercase tracking-[0.16em] text-[#CFE7FF]">
                          {opportunity.evidenceLinks.length} source
                          {opportunity.evidenceLinks.length === 1 ? "" : "s"}
                        </p>
                      </div>

                      {opportunity.evidenceLinks.length > 0 ? (
                        <ul className="mt-3 space-y-3">
                          {opportunity.evidenceLinks.map((entry) => (
                            <li
                              key={`${opportunity.market.ticker}-${entry.href}`}
                              className="rounded-2xl border border-[#3B82C4]/15 bg-[#101947]/70 p-3"
                            >
                              <a
                                href={entry.href}
                                target="_blank"
                                rel="noreferrer"
                                className="text-sm font-semibold text-[#D7EDFF] transition hover:text-white"
                              >
                                {entry.label}
                              </a>
                              <p className="mt-2 text-xs uppercase tracking-[0.16em] text-[#8FC5F4]">
                                {entry.source}
                              </p>
                              <p className="mt-2 text-sm leading-6 text-[#DDEFFF]">{entry.note}</p>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="mt-3 text-sm leading-6 text-[#DDEFFF]">No linked evidence yet.</p>
                      )}
                    </div>

                    <div className="mt-4 rounded-2xl border border-[#F6C76B]/25 bg-[#3A2A10]/20 p-4">
                      <p className="text-xs uppercase tracking-[0.16em] text-[#F6C76B]">
                        What would change the view
                      </p>
                      <p className="mt-2 text-sm leading-6 text-[#F3E5C0]">
                        {opportunity.whatWouldChange}
                      </p>
                    </div>
                  </article>
                ))
              ) : (
                <article className="rounded-[28px] border border-[#6EE7B7]/30 bg-[linear-gradient(135deg,rgba(14,58,45,0.4),rgba(16,25,71,0.92))] p-6 xl:col-span-2">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <p className="text-xs uppercase tracking-[0.22em] text-[#A7F3D0]">
                        No trade today
                      </p>
                      <h3 className="mt-3 text-2xl font-semibold text-white">
                        Nothing cleared the evidence bar today.
                      </h3>
                    </div>
                    <p className="rounded-full border border-[#6EE7B7]/30 bg-[#0A1E1A]/80 px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-[#BBF7D0]">
                      {passCount > 0 ? `${passCount} markets passed` : "Capital preserved"}
                    </p>
                  </div>
                  <p className="mt-4 max-w-3xl text-sm leading-7 text-[#EADFCB]">
                    {report.summary} Keep capital flexible and spend the session on thesis review,
                    evidence refresh, and portfolio discipline instead of forcing exposure.
                  </p>
                  <div className="mt-5 grid gap-3 md:grid-cols-3">
                    {[
                      ["Capital stays optional", "No forced positions just to fill the report."],
                      [
                        passCount > 0 ? "Pass log" : "Evidence first",
                        passCount > 0
                          ? `${passCount} market${passCount === 1 ? "" : "s"} failed the current bar after review.`
                          : "Refresh the inputs before treating a weak setup as actionable.",
                      ],
                      ["Portfolio discipline", "Use the quiet session to clean up stale or crowded risk."],
                    ].map(([label, value]) => (
                      <div
                        key={label}
                        className="rounded-2xl border border-[#6EE7B7]/18 bg-[#0A1E1A]/55 p-4"
                      >
                        <p className="text-xs uppercase tracking-[0.16em] text-[#A7F3D0]">{label}</p>
                        <p className="mt-2 text-sm leading-6 text-[#E8FDF5]">{value}</p>
                      </div>
                    ))}
                  </div>
                </article>
              )}
            </div>
          </div>

          <aside className="grid gap-4">
            <section className="rounded-[28px] border border-[#6EE7B7]/25 bg-[#0E1233]/92 p-6">
              <p className="text-xs uppercase tracking-[0.24em] text-[#9ED4FF]">Report discipline</p>
              <h2 className="mt-2 text-2xl font-semibold text-white">No-trade policy</h2>
              <p className="mt-4 text-sm leading-7 text-[#EADFCB]">{report.noTradePolicy}</p>
            </section>

            <section
              id="opportunities"
              className="rounded-[28px] border border-[#3B82C4]/25 bg-[#0E1233]/92 p-6"
            >
              <p className="text-xs uppercase tracking-[0.24em] text-[#9ED4FF]">Opportunities</p>
              <h2 className="mt-2 text-2xl font-semibold text-white">What stays on watch</h2>

              {report.watchlist.length > 0 ? (
                <ul className="mt-5 space-y-4">
                  {report.watchlist.map((item) => (
                    <li
                      key={item}
                      className="rounded-2xl border border-[#3B82C4]/20 bg-[#101947]/90 px-4 py-3 text-sm leading-6 text-[#DDEFFF]"
                    >
                      {item}
                    </li>
                  ))}
                </ul>
              ) : (
                <article className="mt-5 rounded-2xl border border-[#3B82C4]/20 bg-[#101947]/90 p-4">
                  <p className="text-lg font-semibold text-white">Watchlist clear</p>
                  <p className="mt-3 text-sm leading-6 text-[#EADFCB]">
                    Nothing needs passive monitoring right now; the dashboard is cleanly in pass mode.
                  </p>
                </article>
              )}
            </section>
          </aside>
        </section>

        <section id="portfolio" className="rounded-[28px] border border-[#3B82C4]/25 bg-[#0E1233]/92 p-6">
          <div className="flex flex-col gap-3 border-b border-[#3B82C4]/20 pb-5 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-[#9ED4FF]">Portfolio</p>
              <h2 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-white">
                Existing risk review
              </h2>
            </div>
            <p className="max-w-2xl text-sm leading-6 text-[#D7EAFE]">
              Hold, reduce, and exit calls matter as much as new trades when the edge fades or
              concentration grows.
            </p>
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-[0.7fr_1.3fr]">
            <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-1">
              {[
                ["Gross exposure", `$${grossExposure.toLocaleString()}`],
                ["Unrealized P&L", formatSignedCurrency(unrealizedPnl)],
                ["Cash available", `$${cashAvailable.toLocaleString()}`],
              ].map(([label, value]) => (
                <div key={label} className="rounded-2xl border border-[#3B82C4]/20 bg-[#101947]/90 p-4">
                  <p className="text-xs uppercase tracking-[0.2em] text-[#8FC5F4]">{label}</p>
                  <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
                </div>
              ))}
              <div className="rounded-2xl border border-[#F6C76B]/25 bg-[#3A2A10]/20 p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-[#F6C76B]">Risk posture</p>
                <p className="mt-2 text-sm leading-6 text-[#F3E5C0]">{riskPosture}</p>
              </div>
              <div
                className={`rounded-2xl border p-4 ${
                  portfolioSnapshot.available
                    ? "border-[#6EE7B7]/25 bg-[#0E3A2D]/25"
                    : "border-[#FB7185]/25 bg-[#4A1222]/25"
                }`}
              >
                <p className="text-xs uppercase tracking-[0.2em] text-[#9ED4FF]">
                  {portfolioSnapshot.available ? "Live portfolio snapshot" : "Portfolio unavailable"}
                </p>
                <p className="mt-2 text-sm leading-6 text-[#F7F1E6]">
                  {portfolioSnapshot.available
                    ? "Read-only balance and positions came from the latest sanitized portfolio snapshot."
                    : portfolioSnapshot.warnings.join(" ")}
                </p>
                <p className="mt-3 text-xs uppercase tracking-[0.16em] text-[#CFE7FF]">
                  Source {portfolioSnapshot.source.baseUrl}
                </p>
              </div>
            </div>

            <div className="grid gap-4 xl:grid-cols-3">
              {portfolioCards.length > 0 ? (
                portfolioCards.map((position) => (
                  <article
                    key={position.ticker}
                    className="rounded-[24px] border border-[#3B82C4]/20 bg-[#101947]/90 p-5"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-xs uppercase tracking-[0.18em] text-[#8FC5F4]">
                          {position.ticker}
                        </p>
                        <h3 className="mt-2 text-lg font-semibold text-white">{position.title}</h3>
                      </div>
                      <span
                        className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${
                          actionStyles[position.action]
                        }`}
                      >
                        {position.action}
                      </span>
                    </div>

                    <div className="mt-5 grid gap-3 text-sm sm:grid-cols-3">
                      <div className="rounded-2xl bg-[#0A0F2E] p-3">
                        <p className="text-xs uppercase tracking-[0.16em] text-[#8FC5F4]">Exposure</p>
                        <p className="mt-2 text-lg font-semibold text-[#F7F1E6]">
                          ${position.exposure.toLocaleString()}
                        </p>
                      </div>
                      <div className="rounded-2xl bg-[#0A0F2E] p-3">
                        <p className="text-xs uppercase tracking-[0.16em] text-[#8FC5F4]">P&amp;L</p>
                        <p
                          className={`mt-2 text-lg font-semibold ${
                            position.pnl >= 0 ? "text-[#6EE7B7]" : "text-[#FB7185]"
                          }`}
                        >
                          {position.pnl >= 0 ? "+" : "-"}${Math.abs(position.pnl).toLocaleString()}
                        </p>
                      </div>
                      <div className="rounded-2xl bg-[#0A0F2E] p-3">
                        <p className="text-xs uppercase tracking-[0.16em] text-[#8FC5F4]">
                          Review source
                        </p>
                        <p className="mt-2 text-sm font-semibold text-[#F7F1E6]">
                          {position.sourceLabel}
                        </p>
                      </div>
                    </div>

                    <div className="mt-4 rounded-2xl border border-[#3B82C4]/18 bg-[#0A0F2E] p-4">
                      <p className="text-xs uppercase tracking-[0.16em] text-[#8FC5F4]">Review basis</p>
                      <p className="mt-2 text-sm leading-6 text-[#EADFCB]">{position.note}</p>
                    </div>

                    <div className="mt-4 rounded-2xl border border-[#3B82C4]/18 bg-[#0D1438] p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-xs uppercase tracking-[0.16em] text-[#8FC5F4]">
                          Evidence links
                        </p>
                        <p className="text-xs uppercase tracking-[0.16em] text-[#CFE7FF]">
                          {position.evidenceLinks.length} source
                          {position.evidenceLinks.length === 1 ? "" : "s"}
                        </p>
                      </div>

                      {position.evidenceLinks.length > 0 ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {position.evidenceLinks.map((link) => (
                            <a
                              key={`${position.ticker}-${link.href}`}
                              href={link.href}
                              target="_blank"
                              rel="noreferrer"
                              className="rounded-full border border-[#3B82C4]/28 bg-[#101947]/85 px-3 py-2 text-xs font-medium text-[#D7EDFF] transition hover:border-[#3B82C4] hover:text-white"
                            >
                              {link.label}
                            </a>
                          ))}
                        </div>
                      ) : (
                        <p className="mt-3 text-sm leading-6 text-[#DDEFFF]">No linked evidence yet.</p>
                      )}
                    </div>
                  </article>
                ))
              ) : (
                <article className="rounded-[24px] border border-[#3B82C4]/20 bg-[#101947]/90 p-5 xl:col-span-3">
                  <p className="text-lg font-semibold text-white">No live positions detected</p>
                  <p className="mt-3 text-sm leading-6 text-[#EADFCB]">
                    The account is readable, but there are no open positions to review right now.
                  </p>
                </article>
              )}
            </div>
          </div>
        </section>

        <section id="evidence" className="rounded-[28px] border border-[#3B82C4]/25 bg-[#0E1233]/92 p-6">
          <div className="flex flex-col gap-3 border-b border-[#3B82C4]/20 pb-5 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-[#9ED4FF]">Evidence</p>
              <h2 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-white">
                Polling, pace, and official sources
              </h2>
            </div>
            <p className="max-w-2xl text-sm leading-6 text-[#D7EAFE]">
              Polling summaries should anchor political calls before any narrative gets a vote.
            </p>
          </div>

          {pollingEvidence.length > 0 ? (
            <div className="mt-6 grid gap-4 xl:grid-cols-2">
              {pollingEvidence.map((entry) => (
                <article
                  key={entry.market_key}
                  className="rounded-[24px] border border-[#6EE7B7]/20 bg-[#101947]/90 p-5"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.18em] text-[#8FC5F4]">
                        {formatPollingMarketType(entry.market_type)}
                      </p>
                      <h3 className="mt-2 text-xl font-semibold text-white">{entry.race}</h3>
                    </div>
                    <p className="rounded-full border border-[#6EE7B7]/30 bg-[#0E3A2D]/25 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-[#BBF7D0]">
                      {entry.polling_average.leader} +{entry.polling_average.spread}
                    </p>
                  </div>

                  <div className="mt-5 grid gap-3 md:grid-cols-2">
                    <div className="rounded-2xl bg-[#0A0F2E] p-3">
                      <p className="text-xs uppercase tracking-[0.16em] text-[#8FC5F4]">Polling average</p>
                      <p className="mt-2 text-sm leading-6 text-[#F7F1E6]">
                        {entry.polling_average.leader} {entry.polling_average.leader_share} -{" "}
                        {entry.polling_average.runner_up} {entry.polling_average.runner_up_share}
                      </p>
                    </div>
                    <div className="rounded-2xl bg-[#0A0F2E] p-3">
                      <p className="text-xs uppercase tracking-[0.16em] text-[#8FC5F4]">Latest poll</p>
                      <p className="mt-2 text-sm leading-6 text-[#F7F1E6]">
                        {entry.latest_polls[0]?.pollster ?? "Polling table"} · {entry.latest_polls[0]?.spread ?? "n/a"}
                      </p>
                    </div>
                  </div>

                  <p className="mt-4 text-sm leading-6 text-[#EADFCB]">{entry.trend_summary}</p>

                  <div className="mt-4 flex flex-wrap gap-3">
                    {entry.evidence_links.map((link) => (
                      <a
                        key={`${entry.market_key}-${link.href}`}
                        href={link.href}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded-full border border-[#3B82C4]/30 bg-[#0A0F2E] px-3 py-2 text-xs font-medium text-[#D7EDFF] transition hover:border-[#3B82C4] hover:text-white"
                      >
                        {link.label}
                      </a>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <article className="mt-6 rounded-[24px] border border-[#F6C76B]/25 bg-[#101947]/90 p-5">
              <p className="text-xs uppercase tracking-[0.18em] text-[#F6C76B]">Polling refresh pending</p>
              <h3 className="mt-3 text-xl font-semibold text-white">Political evidence shelf is quiet</h3>
              <p className="mt-3 text-sm leading-6 text-[#F3E5C0]">
                The dashboard can still render the brief, but no saved polling summaries were attached
                to this report yet.
              </p>
            </article>
          )}

          <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {report.evidence.length > 0 ? (
              report.evidence.map((entry) => (
                <a
                  key={entry.label}
                  href={entry.href}
                  target="_blank"
                  rel="noreferrer"
                  className="group rounded-[24px] border border-[#3B82C4]/20 bg-[#101947]/90 p-5 transition hover:border-[#3B82C4] hover:bg-[#132055]"
                >
                  <div className="flex items-start justify-between gap-4">
                    <p className="text-xs uppercase tracking-[0.18em] text-[#8FC5F4]">{entry.source}</p>
                    <span className="rounded-full border border-[#3B82C4]/25 bg-[#0A0F2E]/85 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-[#CFE7FF]">
                      Reference
                    </span>
                  </div>
                  <h3 className="mt-3 text-lg font-semibold text-white">{entry.label}</h3>
                  <p className="mt-4 text-sm leading-6 text-[#EADFCB]">{entry.note}</p>
                  <p className="mt-4 text-xs uppercase tracking-[0.18em] text-[#9ED4FF]">
                    Open evidence shelf
                  </p>
                </a>
              ))
            ) : (
              <article className="rounded-[24px] border border-[#3B82C4]/20 bg-[#101947]/90 p-5 md:col-span-2 xl:col-span-4">
                <p className="text-lg font-semibold text-white">Evidence refresh pending</p>
                <p className="mt-3 text-sm leading-6 text-[#EADFCB]">
                  This report is still usable, but the shared evidence shelf has not been populated yet.
                </p>
              </article>
            )}
          </div>
        </section>

        <section id="archive" className="rounded-[28px] border border-[#3B82C4]/25 bg-[#0E1233]/92 p-6">
          <div className="flex flex-col gap-3 border-b border-[#3B82C4]/20 pb-5 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-[#9ED4FF]">Archive</p>
              <h2 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-white">
                Prior daily reports
              </h2>
            </div>
            <p className="max-w-2xl text-sm leading-6 text-[#D7EAFE]">
              The archive should make it easy to review prior theses, passes, and portfolio cleanup
              calls.
            </p>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {report.archive.length > 0 ? (
              report.archive.map((entry) => (
                <article
                  key={entry.date}
                  className="flex h-full flex-col rounded-[24px] border border-[#3B82C4]/20 bg-[#101947]/90 p-5"
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-xs uppercase tracking-[0.18em] text-[#8FC5F4]">{entry.date}</p>
                    <span className="rounded-full border border-[#3B82C4]/25 bg-[#0A0F2E]/85 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-[#CFE7FF]">
                      Archive
                    </span>
                  </div>
                  <h3 className="mt-3 text-xl font-semibold text-white">{entry.headline}</h3>
                  <p className="mt-4 flex-1 text-sm leading-6 text-[#EADFCB]">{entry.summary}</p>
                  <div className="mt-5 rounded-2xl border border-[#3B82C4]/20 bg-[#0A0F2E] px-4 py-3">
                    <p className="text-xs uppercase tracking-[0.16em] text-[#8FC5F4]">Verdict</p>
                    <p className="mt-2 text-sm leading-6 text-[#DDEFFF]">{entry.verdict}</p>
                  </div>
                </article>
              ))
            ) : (
              <article className="rounded-[24px] border border-[#3B82C4]/20 bg-[#101947]/90 p-5 md:col-span-3">
                <p className="text-xs uppercase tracking-[0.18em] text-[#8FC5F4]">Archive pending</p>
                <h3 className="mt-3 text-xl font-semibold text-white">The latest daily report is ready</h3>
                <p className="mt-4 text-sm leading-6 text-[#EADFCB]">
                  The latest daily report is ready, but there are no prior archived briefs yet.
                </p>
              </article>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
