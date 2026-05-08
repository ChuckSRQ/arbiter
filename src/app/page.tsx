import {
  getTopOpportunities,
  mockDashboardReport,
} from "./dashboard-data";
import {
  getPortfolioReviewCards,
  defaultPortfolioSnapshot,
  type PortfolioSnapshot,
} from "./portfolio-data";
import type { DailyReport, Opportunity, PassDecision } from "./report-schema";
import type { PortfolioReviewCard } from "./portfolio-data";

export const revalidate = 60;

// ─── Action badge styles ──────────────────────────────────────────────────────

const actionBadgeStyles = {
  "Buy YES": "bg-[rgba(59,130,246,0.15)] text-[#93C5FD] border border-[rgba(59,130,246,0.4)]",
  "Buy NO": "bg-[rgba(251,191,36,0.12)] text-[#FDE68A] border border-[rgba(251,191,36,0.4)]",
  Hold: "bg-[rgba(59,130,246,0.12)] text-[#93C5FD] border border-[rgba(59,130,246,0.4)]",
  Reduce: "bg-[rgba(251,191,36,0.12)] text-[#FDE68A] border border-[rgba(251,191,36,0.4)]",
  Exit: "bg-[rgba(251,191,36,0.12)] text-[#FB7185] border border-[rgba(251,191,36,0.4)]",
  Watch: "bg-[rgba(59,130,246,0.12)] text-[#93C5FD] border border-[rgba(59,130,246,0.4)]",
  Pass: "bg-[rgba(59,130,246,0.08)] text-[#60A5FA] border border-[rgba(59,130,246,0.25)]",
} as const;

// ─── Ticker badge ─────────────────────────────────────────────────────────────

function TickerBadge({ ticker }: { ticker: string }) {
  return (
    <span className="inline-block rounded-[6px] bg-[rgba(59,130,246,0.15)] px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#60A5FA] border border-[rgba(59,130,246,0.3)]">
      {ticker}
    </span>
  );
}

// ─── Price box variants ────────────────────────────────────────────────────────

function PriceBoxMarket({ value }: { value: string }) {
  return (
    <div className="flex flex-col items-center rounded-[12px] bg-[#05081A] px-3 py-3 text-center border border-[rgba(59,130,246,0.55)]"
      style={{ boxShadow: "0 0 14px rgba(59,130,246,0.12), inset 0 0 8px rgba(59,130,246,0.06)" }}>
      <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#60A5FA]">Market</span>
      <span className="mt-1 text-[22px] font-bold text-[#93C5FD]">{value}</span>
    </div>
  );
}

function PriceBoxEdge({ value }: { value: string }) {
  return (
    <div className="flex flex-col items-center rounded-[12px] bg-[#05081A] px-4 py-3.5 text-center border border-[rgba(251,191,36,0.6)]"
      style={{ boxShadow: "0 0 18px rgba(251,191,36,0.18), inset 0 0 10px rgba(251,191,36,0.08)" }}>
      <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#FCD34D]">Edge</span>
      <span className="mt-1 text-[22px] font-bold text-[#FDE68A]">{value}</span>
    </div>
  );
}

function PriceBoxMarcus({ value }: { value: string }) {
  return (
    <div className="flex flex-col items-center rounded-[12px] bg-[#05081A] px-3 py-3 text-center border border-[rgba(251,191,36,0.55)]"
      style={{ boxShadow: "0 0 14px rgba(251,191,36,0.12), inset 0 0 8px rgba(251,191,36,0.06)" }}>
      <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#60A5FA]">Marcus</span>
      <span className="mt-1 text-[22px] font-bold text-[#FDE68A]">{value}</span>
    </div>
  );
}

// ─── Opportunity card ─────────────────────────────────────────────────────────

