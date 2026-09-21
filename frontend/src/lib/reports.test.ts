import { describe, it, expect } from 'vitest';
import {
  parseDateRange, inRange, rangeLabel, ticketAnalytics, aiPerformance, percentile, arrivalGrid, volumeSeries,
  latencyBuckets, previousRange, comparePeriods, type ReportTicket,
} from './reports';

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


// ---------------------------------------------------------------- chart engine

describe('arrivalGrid (weekday x hour heatmap data)', () => {
  it('places tickets by UTC weekday (Monday first) and hour', () => {
    // 2026-09-21 is a Monday; 2026-09-27 is a Sunday.
    const grid = arrivalGrid([
      { created_at: '2026-09-21T09:15:00Z' },
      { created_at: '2026-09-21T09:59:59Z' },
      { created_at: '2026-09-27T23:00:00Z' },
      { created_at: '2026-09-23T00:00:00Z' }, // Wednesday midnight
    ]);
    expect(grid).toHaveLength(7);
    expect(grid.every((row) => row.length === 24)).toBe(true);
    expect(grid[0][9]).toBe(2);
    expect(grid[6][23]).toBe(1);
    expect(grid[2][0]).toBe(1);
    expect(grid.flat().reduce((a, b) => a + b, 0)).toBe(4);
  });
  it('ignores unparsable timestamps and is all zeros when empty', () => {
    expect(arrivalGrid([{ created_at: 'nope' }]).flat().every((n) => n === 0)).toBe(true);
    expect(arrivalGrid([]).flat().every((n) => n === 0)).toBe(true);
  });
  it('is part of the analytics and totals the tickets in range', () => {
    const a = ticketAnalytics(
      [tk('a', '2026-09-21T09:00:00Z'), tk('b', '2026-09-22T10:00:00Z'), tk('c', '2027-01-01T10:00:00Z')],
      { from: null, to: new Date('2026-12-31T23:59:59Z') }
    );
    expect(a.arrivals.flat().reduce((x, y) => x + y, 0)).toBe(a.total);
    expect(a.total).toBe(2);
  });
});

describe('volumeSeries', () => {
  const days = (n: number, count = (i: number) => i) =>
    Array.from({ length: n }, (_, i) => ({ date: new Date(Date.UTC(2026, 8, 1 + i)).toISOString().slice(0, 10), count: count(i) }));

  it('plots short spans daily with a trailing 7-day average that starts only when 7 days exist', () => {
    const s = volumeSeries(days(10, () => 7));
    expect(s.granularity).toBe('day');
    expect(s.points).toHaveLength(10);
    expect(s.points.slice(0, 6).every((p) => p.average === null)).toBe(true);
    expect(s.points[6].average).toBe(7);
    expect(s.points[9].average).toBe(7);
  });
  it('averages the trailing window exactly', () => {
    const s = volumeSeries(days(8, (i) => i)); // counts 0..7
    expect(s.points[6].average).toBeCloseTo((0 + 1 + 2 + 3 + 4 + 5 + 6) / 7);
    expect(s.points[7].average).toBeCloseTo((1 + 2 + 3 + 4 + 5 + 6 + 7) / 7);
  });
  it('groups a long span into 7-day buckets counted from the first day, and preserves the total', () => {
    const daily = days(120, () => 2); // starts Tue 2026-09-01
    const s = volumeSeries(daily);
    expect(s.granularity).toBe('week');
    expect(s.points.reduce((sum, p) => sum + p.count, 0)).toBe(240);
    expect(s.points[0]).toMatchObject({ date: '2026-09-01', label: 'Week of 2026-09-01', count: 14, days: 7 });
    expect(s.points[1].date).toBe('2026-09-08');
  });
  it('flags only the final bucket as partial, so the chart can say so instead of showing a false dive', () => {
    const s = volumeSeries(days(120, () => 2)); // 17 full weeks + 1 day
    expect(s.points).toHaveLength(18);
    expect(s.points.slice(0, 17).every((p) => p.days === 7)).toBe(true);
    expect(s.points[17]).toMatchObject({ days: 1, count: 2 });
    expect(volumeSeries(days(98, () => 1)).points.every((p) => p.days === 7)).toBe(true); // exact multiple: no partial
  });
  it('a daily point covers one day', () => {
    expect(volumeSeries(days(3)).points.every((p) => p.days === 1)).toBe(true);
  });
  it('handles an empty series', () => {
    expect(volumeSeries([])).toEqual({ granularity: 'day', points: [] });
  });
});

