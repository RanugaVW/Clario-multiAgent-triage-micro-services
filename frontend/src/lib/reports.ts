// Reporting rules for FR-051 (ticket analytics), FR-052 (AI performance) and FR-053 (export).
// Pure functions - no fetch, no React - so the numbers an administrator reads (and later
// exports) can be verified exactly. Dates are treated as UTC calendar days throughout so the
// server and the browser can never disagree about which day a ticket belongs to.
import { splitCategories } from './classification';

// ---------------------------------------------------------------- date ranges

export type DateRange = { from: Date | null; to: Date | null }; // both inclusive; `to` is the last millisecond of its day

const DAY_RE = /^(\d{4})-(\d{2})-(\d{2})$/;

function parseDay(value: string): Date | null {
  const m = DAY_RE.exec(value);
  if (!m) return null;
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const date = new Date(Date.UTC(y, mo - 1, d));
  // Reject rollovers such as 2026-02-31 (JS would silently turn it into March 3rd).
  return date.getUTCFullYear() === y && date.getUTCMonth() === mo - 1 && date.getUTCDate() === d ? date : null;
}

export type RangeResult = { ok: true; range: DateRange } | { ok: false; error: string };

/** Parses optional `YYYY-MM-DD` bounds. A missing bound means "unbounded on that side". */
export function parseDateRange(from: string | null | undefined, to: string | null | undefined): RangeResult {
  const start = from ? parseDay(from) : null;
  const endDay = to ? parseDay(to) : null;
  if (from && !start) return { ok: false, error: 'from must be a valid date in YYYY-MM-DD format' };
  if (to && !endDay) return { ok: false, error: 'to must be a valid date in YYYY-MM-DD format' };
  const end = endDay ? new Date(endDay.getTime() + 24 * 3600_000 - 1) : null;
  if (start && end && start.getTime() > end.getTime()) return { ok: false, error: 'from must not be after to' };
  return { ok: true, range: { from: start, to: end } };
}

export function inRange(value: string | null | undefined, range: DateRange): boolean {
  if (!value) return false;
  const ms = Date.parse(value);
  if (Number.isNaN(ms)) return false;
  if (range.from && ms < range.from.getTime()) return false;
  if (range.to && ms > range.to.getTime()) return false;
  return true;
}

export function rangeLabel(range: DateRange): string {
  const day = (d: Date | null) => (d ? d.toISOString().slice(0, 10) : null);
  const [a, b] = [day(range.from), day(range.to)];
  if (!a && !b) return 'All time';
  if (a && b) return `${a} to ${b}`;
  return a ? `From ${a}` : `Up to ${b}`;
}

// ---------------------------------------------------------------- ticket analytics (FR-051)

export type ReportTicket = {
  id: string;
  status: string;
  created_at: string;
  ticket_classifications?: { category?: string | null; priority?: string | null; sentiment?: string | null }[] | null;
  resolutions?: {
    escalated: boolean;
    resolved_at?: string | null;
    total_latency_ms?: number | null;
    total_llm_calls?: number | null;
    total_reflection_count?: number | null;
    escalation_reasons?: unknown;
  }[] | null;
  ticket_validations?: { passed?: boolean | null; failure_type?: string | null; judge_ran?: boolean | null }[] | null;
  response_evaluations?: { overall_score?: number | null; evaluation_latency_ms?: number | null }[] | null;
};

export type CountRow = { label: string; count: number };

export type TicketAnalytics = {
  range: DateRange;
  total: number;
  resolved: number;
  awaitingHuman: number;
  inProgress: number;
  resolutionRate: number | null; // 0..1, null when there are no tickets
  byStatus: CountRow[];
  byCategory: CountRow[];
  byPriority: CountRow[];
  bySentiment: CountRow[];
  dailyVolume: { date: string; count: number }[]; // every day in the observed span, zero-filled
};

const UNKNOWN = 'Unclassified';