function OpportunityCard({ opp }: { opp: Opportunity }) {
  const edgeStr = opp.edge > 0 ? `+${opp.edge} pts` : "—";

  return (
    <article className="flex flex-col rounded-[20px] bg-[#141828] p-[18px]">
      {/* Badge row */}
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <TickerBadge ticker={opp.market.ticker} />
        <span className="inline-block rounded-[6px] bg-[rgba(59,130,246,0.08)] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#60A5FA] border border-[rgba(59,130,246,0.2)]">
          {opp.market.category}
        </span>
        <span className={`ml-auto inline-block rounded-full px-3 py-1 text-[10px] font-bold uppercase tracking-[0.14em] ${actionBadgeStyles[opp.action]}`}>
          {opp.action}
        </span>
      </div>

      {/* Race title */}
      <h2 className="text-[20px] font-bold leading-tight text-[#F1F5F9]">{opp.title}</h2>

      {/* Election date */}
      <p className="mt-1 text-[13px] font-medium text-[#60A5FA]">{opp.market.expiresAt}</p>

      {/* Context paragraph */}
      <p className="mt-3 text-[14px] leading-[1.65] text-[#E8E4DC]">
        {opp.reason.length > 160 ? opp.reason.slice(0, 157) + "…" : opp.reason}
      </p>

      {/* Price row */}
      <div className="mt-4 flex items-center justify-center gap-[10px]">
        <PriceBoxMarket value={`${opp.market.yesAskCents}¢`} />
        <PriceBoxEdge value={edgeStr} />
        <PriceBoxMarcus value={`${opp.marcusFairValue}¢`} />
      </div>

      {/* Analysis */}
      <div className="mt-4">
        <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#FCD34D]">Analysis</p>
        <p className="mt-1.5 text-[13px] leading-[1.65] text-[#E8E4DC]">
          {opp.whatWouldChange}
        </p>
      </div>

      {/* Source links */}
      {opp.evidenceLinks.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {opp.evidenceLinks.map((link, i) => (
            <a
              key={i}
              href={link.href}
              target="_blank"
              rel="noreferrer"
              className="inline-block rounded-[6px] bg-[rgba(59,130,246,0.08)] px-3 py-1.5 text-[11px] font-medium text-[#60A5FA] border border-[rgba(59,130,246,0.2)] transition hover:border-[rgba(59,130,246,0.5)] hover:text-[#93C5FD]"
            >
              {link.label}
            </a>
          ))}
        </div>
      )}
    </article>
  );
}

// ─── No-trade card ─────────────────────────────────────────────────────────────

function NoTradeCard({ report }: { report: DailyReport }) {
  const passCount = report.passes?.length ?? 0;

  return (
    <article className="flex flex-col items-center rounded-[20px] bg-[#141828] p-[28px] text-center">
      <div className="inline-block rounded-full bg-[rgba(59,130,246,0.08)] px-4 py-1.5 mb-4 border border-[rgba(59,130,246,0.2)]">
        <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#60A5FA]">No trade today</span>
      </div>
      <h2 className="text-[22px] font-bold text-[#F1F5F9]">Nothing cleared the evidence bar.</h2>
      <p className="mt-3 text-[14px] leading-[1.65] text-[#E8E4DC] max-w-md">
        {report.summary}
      </p>
      {passCount > 0 && (
        <span className="mt-4 inline-block rounded-full bg-[rgba(251,191,36,0.1)] px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-[#FCD34D] border border-[rgba(251,191,36,0.3)]">
          {passCount} market{passCount === 1 ? "" : "s"} passed
        </span>
      )}
    </article>
  );
}

// ─── Portfolio card ────────────────────────────────────────────────────────────

function PortfolioCard({ pos }: { pos: PortfolioReviewCard }) {
  const pnlStr = pos.pnl >= 0 ? `+$${pos.pnl.toLocaleString()}` : `-$${Math.abs(pos.pnl).toLocaleString()}`;
  const pnlColor = pos.pnl >= 0 ? "text-[#6EE7B7]" : "text-[#FB7185]";

  return (
    <article className="flex flex-col rounded-[20px] bg-[#141828] p-[18px]">
      {/* Badge row */}
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <TickerBadge ticker={pos.ticker} />
        <span className={`ml-auto inline-block rounded-full px-3 py-1 text-[10px] font-bold uppercase tracking-[0.14em] ${actionBadgeStyles[pos.action]}`}>
          {pos.action}
        </span>
      </div>

      {/* Title */}
      <h2 className="text-[18px] font-bold leading-tight text-[#F1F5F9]">{pos.title}</h2>

      {/* Price row */}
      <div className="mt-4 flex items-center justify-center gap-[10px]">
        {/* Source */}
        <div className="flex flex-col items-center rounded-[12px] bg-[#05081A] px-3 py-3 text-center border border-[rgba(59,130,246,0.55)]"
          style={{ boxShadow: "0 0 14px rgba(59,130,246,0.12), inset 0 0 8px rgba(59,130,246,0.06)" }}>
          <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#60A5FA]">Source</span>
          <span className="mt-1 text-[15px] font-bold text-[#93C5FD] truncate max-w-[80px]">{pos.sourceLabel}</span>
        </div>
        {/* P&L */}
        <div className="flex flex-col items-center rounded-[12px] bg-[#05081A] px-3 py-3 text-center border border-[rgba(251,191,36,0.55)]"
          style={{ boxShadow: "0 0 14px rgba(251,191,36,0.12), inset 0 0 8px rgba(251,191,36,0.06)" }}>
          <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#FCD34D]">P&L</span>
          <span className={`mt-1 text-[20px] font-bold ${pnlColor}`}>{pnlStr}</span>
        </div>
        {/* Exposure */}
        <div className="flex flex-col items-center rounded-[12px] bg-[#05081A] px-3 py-3 text-center border border-[rgba(59,130,246,0.55)]"
          style={{ boxShadow: "0 0 14px rgba(59,130,246,0.12), inset 0 0 8px rgba(59,130,246,0.06)" }}>
          <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#60A5FA]">Exposure</span>
          <span className="mt-1 text-[20px] font-bold text-[#93C5FD]">${pos.exposure.toLocaleString()}</span>
        </div>
      </div>

      {/* Note */}
      <p className="mt-4 text-[13px] leading-[1.65] text-[#E8E4DC]">{pos.note}</p>

      {/* Evidence links */}
      {pos.evidenceLinks.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {pos.evidenceLinks.map((link, i) => (
            <a
              key={i}
              href={link.href}
              target="_blank"
              rel="noreferrer"
              className="inline-block rounded-[6px] bg-[rgba(59,130,246,0.08)] px-3 py-1.5 text-[11px] font-medium text-[#60A5FA] border border-[rgba(59,130,246,0.2)] transition hover:border-[rgba(59,130,246,0.5)] hover:text-[#93C5FD]"
            >
              {link.label}
            </a>
          ))}
        </div>
      )}
    </article>
  );
}

