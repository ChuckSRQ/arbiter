import type {
  ConfidenceLevel,
  DailyReport,
  EvidenceLink,
  MarketSnapshot as ReportMarketSnapshot,
  OnWatchEntry,
  Opportunity,
  PassReasonCode,
  PassDecision,
  PollingEvidence,
  PositionReview,
  TrackerEntry,
} from "../app/report-schema";
import { findPollingEvidence, isPollingEvidenceStale, latestPollingDate } from "./polling-evidence";

export const DEFAULT_OPPORTUNITY_LIMIT = 5;
export const TRACKER_SERIES = new Set(["KXAPRPOTUS", "KXGENERICBALLOTVOTEHUB"]);

export type MarketClass = "politics" | "tracker" | "other";

export interface PublicMarketSnapshot {
  ticker: string;
  title: string;
  category?: string | null;
  type?: string | null;
  series_ticker?: string | null;
  tracker_value?: string | null;
  candidate_name?: string | null;
  close_time?: string | null;
  expiration_time?: string | null;
  yes_bid_cents?: number | null;
  yes_ask_cents?: number | null;
  no_bid_cents?: number | null;
  no_ask_cents?: number | null;
  yes_midpoint_cents?: number | null;
  no_midpoint_cents?: number | null;
  volume?: number | null;
  open_interest?: number | null;
  liquidity?: number | null;
  rules_text?: string | null;
}

export interface PublicMarketSnapshotFile {
  collected_at: string;
  source: {
    base_url: string;
    endpoint?: string;
  };
  filters?: Record<string, unknown>;
  markets: Array<PublicMarketSnapshot | Record<string, unknown>>;
}

export interface PortfolioPositionInput {
  ticker: string;
  market_title: string;
  side: string;
  count: number;
  avg_price?: number | null;
  current_price?: number | null;
  market_value?: number | null;
  unrealized_pnl?: number | null;
  exposure?: number | null;
  recommendation?: string | null;
}

export interface PortfolioSnapshotInput {
  collected_at: string;
  source: {
    base_url: string;
  };
  available: boolean;
  balance?: {
    cash_balance?: number | null;
      withdrawable_balance?: number | null;
      portfolio_value?: number | null;
    };
  positions: Array<PortfolioPositionInput | Record<string, unknown>>;
  warnings: string[];
}

export interface ModelOverride {
  fairYesCents: number;
  confidence: ConfidenceLevel;
  reason: string;
  whatWouldChange: string;
  evidenceLinks?: EvidenceLink[];
}

interface BuildDailyReportArgs {
  reportDate: string;
  marketSnapshot: PublicMarketSnapshotFile;
  portfolioSnapshot?: PortfolioSnapshotInput;
  modelOverrides?: Record<string, ModelOverride>;
  pollingEvidence?: PollingEvidence[];
  opportunityLimit?: number;
}

interface EvaluatedModel extends ModelOverride {
  marketClass: MarketClass;
}

interface MarketAnalysis {
  opportunity?: Opportunity;
  pass?: PassDecision;
  tracker?: TrackerEntry;
  skipReason?: "other" | "no-model";
}

const DEFAULT_THESIS = "Arbiter is an edge filter, not a broad market screener.";
const DEFAULT_NO_TRADE_POLICY =
  "No trade today is a valid report when none of the current Kalshi prices clear the evidence bar.";
const POLITICAL_MARKET_PATTERN = /\b(election|senate|house|governor|mayor|nominee|primary|runoff|ballot|vote)\b/;

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asNullableString(value: unknown): string | null | undefined {
  return typeof value === "string" ? value : value === null ? null : undefined;
}

function asNullableNumber(value: unknown): number | null | undefined {
  return typeof value === "number" ? value : value === null ? null : undefined;
}

