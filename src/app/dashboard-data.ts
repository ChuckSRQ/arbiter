export type RecommendationAction =
  | "Buy YES"
  | "Buy NO"
  | "Hold"
  | "Reduce"
  | "Exit"
  | "Watch"
  | "Pass";

export type ConfidenceLevel = "High" | "Medium" | "Low";

export interface Opportunity {
  ticker: string;
  title: string;
  action: RecommendationAction;
  kalshiPrice: number;
  marcusFairValue: number;
  edge: number;
  confidence: ConfidenceLevel;
  reason: string;
  evidenceCount: number;
  whatWouldChange: string;
}

export interface PortfolioPositionReview {
  ticker: string;
  title: string;
  action: Extract<RecommendationAction, "Hold" | "Reduce" | "Exit">;
  exposure: number;
  pnl: number;
  note: string;
}

export interface EvidenceLink {
  label: string;
  href: string;
  source: string;
  note: string;
}

export interface ArchiveEntry {
  date: string;
  headline: string;
  summary: string;
  verdict: string;
}

export interface DashboardReport {
  generatedAt: string;
  reportLabel: string;
  thesis: string;
  noTradePolicy: string;
  opportunities: Opportunity[];
  portfolio: {
    grossExposure: number;
    unrealizedPnl: number;
    cashAvailable: number;
    riskPosture: string;
    positions: PortfolioPositionReview[];
  };
  evidence: EvidenceLink[];
  archive: ArchiveEntry[];
  watchlist: string[];
}

export const mockDashboardReport: DashboardReport = {
  generatedAt: "May 6, 2026 · 8:30 PM ET",
  reportLabel: "Private edge brief",
  thesis: "Arbiter is an edge filter, not a broad market screener.",
  noTradePolicy:
    "No trade today is a valid report when none of the current Kalshi prices clear the evidence bar.",
  opportunities: [
    {
      ticker: "FEDCUT-SEP26",
      title: "Fed cuts rates by the September 2026 meeting",
      action: "Buy YES",
      kalshiPrice: 42,
      marcusFairValue: 51,
      edge: 9,
      confidence: "High",
      reason: "Inflation is cooling faster than the strip implies and labor slack is widening.",
      evidenceCount: 4,
      whatWouldChange:
        "A re-acceleration in core CPI or a material upside surprise in payrolls would compress the edge.",
    },
    {
      ticker: "HOUSE-DEM-2026",
      title: "Democrats win the House in 2026",
      action: "Buy YES",
      kalshiPrice: 47,
      marcusFairValue: 54,
      edge: 7,
      confidence: "Medium",
      reason: "Generic ballot drift and district retirements favor a modest Democratic path.",
      evidenceCount: 5,
      whatWouldChange:
        "A Republican polling rebound in suburban districts or a durable fundraising gap would neutralize the view.",
    },
    {
      ticker: "F1-MONACO-LEC",
      title: "Charles Leclerc podium at Monaco Grand Prix",
      action: "Watch",
      kalshiPrice: 58,
      marcusFairValue: 63,
      edge: 5,
      confidence: "Medium",
      reason: "Single-lap pace and tire warm-up profile fit Monaco if qualifying stays clean.",
      evidenceCount: 3,
      whatWouldChange:
        "A grid penalty or long-run degradation in final practice would drop this below the trade bar.",
    },
    {
      ticker: "CPI-LOWER-JUL",
      title: "July CPI comes in below consensus",
      action: "Buy YES",
      kalshiPrice: 39,
      marcusFairValue: 44,
      edge: 5,
      confidence: "Low",
      reason: "Shelter rollover is supportive, but the edge is smaller and data-sensitive.",
      evidenceCount: 3,
      whatWouldChange:
        "A commodity rebound or sticky services prints in the next release would move this to pass.",
    },
  ],
  portfolio: {
    grossExposure: 12450,
    unrealizedPnl: 860,
    cashAvailable: 4780,
    riskPosture: "Concentrated in macro and election timing; avoid adding correlated rate exposure.",
    positions: [
      {
        ticker: "FEDHOLD-JUN",
        title: "Fed holds through June",
        action: "Hold",
        exposure: 3200,
        pnl: 240,
        note: "Still aligned with the base case; thesis review date stays after next CPI print.",
      },
      {
        ticker: "OIL-ABOVE-85",
        title: "WTI settles above $85 this month",
        action: "Reduce",
        exposure: 2650,
        pnl: 110,
        note: "Crowded positioning and softer demand data argue for trimming before inventory numbers.",
      },
      {
        ticker: "F1-VER-WIN",
        title: "Verstappen wins next race",
        action: "Exit",
        exposure: 1400,
        pnl: -190,
        note: "Track-specific pace no longer supports the price; better to free capital than hope for variance.",
      },
    ],
  },
  evidence: [
    {
      label: "RCP generic ballot average",
      href: "https://www.realclearpolling.com/",
      source: "Polling",
      note: "Primary input for the House 2026 market; validates direction before news narrative.",
    },
    {
      label: "F1ReplayTiming Monaco pace notes",
      href: "https://f1replaytiming.com/",
      source: "F1 pace",
      note: "Used for single-lap and long-run pace context before qualifying-sensitive trades.",
    },
    {
      label: "CME FedWatch path",
      href: "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html",
      source: "Rates",
      note: "Cross-check market-implied rate path before assigning Marcus fair value.",
    },
    {
      label: "BLS CPI release calendar",
      href: "https://www.bls.gov/schedule/news_release/cpi.htm",
      source: "Official data",
      note: "Event timing anchor for CPI markets and portfolio review windows.",
    },
  ],
  archive: [
    {
      date: "2026-05-05",
      headline: "Archived brief · Macro over motorsport",
      summary: "One rate cut setup qualified. F1 stayed on watch after weak long-run pace.",
      verdict: "1 trade idea, 2 passes",
    },
    {
      date: "2026-05-04",
      headline: "Archived brief · No trade today",
      summary: "Nothing cleared the confidence threshold after spread and evidence review.",
      verdict: "No trade today",
    },
    {
      date: "2026-05-03",
      headline: "Archived brief · Portfolio cleanup",
      summary: "Focus shifted to an exit and one reduce call instead of new exposure.",
      verdict: "0 new trades, 2 position actions",
    },
  ],
  watchlist: [
    "Pass thin-liquidity weather contracts until a model exists.",
    "Wait on commodity-linked inflation markets until energy trend confirms.",
    "Do not force a fifth idea if only four opportunities clear the bar.",
  ],
};

export function getTopOpportunities(report: DashboardReport): Opportunity[] {
  return [...report.opportunities].sort((left, right) => right.edge - left.edge).slice(0, 5);
}