function tally(values: string[]): CountRow[] {
  const counts = new Map<string, number>();
  for (const v of values) counts.set(v, (counts.get(v) ?? 0) + 1);
  return [...counts.entries()]
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

const isResolved = (t: ReportTicket) => (t.resolutions ?? []).some((r) => !r.escalated) || t.status === 'resolved';
const isAwaitingHuman = (t: ReportTicket) =>
  !isResolved(t) && ((t.resolutions ?? []).some((r) => r.escalated) || t.status === 'escalated');

export function ticketsInRange<T extends { created_at: string }>(tickets: T[], range: DateRange): T[] {
  return tickets.filter((t) => inRange(t.created_at, range));
}

export function ticketAnalytics(allTickets: ReportTicket[], range: DateRange): TicketAnalytics {
  const tickets = ticketsInRange(allTickets, range);
  const resolved = tickets.filter(isResolved).length;
  const awaitingHuman = tickets.filter(isAwaitingHuman).length;

  const days = new Map<string, number>();
  for (const t of tickets) {
    const day = new Date(t.created_at).toISOString().slice(0, 10);
    days.set(day, (days.get(day) ?? 0) + 1);
  }
  const dailyVolume: { date: string; count: number }[] = [];
  if (days.size) {
    const sorted = [...days.keys()].sort();
    const end = Date.parse(sorted[sorted.length - 1]);
    for (let ms = Date.parse(sorted[0]); ms <= end; ms += 24 * 3600_000) {
      const date = new Date(ms).toISOString().slice(0, 10);
      dailyVolume.push({ date, count: days.get(date) ?? 0 });
    }
  }

  return {
    range,
    total: tickets.length,
    resolved,
    awaitingHuman,
    inProgress: tickets.length - resolved - awaitingHuman,
    resolutionRate: tickets.length ? resolved / tickets.length : null,
    byStatus: tally(tickets.map((t) => t.status || 'unknown')),
    // A ticket can carry several categories; it counts once under each (same rule as the admin page).
    byCategory: tally(
      tickets.flatMap((t) => {
        const cats = splitCategories(t.ticket_classifications?.[0]?.category);
        return cats.length ? cats : [UNKNOWN];
      })
    ),
    byPriority: tally(tickets.map((t) => t.ticket_classifications?.[0]?.priority?.trim() || UNKNOWN)),
    bySentiment: tally(tickets.map((t) => t.ticket_classifications?.[0]?.sentiment?.trim() || UNKNOWN)),
    dailyVolume,
  };
}

// ---------------------------------------------------------------- AI performance (FR-052)

export type LatencyStats = { samples: number; meanMs: number; medianMs: number; p95Ms: number; maxMs: number };

export type AiPerformance = {
  range: DateRange;
  ticketsProcessed: number; // tickets in the period that the AI pipeline produced an outcome for
  processingTime: LatencyStats | null; // null when no latency was recorded
  avgLlmCalls: number | null;
  avgReflections: number | null;
  escalation: { escalated: number; rate: number | null; reasons: CountRow[] };
  validation: {
    validated: number;
    passed: number;
    failed: number;
    passRate: number | null;
    failureTypes: CountRow[];
    judged: number; // validations where the LLM judge actually ran
  };
  judgeScores: { evaluated: number; meanOverall: number | null; distribution: CountRow[] }; // 5..1
};

const mean = (xs: number[]) => (xs.length ? xs.reduce((s, x) => s + x, 0) / xs.length : null);
const finite = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x);

/** Nearest-rank percentile on a sorted copy (p in 0..100). Empty input has no percentile. */
export function percentile(values: number[], p: number): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const rank = Math.ceil((p / 100) * sorted.length);
  return sorted[Math.min(sorted.length, Math.max(1, rank)) - 1];
}

export function aiPerformance(allTickets: ReportTicket[], range: DateRange): AiPerformance {
  const tickets = ticketsInRange(allTickets, range);
  const resolutions = tickets.flatMap((t) => t.resolutions ?? []);

  const latencies = resolutions.map((r) => r.total_latency_ms).filter(finite).filter((x) => x >= 0);
  const processingTime: LatencyStats | null = latencies.length
    ? {
        samples: latencies.length,
        meanMs: mean(latencies) as number,
        medianMs: percentile(latencies, 50) as number,
        p95Ms: percentile(latencies, 95) as number,
        maxMs: Math.max(...latencies),
      }
    : null;

  // "Processed" = the pipeline recorded an outcome. A ticket counts once even with several resolution rows.
  const processed = tickets.filter((t) => (t.resolutions ?? []).length > 0);
  const escalatedTickets = processed.filter((t) => (t.resolutions ?? []).some((r) => r.escalated));
  const reasons = tally(
    escalatedTickets.flatMap((t) =>
      (t.resolutions ?? [])
        .filter((r) => r.escalated)
        .flatMap((r) => (Array.isArray(r.escalation_reasons) ? r.escalation_reasons : []))
        .filter((x): x is string => typeof x === 'string' && x.trim() !== '')
        .map((x) => x.trim())
    )
  );

  const validations = tickets.flatMap((t) => t.ticket_validations ?? []);
  const passed = validations.filter((v) => v.passed === true).length;
  const failed = validations.filter((v) => v.passed === false).length;
  const decided = passed + failed; // a row with `passed` still null is neither

  const scores = tickets.flatMap((t) => t.response_evaluations ?? []).map((e) => e.overall_score).filter(finite);

  return {
    range,
    ticketsProcessed: processed.length,
    processingTime,
    avgLlmCalls: mean(resolutions.map((r) => r.total_llm_calls).filter(finite)),
    avgReflections: mean(resolutions.map((r) => r.total_reflection_count).filter(finite)),
    escalation: {
      escalated: escalatedTickets.length,
      rate: processed.length ? escalatedTickets.length / processed.length : null,
      reasons,
    },
    validation: {
      validated: decided,
      passed,
      failed,
      passRate: decided ? passed / decided : null,
      failureTypes: tally(validations.filter((v) => v.passed === false).map((v) => v.failure_type?.trim() || 'unspecified')),
      judged: validations.filter((v) => v.judge_ran === true).length,
    },
    judgeScores: {
      evaluated: scores.length,
      meanOverall: mean(scores),
      distribution: [5, 4, 3, 2, 1].map((n) => ({ label: String(n), count: scores.filter((s) => Math.round(s) === n).length })),
    },
  };
}