function normalizeMarket(market: PublicMarketSnapshot | Record<string, unknown>): PublicMarketSnapshot {
  return {
    ticker: asString(market.ticker),
    title: asString(market.title),
    category: asNullableString(market.category),
    type: asNullableString(market.type),
    series_ticker: asNullableString(market.series_ticker),
    tracker_value: asNullableString(market.tracker_value),
    candidate_name: asNullableString(market.candidate_name),
    close_time: asNullableString(market.close_time),
    expiration_time: asNullableString(market.expiration_time),
    yes_bid_cents: asNullableNumber(market.yes_bid_cents),
    yes_ask_cents: asNullableNumber(market.yes_ask_cents),
    no_bid_cents: asNullableNumber(market.no_bid_cents),
    no_ask_cents: asNullableNumber(market.no_ask_cents),
    yes_midpoint_cents: asNullableNumber(market.yes_midpoint_cents),
    no_midpoint_cents: asNullableNumber(market.no_midpoint_cents),
    volume: asNullableNumber(market.volume),
    open_interest: asNullableNumber(market.open_interest),
    liquidity: asNullableNumber(market.liquidity),
    rules_text: asNullableString(market.rules_text),
  };
}

function normalizePosition(position: PortfolioPositionInput | Record<string, unknown>): PortfolioPositionInput {
  return {
    ticker: asString(position.ticker),
    market_title: asString(position.market_title),
    side: asString(position.side, "YES"),
    count: typeof position.count === "number" ? position.count : 0,
    avg_price: asNullableNumber(position.avg_price),
    current_price: asNullableNumber(position.current_price),
    market_value: asNullableNumber(position.market_value),
    unrealized_pnl: asNullableNumber(position.unrealized_pnl),
    exposure: asNullableNumber(position.exposure),
    recommendation: asNullableString(position.recommendation),
  };
}

function clampCents(value: number | null | undefined): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return null;
  }

  return Math.max(0, Math.min(100, Math.round(value)));
}

function inverseCents(value: number | null | undefined): number | null {
  const cents = clampCents(value);
  return cents === null ? null : 100 - cents;
}

function firstNumber(...values: Array<number | null | undefined>): number | null {
  for (const value of values) {
    const cents = clampCents(value);
    if (cents !== null) {
      return cents;
    }
  }

  return null;
}

function yesAskCents(market: PublicMarketSnapshot): number {
  return firstNumber(market.yes_ask_cents, inverseCents(market.no_bid_cents), market.yes_midpoint_cents, 50) ?? 50;
}

function yesBidCents(market: PublicMarketSnapshot): number {
  return firstNumber(market.yes_bid_cents, inverseCents(market.no_ask_cents), market.yes_midpoint_cents, yesAskCents(market)) ?? 50;
}

function noAskCents(market: PublicMarketSnapshot): number {
  return firstNumber(market.no_ask_cents, inverseCents(market.yes_bid_cents), market.no_midpoint_cents, inverseCents(yesBidCents(market)), 50) ?? 50;
}

function noBidCents(market: PublicMarketSnapshot): number {
  return firstNumber(market.no_bid_cents, inverseCents(market.yes_ask_cents), market.no_midpoint_cents, inverseCents(yesAskCents(market)), 50) ?? 50;
}

function lastTradeCents(market: PublicMarketSnapshot): number {
  return firstNumber(
    market.yes_midpoint_cents,
    market.yes_ask_cents !== null && market.yes_ask_cents !== undefined
      ? (yesAskCents(market) + yesBidCents(market)) / 2
      : null,
    50,
  ) ?? 50;
}

function toReportMarketSnapshot(
  market: PublicMarketSnapshot,
  titleOverride?: string,
  categoryOverride?: string,
): ReportMarketSnapshot {
  return {
    ticker: market.ticker,
    title: titleOverride ?? market.title,
    category: categoryOverride ?? market.category ?? "Other",
    yesBidCents: yesBidCents(market),
    yesAskCents: yesAskCents(market),
    lastTradeCents: lastTradeCents(market),
    expiresAt: market.expiration_time ?? market.close_time ?? "",
  };
}