// ─── Pass pill ─────────────────────────────────────────────────────────────────

function PassPill({ pass }: { pass: PassDecision }) {
  return (
    <span className="inline-block rounded-[8px] bg-[#141828] px-3 py-2 text-[11px] text-[#60A5FA] border border-[rgba(59,130,246,0.2)]">
      {pass.market.ticker}
    </span>
  );
}

// ─── Live dot ──────────────────────────────────────────────────────────────────

function LiveDot() {
  return (
    <span className="relative flex h-2 w-2">
      <span className="absolute inline-flex h-full w-full rounded-full" style={{ background: "#FBBF24", opacity: 0.4, animation: "pulse 2s ease-in-out infinite" }} />
      <span className="relative inline-flex h-2 w-2 rounded-full" style={{ background: "#FBBF24" }} />
    </span>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

type HomeProps = {
  report?: DailyReport;
  portfolioSnapshot?: PortfolioSnapshot;
};

export default function Home({
  report = mockDashboardReport,
  portfolioSnapshot = defaultPortfolioSnapshot,
}: HomeProps) {
  const topOpps = getTopOpportunities(report);
  const portfolioCards = getPortfolioReviewCards(report, portfolioSnapshot);
  const passes = (report.passes ?? []).slice(0, 8);

  return (
    <div className="min-h-[100dvh] bg-[#0D0F1A]">
      {/* Sticky header */}
      <header className="sticky top-0 z-50 bg-[#0D0F1A] border-b border-[rgba(59,130,246,0.15)]">
        <div className="flex items-center justify-between px-[18px] py-3">
          <h1 className="text-[22px] font-bold text-[#F1F5F9] tracking-tight">Arbiter</h1>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <LiveDot />
              <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#FCD34D]">Live</span>
            </div>
            <span className="text-[11px] font-medium text-[#60A5FA]">{report.reportDate}</span>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="px-4 py-6 lg:px-8 lg:py-8">

        {/* Opportunities section */}
        <section>
          {topOpps.length > 0 ? (
            <div className="grid gap-4 sm:grid-cols-2 min-[1200px]:grid-cols-3">
              {topOpps.map((opp) => (
                <OpportunityCard key={opp.market.ticker} opp={opp} />
              ))}
            </div>
          ) : (
            <NoTradeCard report={report} />
          )}
        </section>

        {/* Portfolio section */}
        {portfolioCards.length > 0 && (
          <section className="mt-8">
            <p className="mb-4 text-[11px] font-bold uppercase tracking-[0.18em] text-[#60A5FA]">Portfolio</p>
            <div className="grid gap-4 sm:grid-cols-2 min-[1200px]:grid-cols-3">
              {portfolioCards.map((pos) => (
                <PortfolioCard key={pos.ticker} pos={pos} />
              ))}
            </div>
          </section>
        )}

        {/* Pass entries */}
        {passes.length > 0 && (
          <section className="mt-8">
            <p className="mb-4 text-[11px] font-bold uppercase tracking-[0.18em] text-[#60A5FA]">Passed</p>
            <div className="flex flex-wrap gap-2">
              {passes.map((pass) => (
                <PassPill key={pass.market.ticker} pass={pass} />
              ))}
            </div>
          </section>
        )}

      </main>
    </div>
  );
}
