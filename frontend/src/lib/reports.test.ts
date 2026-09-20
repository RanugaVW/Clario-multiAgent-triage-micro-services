import { describe, it, expect } from 'vitest';
import { parseDateRange, inRange, rangeLabel, ticketAnalytics, aiPerformance, percentile, type ReportTicket } from './reports';

const unbounded = { from: null, to: null };
const tk = (id: string, created_at: string, over: Partial<ReportTicket> & { cat?: string; pri?: string; sent?: string } = {}): ReportTicket => {
  const { cat, pri, sent, ...rest } = over;
  return {
    id, created_at, status: 'open', resolutions: [],
    ticket_classifications: cat || pri || sent ? [{ category: cat, priority: pri, sentiment: sent }] : [],
    ...rest,
  };
};

describe('parseDateRange', () => {
  it('accepts both, one, or neither bound', () => {
    expect(parseDateRange(null, null)).toEqual({ ok: true, range: unbounded });
    const r = parseDateRange('2026-09-01', '2026-09-30');
    expect(r.ok && r.range.from?.toISOString()).toBe('2026-09-01T00:00:00.000Z');
    expect(r.ok && r.range.to?.toISOString()).toBe('2026-09-30T23:59:59.999Z');
    expect(parseDateRange('2026-09-01', undefined).ok).toBe(true);
  });
  it('rejects malformed, impossible and reversed dates with a clear message', () => {
    expect(parseDateRange('01/09/2026', null)).toEqual({ ok: false, error: expect.stringContaining('from') });
    expect(parseDateRange(null, '2026-13-01')).toEqual({ ok: false, error: expect.stringContaining('to') });
    expect(parseDateRange('2026-02-31', null).ok).toBe(false); // would roll over to March
    expect(parseDateRange('2026-09-30', '2026-09-01')).toEqual({ ok: false, error: expect.stringContaining('after') });
  });
  it('treats a single-day range as that whole day', () => {
    const r = parseDateRange('2026-09-19', '2026-09-19');
    if (!r.ok) throw new Error('unexpected');
    expect(inRange('2026-09-19T00:00:00Z', r.range)).toBe(true);
    expect(inRange('2026-09-19T23:59:59Z', r.range)).toBe(true);
    expect(inRange('2026-09-20T00:00:00Z', r.range)).toBe(false);
    expect(inRange('2026-09-18T23:59:59Z', r.range)).toBe(false);
  });
  it('labels ranges for report headings', () => {
    expect(rangeLabel(unbounded)).toBe('All time');
    const r = parseDateRange('2026-09-01', '2026-09-30');
    expect(r.ok && rangeLabel(r.range)).toBe('2026-09-01 to 2026-09-30');
  });
  it('inRange rejects missing or unparsable timestamps', () => {
    expect(inRange(null, unbounded)).toBe(false);
    expect(inRange('nonsense', unbounded)).toBe(false);
  });
});