function categoryLabel(marketClass: MarketClass): string {
  switch (marketClass) {
    case "politics":
      return "Politics";
    case "tracker":
      return "Tracker";
    default:
      return "Other";
  }
}

export function classifyMarket(
  market: Pick<PublicMarketSnapshot, "category" | "ticker" | "title" | "type" | "series_ticker">,
): MarketClass {
  const haystack = `${market.category ?? ""} ${market.ticker} ${market.title}`.toLowerCase();
  const marketType = market.type?.toLowerCase();
  const seriesTicker = market.series_ticker?.toUpperCase();

  if (marketType === "tracker" || (seriesTicker && TRACKER_SERIES.has(seriesTicker))) {
    return "tracker";
  }

  if (marketType === "election" || POLITICAL_MARKET_PATTERN.test(haystack)) {
    return "politics";
  }

  return "other";
}

function requiredEdge(confidence: ConfidenceLevel): number {
  switch (confidence) {
    case "High":
      return 5;
    case "Medium":
      return 8;
    case "Low":
      return 12;
  }
}

function watchEdge(confidence: ConfidenceLevel): number {
  switch (confidence) {
    case "High":
      return 4;
    case "Medium":
      return 7;
    case "Low":
      return Number.POSITIVE_INFINITY;
  }
}

function marketSpread(market: PublicMarketSnapshot): number {
  return Math.max(0, yesAskCents(market) - yesBidCents(market));
}

function pollingConfidence(marketType: PollingEvidence["market_type"]): ConfidenceLevel {
  switch (marketType) {
    case "binary-general":
      return "High";
    case "multi-candidate-primary":
    case "top-two":
      return "Medium";
    default:
      return "Low";
  }
}

function fallbackFairYesFromPolling(record: PollingEvidence): number {
  const multiplier = record.market_type === "binary-general" ? 4 : 2;
  return clampCents(50 + record.polling_average.spread * multiplier) ?? 50;
}

function buildPoliticalPollingModel(record: PollingEvidence, marketClass: MarketClass): EvaluatedModel {
  const fairYesCents = clampCents(record.polling_average.fair_yes_cents) ?? fallbackFairYesFromPolling(record);
  const confidence = pollingConfidence(record.market_type);
  const latestSpread = record.latest_polls[0]?.spread ?? `${record.polling_average.leader} +${record.polling_average.spread}`;
  const pluralityWarning =
    record.market_type === "multi-candidate-primary" || record.market_type === "top-two"
      ? " Raw primary vote share is not direct win probability; plurality and fragmentation matter more than a one-to-one vote-share comparison."
      : "";
  const reason = `Polling-first view: ${record.polling_average.leader} leads ${record.polling_average.runner_up} ${record.polling_average.leader_share}-${record.polling_average.runner_up_share} in the current average, latest tracked spread is ${latestSpread}, and ${record.trend_summary} That supports roughly ${fairYesCents}c fair value.${pluralityWarning}`;
  const whatWouldChange =
    record.market_type === "multi-candidate-primary" || record.market_type === "top-two"
      ? `A fresher poll showing the field consolidating behind ${record.polling_average.runner_up} would cut the plurality edge.`
      : `A fresher poll moving ${record.polling_average.runner_up} ahead would take this back to pass.`;

  return {
    fairYesCents,
    confidence,
    reason,
    whatWouldChange,
    evidenceLinks:
      record.evidence_links.length > 0
        ? record.evidence_links
        : [
            {
              label: `${record.race} polling source`,
              href: record.source_url,
              source: "Polling",
              note: record.trend_summary,
            },
          ],
    marketClass,
  };
}

