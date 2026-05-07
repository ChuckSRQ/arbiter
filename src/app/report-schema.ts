export const recommendationActions = [
  "Buy YES",
  "Buy NO",
  "Hold",
  "Reduce",
  "Exit",
  "Watch",
  "Pass",
] as const;

export const confidenceLevels = ["High", "Medium", "Low"] as const;
export const passReasonCodes = [
  "no-reliable-model",
  "edge-below-threshold",
  "low-confidence-pass",
  "spread-too-wide",
] as const;

export type RecommendationAction = (typeof recommendationActions)[number];
export type ConfidenceLevel = (typeof confidenceLevels)[number];
export type PassReasonCode = (typeof passReasonCodes)[number];

export interface EvidenceLink {
  label: string;
  href: string;
  source: string;
  note: string;
}

export interface MarketSnapshot {
  ticker: string;
  title: string;
  category: string;
  yesBidCents: number;
  yesAskCents: number;
  lastTradeCents: number;
  expiresAt: string;
}

export interface Opportunity {
  title: string;
  market: MarketSnapshot;
  action: RecommendationAction;
  marcusFairValue: number;
  edge: number;
  confidence: ConfidenceLevel;
  reason: string;
  evidenceLinks: EvidenceLink[];
  whatWouldChange: string;
}

export interface PositionReview {
  title: string;
  market: MarketSnapshot;
  action: Extract<RecommendationAction, "Hold" | "Reduce" | "Exit">;
  exposure: number;
  pnl: number;
  note: string;
   reason?: string;
   confidence?: ConfidenceLevel;
   marcusFairValue?: number;
   executablePrice?: number;
  evidenceLinks: EvidenceLink[];
}

export interface PassDecision {
  title: string;
  market: MarketSnapshot;
  marketClass: string;
  reasonCode: PassReasonCode;
  reason: string;
  executablePrice: number;
  marcusFairValue?: number;
  edge?: number;
  confidence?: ConfidenceLevel;
}

export interface PortfolioSnapshot {
  grossExposure: number;
  unrealizedPnl: number;
  cashAvailable: number;
  riskPosture: string;
  positions: PositionReview[];
}

export interface ArchiveEntry {
  date: string;
  headline: string;
  summary: string;
  verdict: string;
}

export interface DailyReport {
  reportDate: string;
  generatedAt: string;
  reportLabel: string;
  thesis: string;
  summary: string;
  noTradePolicy: string;
  opportunities: Opportunity[];
  portfolio: PortfolioSnapshot;
  evidence: EvidenceLink[];
  archive: ArchiveEntry[];
  watchlist: string[];
  passes?: PassDecision[];
}

export class ValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ValidationError";
  }
}

function describeValue(value: unknown): string {
  if (value === null) {
    return "null";
  }

  if (value === undefined) {
    return "undefined";
  }

  if (typeof value === "string") {
    return `"${value}"`;
  }

  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  if (Array.isArray(value)) {
    return "an array";
  }

  return typeof value;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function expectRecord(value: unknown, path: string): Record<string, unknown> {
  if (!isRecord(value)) {
    throw new ValidationError(`${path} must be an object, received ${describeValue(value)}.`);
  }

  return value;
}

function expectString(value: unknown, path: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new ValidationError(`${path} must be a non-empty string, received ${describeValue(value)}.`);
  }

  return value;
}

function expectNumber(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new ValidationError(`${path} must be a finite number, received ${describeValue(value)}.`);
  }

  return value;
}

function expectOptionalNumber(value: unknown, path: string): number | undefined {
  if (value === undefined) {
    return undefined;
  }

  return expectNumber(value, path);
}

function expectOptionalString(value: unknown, path: string): string | undefined {
  if (value === undefined) {
    return undefined;
  }

  return expectString(value, path);
}

function expectArray(value: unknown, path: string): unknown[] {
  if (!Array.isArray(value)) {
    throw new ValidationError(`${path} must be an array, received ${describeValue(value)}.`);
  }

  return value;
}

function expectEnum<T extends string>(
  value: unknown,
  allowedValues: readonly T[],
  path: string,
  typeName: string,
): T {
  if (typeof value !== "string" || !allowedValues.includes(value as T)) {
    throw new ValidationError(
      `${path} must be a valid ${typeName} (${allowedValues.join(", ")}), received ${describeValue(value)}.`,
    );
  }

  return value as T;
}

function parseEvidenceLink(value: unknown, path: string): EvidenceLink {
  const record = expectRecord(value, path);

  return {
    label: expectString(record.label, `${path}.label`),
    href: expectString(record.href, `${path}.href`),
    source: expectString(record.source, `${path}.source`),
    note: expectString(record.note, `${path}.note`),
  };
}

function parseMarketSnapshot(value: unknown, path: string): MarketSnapshot {
  const record = expectRecord(value, path);

  return {
    ticker: expectString(record.ticker, `${path}.ticker`),
    title: expectString(record.title, `${path}.title`),
    category: expectString(record.category, `${path}.category`),
    yesBidCents: expectNumber(record.yesBidCents, `${path}.yesBidCents`),
    yesAskCents: expectNumber(record.yesAskCents, `${path}.yesAskCents`),
    lastTradeCents: expectNumber(record.lastTradeCents, `${path}.lastTradeCents`),
    expiresAt: expectString(record.expiresAt, `${path}.expiresAt`),
  };
}