describe('ticketAnalytics', () => {
  const data: ReportTicket[] = [
    tk('a', '2026-09-01T10:00:00Z', { cat: 'Billing & Invoicing, Refunds', pri: 'High', sent: 'Frustrated', status: 'resolved', resolutions: [{ escalated: false }] }),
    tk('b', '2026-09-01T12:00:00Z', { cat: 'Refunds', pri: 'High', sent: 'Neutral', status: 'escalated', resolutions: [{ escalated: true }] }),
    tk('c', '2026-09-04T09:00:00Z', { cat: 'Authentication', pri: 'Low', sent: 'Neutral' }),
    tk('d', '2026-10-01T09:00:00Z'),
  ];

  it('counts totals and the three lifecycle buckets so that they add up', () => {
    const a = ticketAnalytics(data, unbounded);
    expect(a.total).toBe(4);
    expect(a.resolved).toBe(1);
    expect(a.awaitingHuman).toBe(1);
    expect(a.inProgress).toBe(2);
    expect(a.resolved + a.awaitingHuman + a.inProgress).toBe(a.total);
    expect(a.resolutionRate).toBeCloseTo(0.25);
  });

  it('applies the date range to everything', () => {
    const r = parseDateRange('2026-09-01', '2026-09-30');
    if (!r.ok) throw new Error('unexpected');
    const a = ticketAnalytics(data, r.range);
    expect(a.total).toBe(3);
    expect(a.byPriority.map((x) => x.label)).not.toContain('Unclassified');
  });

  it('keeps every figure inside the range, including resolved and awaiting-human counts', () => {
    const r = parseDateRange('2026-09-01', '2026-09-30');
    if (!r.ok) throw new Error('unexpected');
    const a = ticketAnalytics([
      ...data,
      tk('late-resolved', '2026-10-05T00:00:00Z', { status: 'resolved', resolutions: [{ escalated: false }] }),
      tk('late-escalated', '2026-10-06T00:00:00Z', { status: 'escalated' }),
    ], r.range);
    expect(a.total).toBe(3);
    expect(a.resolved).toBe(1);
    expect(a.awaitingHuman).toBe(1);
    expect(a.inProgress).toBe(1);
  });

  it('counts a multi-category ticket under each category and orders by count then name', () => {
    const a = ticketAnalytics(data, unbounded);
    expect(a.byCategory).toEqual([
      { label: 'Refunds', count: 2 },
      { label: 'Unclassified', count: 1 },
      { label: 'Authentication', count: 1 },
      { label: 'Billing & Invoicing', count: 1 },
    ].sort((x, y) => y.count - x.count || x.label.localeCompare(y.label)));
  });

  it('groups priority and sentiment, bucketing missing values as Unclassified', () => {
    const a = ticketAnalytics(data, unbounded);
    expect(a.byPriority).toContainEqual({ label: 'High', count: 2 });
    expect(a.byPriority).toContainEqual({ label: 'Unclassified', count: 1 });
    expect(a.bySentiment).toContainEqual({ label: 'Neutral', count: 2 });
  });

  it('zero-fills days with no tickets between the first and last', () => {
    const r = parseDateRange('2026-09-01', '2026-09-30');
    if (!r.ok) throw new Error('unexpected');
    const a = ticketAnalytics(data, r.range);
    expect(a.dailyVolume).toEqual([
      { date: '2026-09-01', count: 2 },
      { date: '2026-09-02', count: 0 },
      { date: '2026-09-03', count: 0 },
      { date: '2026-09-04', count: 1 },
    ]);
    expect(a.dailyVolume.reduce((s, d) => s + d.count, 0)).toBe(a.total);
  });

  it('handles an empty range without dividing by zero', () => {
    const a = ticketAnalytics([], unbounded);
    expect(a).toMatchObject({ total: 0, resolved: 0, resolutionRate: null, dailyVolume: [], byCategory: [] });
  });

  it('treats a ticket with status resolved as resolved even if its resolution row is missing', () => {
    expect(ticketAnalytics([tk('x', '2026-09-01T00:00:00Z', { status: 'resolved' })], unbounded).resolved).toBe(1);
  });

  it('does not treat an escalated ticket that later got a final answer as awaiting a human', () => {
    const t = tk('x', '2026-09-01T00:00:00Z', { status: 'resolved', resolutions: [{ escalated: true }, { escalated: false }] });
    const a = ticketAnalytics([t], unbounded);
    expect(a.awaitingHuman).toBe(0);
    expect(a.resolved).toBe(1);
  });
});

// ---------------------------------------------------------------- FR-052

describe('percentile (nearest rank)', () => {
  it('matches hand-computed values and ignores input order', () => {
    const v = [50, 10, 40, 20, 30];
    expect(percentile(v, 50)).toBe(30);
    expect(percentile(v, 95)).toBe(50);
    expect(percentile(v, 0)).toBe(10);
    expect(percentile(v, 100)).toBe(50);
    expect(v).toEqual([50, 10, 40, 20, 30]); // input not mutated
  });
  it('has no percentile of nothing', () => expect(percentile([], 50)).toBeNull());
});