function resolveModel(
  market: PublicMarketSnapshot,
  overrides: Record<string, ModelOverride> | undefined,
  marketClass: MarketClass,
  pollingEvidence: PollingEvidence[] | undefined,
  reportDate: string,
): EvaluatedModel | null {
  const override = overrides?.[market.ticker];
  if (override) {
    return { ...override, marketClass };
  }

  if (marketClass === "politics") {
    const record = findPollingEvidence(market, pollingEvidence);
    if (!record || isPollingEvidenceStale(record, reportDate)) {
      return null;
    }

    return buildPoliticalPollingModel(record, marketClass);
  }

  return null;
}

function trackerDirection(market: PublicMarketSnapshot): string {
  const currentValue = market.tracker_value?.toLowerCase() ?? "";
  const title = market.title.toLowerCase();

  if (currentValue.includes(" to ") || title.includes(" between ")) {
    return "Between";
  }

  if (/\b(above|over)\b/.test(currentValue) || /\b(above|over)\b/.test(title)) {
    return "Above";
  }

  if (/\b(below|under)\b/.test(currentValue) || /\b(below|under)\b/.test(title)) {
    return "Below";
  }

  return "Range";
}

function buildTrackerEntry(market: PublicMarketSnapshot): TrackerEntry {
  return {
    seriesTicker: market.series_ticker ?? market.ticker,
    title: market.title,
    currentValue: market.tracker_value ?? market.title,
    marketPrice: lastTradeCents(market),
    direction: trackerDirection(market),
  };
}

function buildPassDecision(
  market: PublicMarketSnapshot,
  marketClass: MarketClass,
  reasonCode: PassReasonCode,
  reason: string,
  executablePrice: number,
  fairYesCents?: number,
  confidence?: ConfidenceLevel,
  edge?: number,
): PassDecision {
  return {
    title: market.title,
    market: toReportMarketSnapshot(market, market.title, market.category ?? categoryLabel(marketClass)),
    marketClass,
    reasonCode,
    reason,
    executablePrice,
    marcusFairValue: fairYesCents,
    confidence,
    edge,
  };
}

function analyzeMarket(
  market: PublicMarketSnapshot,
  overrides: Record<string, ModelOverride> | undefined,
  pollingEvidence: PollingEvidence[] | undefined,
  reportDate: string,
): MarketAnalysis {
  const marketClass = classifyMarket(market);

  if (marketClass === "tracker") {
    return { tracker: buildTrackerEntry(market) };
  }

  if (marketClass === "other") {
    return { skipReason: "other" };
  }

  const executableYes = yesAskCents(market);
  const executableNo = noAskCents(market);

  const record = findPollingEvidence(market, pollingEvidence);
  if (!record || isPollingEvidenceStale(record, reportDate)) {
    const freshness = record ? ` Latest tracked poll ended ${latestPollingDate(record)}.` : "";

    return {
      pass: buildPassDecision(
        market,
        marketClass,
        "missing-or-stale-polling",
        `Pass: missing-or-stale-polling.${freshness}`,
        executableYes,
      ),
    };
  }

  const model = resolveModel(market, overrides, marketClass, pollingEvidence, reportDate);

  if (model === null) {
    return { skipReason: "no-model" };
  }

  const fairNo = 100 - model.fairYesCents;
  const yesEdge = model.fairYesCents - executableYes;
  const noEdge = fairNo - executableNo;
  const buyYes = yesEdge >= noEdge;
  const bestEdge = buyYes ? yesEdge : noEdge;
  const bestExecutablePrice = buyYes ? executableYes : executableNo;
  const minimumEdge = requiredEdge(model.confidence);

  if (bestEdge >= minimumEdge) {
    return {
      opportunity: {
        title: market.title,
        market: toReportMarketSnapshot(market, market.title, market.category ?? categoryLabel(marketClass)),
        action: buyYes ? "Buy YES" : "Buy NO",
        marcusFairValue: model.fairYesCents,
        edge: bestEdge,
        confidence: model.confidence,
        reason: model.reason,
        evidenceLinks: model.evidenceLinks ?? [],
        whatWouldChange: model.whatWouldChange,
      },
    };
  }

  if (bestEdge >= watchEdge(model.confidence)) {
    return {
      opportunity: {
        title: market.title,
        market: toReportMarketSnapshot(market, market.title, market.category ?? categoryLabel(marketClass)),
        action: "Watch",
        marcusFairValue: model.fairYesCents,
        edge: bestEdge,
        confidence: model.confidence,
        reason: model.reason,
        evidenceLinks: model.evidenceLinks ?? [],
        whatWouldChange: model.whatWouldChange,
      },
    };
  }

  const spread = marketSpread(market);
  const reasonCode: PassReasonCode =
    model.confidence === "Low"
      ? "low-confidence-pass"
      : spread >= 6 && bestEdge < minimumEdge
        ? "spread-too-wide"
        : "edge-below-threshold";

  const reason =
    reasonCode === "low-confidence-pass"
      ? `Pass: low-confidence setups need a much larger edge than the current ${bestEdge}c gap.`
      : reasonCode === "spread-too-wide"
        ? "Pass: the spread is too wide for the remaining edge."
        : `Pass: ${bestEdge}c is below the ${minimumEdge}c trade threshold for ${model.confidence.toLowerCase()} confidence.`;

  return {
    pass: buildPassDecision(
      market,
      marketClass,
      reasonCode,
      reason,
      bestExecutablePrice,
      model.fairYesCents,
      model.confidence,
      bestEdge,
    ),
  };
}

