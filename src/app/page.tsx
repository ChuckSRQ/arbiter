import {
  type DashboardReportStatus,
  getTopOpportunities,
  mockDashboardReport,
} from "./dashboard-data";
import { parseDailyReport } from "./report-schema";
import type { DailyReport, OnWatchEntry, Opportunity, TrackerEntry } from "./report-schema";

export const dynamic = 'force-dynamic';

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

// ─── On-watch card ────────────────────────────────────────────────────────────

function OnWatchCard({ entry }: { entry: OnWatchEntry }) {
  const maxPrice = Math.max(...entry.marketFavorites.map(f => f.yesPrice));
  
  return (
    <article className="flex flex-col rounded-[20px] bg-[#141828] p-[18px]">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <TickerBadge ticker={entry.ticker} />
        <span className="inline-block rounded-[6px] bg-[rgba(59,130,246,0.08)] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#60A5FA] border border-[rgba(59,130,246,0.2)]">
          On Watch
        </span>
      </div>

      {/* Title */}
      <h3 className="text-[18px] font-bold leading-tight text-[#F1F5F9]">{entry.title}</h3>

      {/* Election date */}
      <p className="mt-1 text-[13px] font-medium text-[#60A5FA]">{entry.electionDate.split("T")[0]}</p>

      {/* Polling data or placeholder */}
      {entry.pollingSpread ? (
        <p className="mt-2 text-[13px] text-[#E8E4DC]">{entry.pollingSpread}</p>
      ) : (
        <p className="mt-2 text-[13px] text-[#888]">No polling data</p>
      )}

      {/* Candidates table */}
      <div className="mt-4 space-y-2">
        {entry.marketFavorites.map((fav, i) => (
          <div key={i} className="flex items-center justify-between rounded-[8px] bg-[rgba(59,130,246,0.08)] px-3 py-2">
            <span className={`text-[12px] font-medium ${fav.yesPrice === maxPrice ? "text-[#FCD34D]" : "text-[#E8E4DC]"}`}>
              {fav.candidate}
            </span>
            <span className={`text-[13px] font-bold ${fav.yesPrice === maxPrice ? "text-[#FCD34D]" : "text-[#93C5FD]"}`}>
              {fav.yesPrice}¢
            </span>
          </div>
        ))}
      </div>
    </article>
  );
}

// ─── Tracker card ──────────────────────────────────────────────────────────────

function TrackerCard({ entry }: { entry: TrackerEntry }) {
  return (
    <article className="flex flex-col rounded-[20px] bg-[#141828] p-[18px]">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <span className="inline-block rounded-[6px] bg-[rgba(59,130,246,0.08)] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#60A5FA] border border-[rgba(59,130,246,0.2)]">
          Pulse Check
        </span>
      </div>

      {/* Title */}
      <h3 className="text-[16px] font-bold text-[#F1F5F9]">{entry.title}</h3>

      {/* Current value and market price */}
      <div className="mt-3 flex items-end gap-3">
        <div className="flex flex-col">
          <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[#60A5FA]">Current</span>
          <span className="text-[16px] font-bold text-[#E8E4DC]">{entry.currentValue}</span>
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[#FCD34D]">Market</span>
          <span className="text-[16px] font-bold text-[#FDE68A]">{entry.marketPrice}¢</span>
        </div>
      </div>
    </article>
  );
}

function NoTradeCard({ report }: { report: DailyReport }) {
  const watchCount = report.watchlist?.length ?? 0;
  const message = watchCount > 0
    ? `No edge today. ${watchCount} elections on watch.`
    : "No edge today.";

  return (
    <p className="text-[12px] font-semibold text-[#FCD34D]">
      {message}
    </p>
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
  report?: unknown;
  reportStatus?: DashboardReportStatus;
  portfolioSnapshot?: unknown;
};

export default function Home({
  report = mockDashboardReport,
}: HomeProps) {
  const dailyReport = parseDailyReport(report);
  const topOpps = getTopOpportunities(dailyReport);
  const onWatchItems = [...(dailyReport.onWatch ?? [])].sort((left, right) => {
    const leftTime = new Date(left.electionDate).getTime();
    const rightTime = new Date(right.electionDate).getTime();
    const leftValid = Number.isFinite(leftTime);
    const rightValid = Number.isFinite(rightTime);

    if (!leftValid && !rightValid) {
      return left.title.localeCompare(right.title);
    }
    if (!leftValid) {
      return 1;
    }
    if (!rightValid) {
      return -1;
    }
    return leftTime - rightTime;
  });

  return (
    <div className="min-h-[100dvh] bg-[#0D0F1A]">
      {/* Sticky header */}
      <header className="sticky top-0 z-50 bg-[#0D0F1A] border-b border-[rgba(59,130,246,0.15)]">
        <div className="px-[18px] py-3">
          <div className="flex items-center justify-between">
            <h1 className="text-[22px] font-bold text-[#F1F5F9] tracking-tight">Arbiter</h1>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5">
                <LiveDot />
                <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#FCD34D]">Live</span>
              </div>
              <span className="text-[11px] font-medium text-[#60A5FA]">{dailyReport.reportDate}</span>
            </div>
          </div>
          {topOpps.length === 0 && (
            <div className="mt-2">
              <NoTradeCard report={dailyReport} />
            </div>
          )}
        </div>
      </header>

      {/* Main content */}
      <main className="px-4 py-6 lg:px-8 lg:py-8 space-y-8">
        {/* Opportunities section */}
        {topOpps.length > 0 && (
          <section>
            <h2 className="text-[16px] font-bold text-[#F1F5F9] mb-4 uppercase tracking-[0.08em]">Opportunities</h2>
            <div className="grid gap-4 sm:grid-cols-2 min-[1200px]:grid-cols-3">
              {topOpps.map((opp) => (
                <OpportunityCard key={opp.market.ticker} opp={opp} />
              ))}
            </div>
          </section>
        )}

        {/* On-watch section */}
        {onWatchItems.length > 0 && (
          <section>
            <h2 className="text-[16px] font-bold text-[#F1F5F9] mb-4 uppercase tracking-[0.08em]">On Watch</h2>
            <div className="grid gap-4 sm:grid-cols-2 min-[1200px]:grid-cols-3">
              {onWatchItems.map((entry) => (
                <OnWatchCard key={entry.ticker} entry={entry} />
              ))}
            </div>
          </section>
        )}

        {/* Pulse check section */}
        {dailyReport.trackers && dailyReport.trackers.length > 0 && (
          <section>
            <h2 className="text-[16px] font-bold text-[#F1F5F9] mb-4 uppercase tracking-[0.08em]">Pulse Check</h2>
            <div className="grid gap-4 sm:grid-cols-2 min-[1200px]:grid-cols-3">
              {dailyReport.trackers.map((tracker) => (
                <TrackerCard key={tracker.seriesTicker} entry={tracker} />
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