describe('aiPerformance', () => {
  const ai = (id: string, created_at: string, over: Partial<ReportTicket> = {}): ReportTicket => ({
    id, created_at, status: 'resolved', ticket_classifications: [], ...over,
  });
  const data: ReportTicket[] = [
    ai('a', '2026-09-01T00:00:00Z', {
      resolutions: [{ escalated: false, total_latency_ms: 1000, total_llm_calls: 4, total_reflection_count: 0 }],
      ticket_validations: [{ passed: true, judge_ran: true }],
      response_evaluations: [{ overall_score: 5 }],
    }),
    ai('b', '2026-09-02T00:00:00Z', {
      resolutions: [{ escalated: true, total_latency_ms: 3000, total_llm_calls: 8, total_reflection_count: 2, escalation_reasons: ['Low RAG relevance', 'Mandatory Human Review'] }],
      ticket_validations: [{ passed: false, failure_type: 'policy', judge_ran: true }, { passed: true, judge_ran: false }],
      response_evaluations: [{ overall_score: 2 }],
    }),
    ai('c', '2026-09-03T00:00:00Z', {
      resolutions: [{ escalated: true, total_latency_ms: 2000, total_llm_calls: 6, total_reflection_count: 1, escalation_reasons: ['Mandatory Human Review'] }],
      ticket_validations: [{ passed: false, failure_type: null }],
    }),
    ai('d', '2026-09-04T00:00:00Z', { status: 'open' }), // not processed yet
  ];

  it('reports processing time from recorded latencies only', () => {
    const p = aiPerformance(data, unbounded).processingTime!;
    expect(p).toEqual({ samples: 3, meanMs: 2000, medianMs: 2000, p95Ms: 3000, maxMs: 3000 });
  });

  it('computes escalation rate over processed tickets and ranks reasons', () => {
    const e = aiPerformance(data, unbounded);
    expect(e.ticketsProcessed).toBe(3); // the unprocessed ticket is excluded from the denominator
    expect(e.escalation.escalated).toBe(2);
    expect(e.escalation.rate).toBeCloseTo(2 / 3);
    expect(e.escalation.reasons).toEqual([
      { label: 'Mandatory Human Review', count: 2 },
      { label: 'Low RAG relevance', count: 1 },
    ]);
  });

  it('computes validation outcomes and failure types', () => {
    const v = aiPerformance(data, unbounded).validation;
    expect(v).toMatchObject({ validated: 4, passed: 2, failed: 2, judged: 2 });
    expect(v.passRate).toBeCloseTo(0.5);
    expect(v.failureTypes).toEqual([{ label: 'policy', count: 1 }, { label: 'unspecified', count: 1 }]);
  });

  it('averages effort and summarises judge scores', () => {
    const r = aiPerformance(data, unbounded);
    expect(r.avgLlmCalls).toBeCloseTo(6);
    expect(r.avgReflections).toBeCloseTo(1);
    expect(r.judgeScores.evaluated).toBe(2);
    expect(r.judgeScores.meanOverall).toBeCloseTo(3.5);
    expect(r.judgeScores.distribution).toEqual([
      { label: '5', count: 1 }, { label: '4', count: 0 }, { label: '3', count: 0 }, { label: '2', count: 1 }, { label: '1', count: 0 },
    ]);
  });

  it('applies the date range to the AI figures too', () => {
    const r = parseDateRange('2026-09-01', '2026-09-01');
    if (!r.ok) throw new Error('unexpected');
    const a = aiPerformance(data, r.range);
    expect(a.ticketsProcessed).toBe(1);
    expect(a.escalation.escalated).toBe(0);
    expect(a.processingTime?.samples).toBe(1);
  });

  it('returns nulls, not NaN or zero, when there is nothing to measure', () => {
    const a = aiPerformance([], unbounded);
    expect(a.processingTime).toBeNull();
    expect(a.avgLlmCalls).toBeNull();
    expect(a.escalation).toEqual({ escalated: 0, rate: null, reasons: [] });
    expect(a.validation.passRate).toBeNull();
    expect(a.judgeScores.meanOverall).toBeNull();
  });

  it('ignores garbage values (negative/NaN latency, non-string reasons, undecided validations)', () => {
    const a = aiPerformance([ai('x', '2026-09-01T00:00:00Z', {
      resolutions: [{ escalated: true, total_latency_ms: -5, escalation_reasons: [null, 3, '  ', 'ok'] as unknown as string[] }, { escalated: false, total_latency_ms: NaN }],
      ticket_validations: [{ passed: null }],
    })], unbounded);
    expect(a.processingTime).toBeNull();
    expect(a.escalation.reasons).toEqual([{ label: 'ok', count: 1 }]);
    expect(a.validation.validated).toBe(0);
  });

  it('counts a ticket once for escalation even when it has several escalated resolution rows', () => {
    const a = aiPerformance([ai('x', '2026-09-01T00:00:00Z', { resolutions: [{ escalated: true }, { escalated: true }] })], unbounded);
    expect(a.escalation.escalated).toBe(1);
    expect(a.escalation.rate).toBe(1);
  });
});