function makePositionMarket(
  position: PortfolioPositionInput,
  liveMarket: PublicMarketSnapshot | undefined,
): ReportMarketSnapshot {
  if (liveMarket) {
    return toReportMarketSnapshot(liveMarket, position.market_title);
  }

  const marketClass = classifyMarket({
    ticker: position.ticker,
    title: position.market_title,
    category: "",
  });
  const lastTrade = clampCents(position.current_price) ?? clampCents(position.avg_price) ?? 50;

  return {
    ticker: position.ticker,
    title: position.market_title,
    category: categoryLabel(marketClass),
    yesBidCents: lastTrade,
    yesAskCents: lastTrade,
    lastTradeCents: lastTrade,
    expiresAt: "1970-01-01T00:00:00Z",
  };
}

function exitPriceForPosition(position: PortfolioPositionInput, liveMarket: PublicMarketSnapshot | undefined): number {
  if (String(position.side).toUpperCase() === "NO") {
    return liveMarket ? noBidCents(liveMarket) : clampCents(position.current_price) ?? 50;
  }

  return liveMarket ? yesBidCents(liveMarket) : clampCents(position.current_price) ?? 50;
}

function fairValueForPosition(model: EvaluatedModel, side: string): number {
  return side.toUpperCase() === "NO" ? 100 - model.fairYesCents : model.fairYesCents;
}