function parseOpportunity(value: unknown, path: string): Opportunity {
  const record = expectRecord(value, path);

  return {
    title: expectString(record.title, `${path}.title`),
    market: parseMarketSnapshot(record.market, `${path}.market`),
    action: expectEnum(record.action, recommendationActions, `${path}.action`, "RecommendationAction"),
    marcusFairValue: expectNumber(record.marcusFairValue, `${path}.marcusFairValue`),
    edge: expectNumber(record.edge, `${path}.edge`),
    confidence: expectEnum(record.confidence, confidenceLevels, `${path}.confidence`, "ConfidenceLevel"),
    reason: expectString(record.reason, `${path}.reason`),
    evidenceLinks: expectArray(record.evidenceLinks, `${path}.evidenceLinks`).map((entry, index) =>
      parseEvidenceLink(entry, `${path}.evidenceLinks[${index}]`),
    ),
    whatWouldChange: expectString(record.whatWouldChange, `${path}.whatWouldChange`),
  };
}

function parsePositionReview(value: unknown, path: string): PositionReview {
  const record = expectRecord(value, path);

  return {
    title: expectString(record.title, `${path}.title`),
    market: parseMarketSnapshot(record.market, `${path}.market`),
    action: expectEnum(record.action, ["Hold", "Reduce", "Exit"], `${path}.action`, "RecommendationAction"),
    exposure: expectNumber(record.exposure, `${path}.exposure`),
    pnl: expectNumber(record.pnl, `${path}.pnl`),
    note: expectString(record.note, `${path}.note`),
    reason: expectOptionalString(record.reason, `${path}.reason`),
    confidence:
      record.confidence === undefined
        ? undefined
        : expectEnum(record.confidence, confidenceLevels, `${path}.confidence`, "ConfidenceLevel"),
    marcusFairValue: expectOptionalNumber(record.marcusFairValue, `${path}.marcusFairValue`),
    executablePrice: expectOptionalNumber(record.executablePrice, `${path}.executablePrice`),
    evidenceLinks: expectArray(record.evidenceLinks, `${path}.evidenceLinks`).map((entry, index) =>
      parseEvidenceLink(entry, `${path}.evidenceLinks[${index}]`),
    ),
  };
}

function parsePassDecision(value: unknown, path: string): PassDecision {
  const record = expectRecord(value, path);

  return {
    title: expectString(record.title, `${path}.title`),
    market: parseMarketSnapshot(record.market, `${path}.market`),
    marketClass: expectString(record.marketClass, `${path}.marketClass`),
    reasonCode: expectEnum(record.reasonCode, passReasonCodes, `${path}.reasonCode`, "PassReasonCode"),
    reason: expectString(record.reason, `${path}.reason`),
    executablePrice: expectNumber(record.executablePrice, `${path}.executablePrice`),
    marcusFairValue: expectOptionalNumber(record.marcusFairValue, `${path}.marcusFairValue`),
    edge: expectOptionalNumber(record.edge, `${path}.edge`),
    confidence:
      record.confidence === undefined
        ? undefined
        : expectEnum(record.confidence, confidenceLevels, `${path}.confidence`, "ConfidenceLevel"),
  };
}

function parsePortfolioSnapshot(value: unknown, path: string): PortfolioSnapshot {
  const record = expectRecord(value, path);

  return {
    grossExposure: expectNumber(record.grossExposure, `${path}.grossExposure`),
    unrealizedPnl: expectNumber(record.unrealizedPnl, `${path}.unrealizedPnl`),
    cashAvailable: expectNumber(record.cashAvailable, `${path}.cashAvailable`),
    riskPosture: expectString(record.riskPosture, `${path}.riskPosture`),
    positions: expectArray(record.positions, `${path}.positions`).map((entry, index) =>
      parsePositionReview(entry, `${path}.positions[${index}]`),
    ),
  };
}

function parseArchiveEntry(value: unknown, path: string): ArchiveEntry {
  const record = expectRecord(value, path);

  return {
    date: expectString(record.date, `${path}.date`),
    headline: expectString(record.headline, `${path}.headline`),
    summary: expectString(record.summary, `${path}.summary`),
    verdict: expectString(record.verdict, `${path}.verdict`),
  };
}

export function parseDailyReport(value: unknown): DailyReport {
  const record = expectRecord(value, "report");

  return {
    reportDate: expectString(record.reportDate, "report.reportDate"),
    generatedAt: expectString(record.generatedAt, "report.generatedAt"),
    reportLabel: expectString(record.reportLabel, "report.reportLabel"),
    thesis: expectString(record.thesis, "report.thesis"),
    summary: expectString(record.summary, "report.summary"),
    noTradePolicy: expectString(record.noTradePolicy, "report.noTradePolicy"),
    opportunities: expectArray(record.opportunities, "report.opportunities").map((entry, index) =>
      parseOpportunity(entry, `report.opportunities[${index}]`),
    ),
    portfolio: parsePortfolioSnapshot(record.portfolio, "report.portfolio"),
    evidence: expectArray(record.evidence, "report.evidence").map((entry, index) =>
      parseEvidenceLink(entry, `report.evidence[${index}]`),
    ),
    archive: expectArray(record.archive, "report.archive").map((entry, index) =>
      parseArchiveEntry(entry, `report.archive[${index}]`),
    ),
    watchlist: expectArray(record.watchlist, "report.watchlist").map((entry, index) =>
      expectString(entry, `report.watchlist[${index}]`),
    ),
    passes:
      record.passes === undefined
        ? undefined
        : expectArray(record.passes, "report.passes").map((entry, index) =>
            parsePassDecision(entry, `report.passes[${index}]`),
          ),
  };
}