describe('latencyBuckets', () => {
  it('assigns each duration to the right band, with the upper edge belonging to the next band', () => {
    const b = latencyBuckets([0, 999, 1000, 1999, 2000, 4999, 5000, 9999, 10000, 29999, 30000, 500000]);
    expect(b.map((x) => x.count)).toEqual([2, 2, 2, 2, 2, 2]);
    expect(b.map((x) => x.label)).toEqual(['<1 s', '1–2 s', '2–5 s', '5–10 s', '10–30 s', '30 s+']);
  });
  it('is all zeros for no data, and its total equals the sample count', () => {
    expect(latencyBuckets([]).every((x) => x.count === 0)).toBe(true);
    expect(latencyBuckets([100, 3000, 3000]).reduce((s, x) => s + x.count, 0)).toBe(3);
  });
  it('is exposed on aiPerformance', () => {
    const a = aiPerformance(
      [{ id: 'x', status: 'resolved', created_at: '2026-09-01T00:00:00Z', resolutions: [{ escalated: false, total_latency_ms: 1500 }, { escalated: false, total_latency_ms: 40000 }] }],
      unbounded
    );
    expect(a.latencyBuckets.find((b) => b.label === '1–2 s')?.count).toBe(1);
    expect(a.latencyBuckets.find((b) => b.label === '30 s+')?.count).toBe(1);
  });
});

describe('previousRange / comparePeriods', () => {
  const range = (from: string, to: string) => {
    const r = parseDateRange(from, to);
    if (!r.ok) throw new Error('bad range');
    return r.range;
  };

  it('is the equal-length window ending the millisecond before the range starts', () => {
    const prev = previousRange(range('2026-09-08', '2026-09-14'))!; // 7 days
    expect(prev.from!.toISOString()).toBe('2026-09-01T00:00:00.000Z');
    expect(prev.to!.toISOString()).toBe('2026-09-07T23:59:59.999Z');
  });
  it('has no previous period for an open-ended range', () => {
    expect(previousRange({ from: null, to: null })).toBeNull();
    expect(previousRange({ from: new Date(), to: null })).toBeNull();
    expect(comparePeriods([], { from: null, to: null })).toBeNull();
  });

  const data: ReportTicket[] = [
    // previous week: 2 tickets, 1 resolved
    { id: 'p1', status: 'resolved', created_at: '2026-09-02T10:00:00Z', resolutions: [{ escalated: false, total_latency_ms: 4000 }], ticket_validations: [{ passed: true }], response_evaluations: [{ overall_score: 3 }] },
    { id: 'p2', status: 'open', created_at: '2026-09-03T10:00:00Z', resolutions: [] },
    // current week: 4 tickets, 3 resolved, 1 escalated
    { id: 'c1', status: 'resolved', created_at: '2026-09-09T10:00:00Z', resolutions: [{ escalated: false, total_latency_ms: 2000 }], ticket_validations: [{ passed: true }], response_evaluations: [{ overall_score: 5 }] },
    { id: 'c2', status: 'resolved', created_at: '2026-09-10T10:00:00Z', resolutions: [{ escalated: false, total_latency_ms: 2000 }], ticket_validations: [{ passed: true }] },
    { id: 'c3', status: 'resolved', created_at: '2026-09-11T10:00:00Z', resolutions: [{ escalated: false, total_latency_ms: 2000 }], ticket_validations: [{ passed: false }] },
    { id: 'c4', status: 'escalated', created_at: '2026-09-12T10:00:00Z', resolutions: [{ escalated: true, total_latency_ms: 2000 }] },
  ];

  it('reports current vs previous for counts with relative change, and for rates with point change', () => {
    const c = comparePeriods(data, range('2026-09-08', '2026-09-14'))!;
    expect(c.previousLabel).toBe('2026-09-01 to 2026-09-07');
    expect(c.tickets).toMatchObject({ current: 4, previous: 2, changePct: 100, change: 2 });
    expect(c.resolved).toMatchObject({ current: 3, previous: 1, changePct: 200 });
    expect(c.resolutionRate.current).toBeCloseTo(0.75);
    expect(c.resolutionRate.previous).toBeCloseTo(0.5);
    expect(c.resolutionRate.change).toBeCloseTo(0.25); // +25 percentage points, expressed 0..1
    expect(c.medianProcessingMs).toMatchObject({ current: 2000, previous: 4000, changePct: -50 });
    expect(c.judgeScore).toMatchObject({ current: 5, previous: 3 });
    expect(c.validationPassRate.current).toBeCloseTo(2 / 3);
    expect(c.escalationRate.current).toBeCloseTo(0.25);
    expect(c.escalationRate.previous).toBe(0); // 0 of 1 processed
  });
  it('gives no relative change when the previous figure is zero, but still the absolute one', () => {
    const c = comparePeriods(data, range('2026-09-08', '2026-09-14'))!;
    expect(c.escalationRate.changePct).toBeNull();
    expect(c.escalationRate.change).toBeCloseTo(0.25);
  });
  it('is null-safe when the previous period is empty', () => {
    const c = comparePeriods(data, range('2026-09-15', '2026-09-21'))!; // previous = the busy week, current = empty
    expect(c.tickets).toMatchObject({ current: 0, previous: 4, changePct: -100 });
    expect(c.medianProcessingMs.current).toBeNull();
    expect(c.medianProcessingMs.changePct).toBeNull();
    const none = comparePeriods([], range('2026-09-08', '2026-09-14'))!;
    expect(none.tickets).toMatchObject({ current: 0, previous: 0, changePct: null });
    expect(none.resolutionRate).toMatchObject({ current: null, previous: null, change: null });
  });
});