function reviewPosition(
  position: PortfolioPositionInput,
  liveMarket: PublicMarketSnapshot | undefined,
  overrides: Record<string, ModelOverride> | undefined,
  pollingEvidence: PollingEvidence[] | undefined,
  reportDate: string,
): PositionReview {
  const marketReference: PublicMarketSnapshot = liveMarket ?? {
    ticker: position.ticker,
    title: position.market_title,
    category: undefined,
    yes_bid_cents: clampCents(position.current_price),
    yes_ask_cents: clampCents(position.current_price),
    no_bid_cents: inverseCents(position.current_price),
    no_ask_cents: inverseCents(position.current_price),
  };
  const marketClass = classifyMarket(marketReference);
  const model = resolveModel(marketReference, overrides, marketClass, pollingEvidence, reportDate);
  const executablePrice = exitPriceForPosition(position, liveMarket);

  if (!model) {
    return {
      title: position.market_title,
      market: makePositionMarket(position, liveMarket),
      action: "Hold",
      exposure: position.exposure ?? 0,
      pnl: position.unrealized_pnl ?? 0,
      note: "No reliable exit model is available yet, so the position stays on hold.",
      reason: "No reliable exit model is available yet, so the position stays on hold.",
      confidence: "Low",
      executablePrice,
      evidenceLinks: [],
    };
  }

  const fairValue = fairValueForPosition(model, position.side);
  const negativeEdge = executablePrice - fairValue;
  const placeholder = position.recommendation ?? "";
  const action =
    negativeEdge >= 8 || placeholder === "Exit candidate"
      ? "Exit"
      : negativeEdge >= 4 || placeholder === "Reduce candidate" || (position.exposure ?? 0) >= 3000
        ? "Reduce"
        : "Hold";

  const reason =
    action === "Hold"
      ? `Marcus fair value ${fairValue}c is close enough to the ${executablePrice}c executable exit price to keep holding.`
      : `Marcus fair value ${fairValue}c sits below the executable exit price of ${executablePrice}c, so trimming risk is justified.`;

  const note =
    action === "Exit"
      ? `${reason} Exit now instead of waiting for variance.`
      : action === "Reduce"
        ? `${reason} Reduce the position before adding new risk.`
        : reason;

  return {
    title: position.market_title,
    market: makePositionMarket(position, liveMarket),
    action,
    exposure: position.exposure ?? 0,
    pnl: position.unrealized_pnl ?? 0,
    note,
    reason,
    confidence: model.confidence,
    marcusFairValue: fairValue,
    executablePrice,
    evidenceLinks: model.evidenceLinks ?? [],
  };
}

function formatGeneratedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const formatter = new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "America/New_York",
  });
  return `${formatter.format(date)} ET`;
}

