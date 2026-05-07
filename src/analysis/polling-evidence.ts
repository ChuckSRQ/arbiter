import type { PollingEvidence } from "../app/report-schema";

type MarketReference = {
  ticker: string;
  title: string;
};

export interface PollingEvidenceFile {
  evidence: PollingEvidence[];
}

function normalizeText(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function normalizeCompact(value: string): string {
  return normalizeText(value).replace(/\s+/g, "");
}

function containsMatch(left: string, right: string): boolean {
  return left.length > 0 && right.length > 0 && (left.includes(right) || right.includes(left));
}

export function findPollingEvidence(
  market: MarketReference,
  records: PollingEvidence[] | undefined,
): PollingEvidence | undefined {
  const titleKey = normalizeCompact(market.title);
  const tickerKey = normalizeCompact(market.ticker);

  return records?.find((record) => {
    const marketKey = normalizeCompact(record.market_key);
    const raceKey = normalizeCompact(record.race);

    return (
      containsMatch(titleKey, marketKey) ||
      containsMatch(titleKey, raceKey) ||
      containsMatch(tickerKey, marketKey) ||
      containsMatch(tickerKey, raceKey)
    );
  });
}

export function latestPollingDate(record: PollingEvidence): string {
  const latestPollDate = [...record.latest_polls]
    .map((poll) => poll.dates.end)
    .filter((value) => value.length > 0)
    .sort()
    .at(-1);

  return latestPollDate ?? record.polling_average.updated_at ?? record.collected_at;
}

export function isPollingEvidenceStale(record: PollingEvidence, reportDate: string, maxAgeDays = 21): boolean {
  const freshest = new Date(latestPollingDate(record));
  const report = new Date(`${reportDate}T00:00:00Z`);

  if (Number.isNaN(freshest.getTime()) || Number.isNaN(report.getTime())) {
    return true;
  }

  const ageDays = (report.getTime() - freshest.getTime()) / (1000 * 60 * 60 * 24);
  return ageDays > maxAgeDays;
}

function expectRecord(value: unknown, path: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${path} must be an object.`);
  }

  return value as Record<string, unknown>;
}

function expectString(value: unknown, path: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new Error(`${path} must be a non-empty string.`);
  }

  return value;
}

function expectNumber(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`${path} must be a finite number.`);
  }

  return value;
}

function expectArray(value: unknown, path: string): unknown[] {
  if (!Array.isArray(value)) {
    throw new Error(`${path} must be an array.`);
  }

  return value;
}

function parseEvidenceLink(value: unknown, path: string) {
  const record = expectRecord(value, path);

  return {
    label: expectString(record.label, `${path}.label`),
    href: expectString(record.href, `${path}.href`),
    source: expectString(record.source, `${path}.source`),
    note: expectString(record.note, `${path}.note`),
  };
}

function parsePollingEvidence(value: unknown, path: string): PollingEvidence {
  const record = expectRecord(value, path);
  const pollingAverage = expectRecord(record.polling_average, `${path}.polling_average`);

  return {
    collected_at: expectString(record.collected_at, `${path}.collected_at`),
    source_url: expectString(record.source_url, `${path}.source_url`),
    race: expectString(record.race, `${path}.race`),
    market_key: expectString(record.market_key, `${path}.market_key`),
    market_type: expectString(record.market_type, `${path}.market_type`) as PollingEvidence["market_type"],
    polling_average: {
      updated_at: expectString(pollingAverage.updated_at, `${path}.polling_average.updated_at`),
      leader: expectString(pollingAverage.leader, `${path}.polling_average.leader`),
      leader_share: expectNumber(pollingAverage.leader_share, `${path}.polling_average.leader_share`),
      runner_up: expectString(pollingAverage.runner_up, `${path}.polling_average.runner_up`),
      runner_up_share: expectNumber(pollingAverage.runner_up_share, `${path}.polling_average.runner_up_share`),
      spread: expectNumber(pollingAverage.spread, `${path}.polling_average.spread`),
      fair_yes_cents:
        pollingAverage.fair_yes_cents === undefined
          ? undefined
          : expectNumber(pollingAverage.fair_yes_cents, `${path}.polling_average.fair_yes_cents`),
    },
    latest_polls: expectArray(record.latest_polls, `${path}.latest_polls`).map((entry, index) => {
      const poll = expectRecord(entry, `${path}.latest_polls[${index}]`);
      const dates = expectRecord(poll.dates, `${path}.latest_polls[${index}].dates`);

      return {
        pollster: expectString(poll.pollster, `${path}.latest_polls[${index}].pollster`),
        dates: {
          start: expectString(dates.start, `${path}.latest_polls[${index}].dates.start`),
          end: expectString(dates.end, `${path}.latest_polls[${index}].dates.end`),
        },
        sample: expectString(poll.sample, `${path}.latest_polls[${index}].sample`),
        toplines: expectArray(poll.toplines, `${path}.latest_polls[${index}].toplines`).map((topline, toplineIndex) => {
          const toplineRecord = expectRecord(
            topline,
            `${path}.latest_polls[${index}].toplines[${toplineIndex}]`,
          );

          return {
            candidate: expectString(
              toplineRecord.candidate,
              `${path}.latest_polls[${index}].toplines[${toplineIndex}].candidate`,
            ),
            pct: expectNumber(toplineRecord.pct, `${path}.latest_polls[${index}].toplines[${toplineIndex}].pct`),
          };
        }),
        spread: expectString(poll.spread, `${path}.latest_polls[${index}].spread`),
      };
    }),
    trend_summary: expectString(record.trend_summary, `${path}.trend_summary`),
    evidence_links: expectArray(record.evidence_links, `${path}.evidence_links`).map((entry, index) =>
      parseEvidenceLink(entry, `${path}.evidence_links[${index}]`),
    ),
  };
}

export function parsePollingEvidenceFile(value: unknown): PollingEvidenceFile {
  const record = expectRecord(value, "pollingEvidence");

  return {
    evidence: expectArray(record.evidence, "pollingEvidence.evidence").map((entry, index) =>
      parsePollingEvidence(entry, `pollingEvidence.evidence[${index}]`),
    ),
  };
}