function dedupeEvidence(links: EvidenceLink[]): EvidenceLink[] {
  const seen = new Set<string>();
  const deduped: EvidenceLink[] = [];

  for (const link of links) {
    const key = `${link.label}|${link.href}|${link.source}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    deduped.push(link);
  }

  return deduped;
}

function dedupePollingEvidence(records: PollingEvidence[]): PollingEvidence[] {
  const seen = new Set<string>();
  const deduped: PollingEvidence[] = [];

  for (const record of records) {
    if (seen.has(record.market_key)) {
      continue;
    }

    seen.add(record.market_key);
    deduped.push(record);
  }

  return deduped;
}

function confidenceMultiplier(confidence: ConfidenceLevel): number {
  switch (confidence) {
    case "High":
      return 1.0;
    case "Medium":
      return 0.7;
    case "Low":
      return 0.4;
  }
}

function daysUntilExpiration(expiresAt: string, now: Date = new Date()): number {
  const expiryDate = new Date(expiresAt);
  if (Number.isNaN(expiryDate.getTime())) {
    return Number.POSITIVE_INFINITY;
  }
  return Math.max(0, (expiryDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
}

export function calculateOpportunityScore(opportunity: Opportunity, now: Date = new Date()): number {
  const daysUntilExpiry = daysUntilExpiration(opportunity.market.expiresAt, now);

  let timeWeight = 1.0;
  if (daysUntilExpiry <= 14) {
    timeWeight = 1.5;
  } else if (daysUntilExpiry <= 30) {
    timeWeight = 1.2;
  }
  
  const confidenceMultiplierValue = confidenceMultiplier(opportunity.confidence);
  const score = opportunity.edge * confidenceMultiplierValue * timeWeight;

  return score;
}

function buildOnWatchEntry(
  markets: PublicMarketSnapshot[],
  mainMarket: PublicMarketSnapshot,
  pollingEvidence: PollingEvidence[] | undefined,
): OnWatchEntry | null {
  const maybeMayorLaGroup =
    (mainMarket.ticker === "KXMAYORLA" || mainMarket.ticker.startsWith("KXMAYORLA-")) &&
    markets.some((m) => m.ticker === "KXMAYORLA" || m.ticker.startsWith("KXMAYORLA-"));

  if (maybeMayorLaGroup) {
    const primary = markets.find((m) => m.ticker === "KXMAYORLA") ?? mainMarket;
    const electionDate = primary.close_time || primary.expiration_time || mainMarket.close_time || mainMarket.expiration_time || "";
    const title = primary.title || "Los Angeles Mayoral Election";
    const candidates = markets
      .filter((m) => m.ticker?.startsWith("KXMAYORLA-"))
      .map((m) => {
        const name = m.candidate_name
          || m.ticker?.split("-").pop()
          || m.title;
        const price = yesAskCents(m);
        return { candidate: name, yesPrice: price };
      })
      .sort((a, b) => b.yesPrice - a.yesPrice);

    if (candidates.length === 0) {
      return null;
    }

    const pollingRecord = findPollingEvidence(primary, pollingEvidence);
    const pollingSpread = pollingRecord?.polling_average?.spread
      ? `${pollingRecord.polling_average.leader} +${pollingRecord.polling_average.spread}`
      : null;

    return {
      ticker: "KXMAYORLA",
      title,
      electionDate,
      marketFavorites: candidates,
      pollingSpread,
    };
  }

  const ticker = mainMarket.ticker;
  const title = mainMarket.title;
  const electionDate = mainMarket.close_time || mainMarket.expiration_time || "";
  const pollingRecord = findPollingEvidence(mainMarket, pollingEvidence);
  const pollingSpread = pollingRecord?.polling_average?.spread
    ? `${pollingRecord.polling_average.leader} +${pollingRecord.polling_average.spread}`
    : null;

  return {
    ticker,
    title,
    electionDate,
    marketFavorites: [{ candidate: "YES", yesPrice: yesAskCents(mainMarket) }],
    pollingSpread,
  };
}

export function buildDailyReport({
  reportDate,
  marketSnapshot,
  portfolioSnapshot,
  modelOverrides,
  pollingEvidence,
  opportunityLimit = DEFAULT_OPPORTUNITY_LIMIT,
}: BuildDailyReportArgs): DailyReport {
  const normalizedMarkets = marketSnapshot.markets.map((market) => normalizeMarket(market));
  const normalizedPositions = (portfolioSnapshot?.positions ?? []).map((position) => normalizePosition(position));
  const evaluated = normalizedMarkets.map((market) =>
    analyzeMarket(market, modelOverrides, pollingEvidence, reportDate),
  );
  const generatedOpportunities = evaluated.flatMap((entry) => (entry.opportunity ? [entry.opportunity] : []));
  const opportunities = generatedOpportunities
    .slice()
    .sort((left, right) => calculateOpportunityScore(right) - calculateOpportunityScore(left))
    .slice(0, opportunityLimit);
  const passes = evaluated.flatMap((entry) => (entry.pass ? [entry.pass] : []));
  const trackers = evaluated.flatMap((entry) => (entry.tracker ? [entry.tracker] : []));

  const portfolioReviews = normalizedPositions.map((position) =>
    reviewPosition(
      position,
      normalizedMarkets.find((market) => market.ticker === position.ticker),
      modelOverrides,
      pollingEvidence,
      reportDate,
    ),
  );
  const positionActions = portfolioReviews.filter((position) => position.action !== "Hold");
  const matchedPollingEvidence = dedupePollingEvidence(
    [
      ...normalizedMarkets
        .filter((market) => classifyMarket(market) === "politics")
        .map((market) => findPollingEvidence(market, pollingEvidence)),
      ...normalizedPositions.map((position) =>
        findPollingEvidence({ ticker: position.ticker, title: position.market_title }, pollingEvidence),
      ),
    ].flatMap((record) => (record ? [record] : [])),
  );
  const evidence = dedupeEvidence([
    ...matchedPollingEvidence.flatMap((record) => record.evidence_links),
    ...opportunities.flatMap((opportunity) => opportunity.evidenceLinks),
    ...portfolioReviews.flatMap((position) => position.evidenceLinks),
  ]);
  const summary =
    opportunities.length === 0
      ? "No trade today. Nothing cleared the evidence bar after executable prices and confidence thresholds."
      : `${opportunities.length} opportunity${opportunities.length === 1 ? "" : "ies"} cleared the bar, with ${positionActions.length} portfolio action${positionActions.length === 1 ? "" : "s"} also worth attention.`;

  // Build onWatch entries for politics markets without opportunities
  const politicsMarkets = normalizedMarkets.filter((m) => classifyMarket(m) === "politics");
  const generatedOpportunityTickers = new Set(generatedOpportunities.map((o) => o.market.ticker));

  // Handle KXMAYORLA specially - group all sub-markets
  const kxmayorlaMarkets = politicsMarkets.filter((m) => m.ticker === "KXMAYORLA" || m.ticker.startsWith("KXMAYORLA-"));
  const onWatchItems: OnWatchEntry[] = [];

  if (
    kxmayorlaMarkets.length > 0 &&
    !kxmayorlaMarkets.some((market) => generatedOpportunityTickers.has(market.ticker))
  ) {
    const main = kxmayorlaMarkets.find((m) => m.ticker === "KXMAYORLA") || kxmayorlaMarkets[0];
    const entry = buildOnWatchEntry(kxmayorlaMarkets, main, pollingEvidence);
    if (entry) {
      onWatchItems.push(entry);
    }
  }

  // Add other politics markets without opportunities
  for (const market of politicsMarkets) {
    if (generatedOpportunityTickers.has(market.ticker) || market.ticker.startsWith("KXMAYORLA")) {
      continue;
    }
    const entry = buildOnWatchEntry(politicsMarkets, market, pollingEvidence);
    if (entry) {
      onWatchItems.push(entry);
    }
  }

  // Sort onWatch items by election date (closest first)
  onWatchItems.sort((a, b) => {
    const leftTime = new Date(a.electionDate).getTime();
    const rightTime = new Date(b.electionDate).getTime();
    const leftValid = Number.isFinite(leftTime);
    const rightValid = Number.isFinite(rightTime);
    if (!leftValid && !rightValid) {
      return a.title.localeCompare(b.title);
    }
    if (!leftValid) {
      return 1;
    }
    if (!rightValid) {
      return -1;
    }
    return leftTime - rightTime;
  });


  return {
    reportDate,
    generatedAt: formatGeneratedAt(marketSnapshot.collected_at),
    reportLabel: opportunities.length === 0 ? "No trade day" : "Generated edge brief",
    thesis: DEFAULT_THESIS,
    summary,
    noTradePolicy: DEFAULT_NO_TRADE_POLICY,
    opportunities,
    portfolio: {
      grossExposure: normalizedPositions.reduce((total, position) => total + (position.exposure ?? 0), 0),
      unrealizedPnl: normalizedPositions.reduce(
        (total, position) => total + (position.unrealized_pnl ?? 0),
        0,
      ),
      cashAvailable: portfolioSnapshot?.balance?.cash_balance ?? 0,
      riskPosture:
        positionActions.length > 0
          ? "Clean up stale or overpriced positions before forcing fresh risk."
          : "Stay patient; most markets should stay passed until a reliable model appears.",
      positions: portfolioReviews,
    },
    evidence,
    pollingEvidence: matchedPollingEvidence.length > 0 ? matchedPollingEvidence : undefined,
    archive: [],
    watchlist: [
      "Most markets should stay passed until a reliable model exists.",
      opportunities.length === 0
        ? "No trade today remains the default output."
        : `Only the top ${opportunityLimit} ideas make the report.`,
      "Use executable prices, not midpoints, when deciding whether an edge is real.",
    ],
    passes: passes.length > 0 ? passes : undefined,
    trackers: trackers.length > 0 ? trackers : undefined,
    onWatch: onWatchItems.length > 0 ? onWatchItems : undefined,
  };
}
