import { describe, it, expect } from 'vitest';
import {
  compactNumber, formatDuration, formatPercent, describeDelta, topWithOther, orderPriority, orderSentiment,
  withShares, gridMax, OTHER_LABEL,
} from './reportCharts';
import type { Delta } from './reports';

const d = (over: Partial<Delta>): Delta => ({ current: 1, previous: 1, changePct: null, change: null, ...over });

describe('number formatting', () => {
  it('compacts large numbers but keeps small ones exact', () => {
    expect([0, 7, 1284, 9999, 10_000, 12_940, 999_999, 1_000_000, 4_200_000].map(compactNumber)).toEqual(
      ['0', '7', '1,284', '9,999', '10K', '12.9K', '1,000K', '1M', '4.2M']
    );
  });
  it('formats durations in the unit a person would say', () => {
    expect([0, 450, 999, 1000, 2400, 59_999, 60_000, 150_000].map(formatDuration)).toEqual(
      ['0 ms', '450 ms', '999 ms', '1 s', '2.4 s', '60 s', '1 min', '2.5 min']
    );
    expect(formatDuration(null)).toBe('—');
    expect(formatDuration(Number.NaN)).toBe('—');
  });
  it('formats percentages and treats missing as a dash', () => {
    expect(formatPercent(0.256)).toBe('26%');
    expect(formatPercent(0.256, 1)).toBe('25.6%');
    expect(formatPercent(0)).toBe('0%');
    expect(formatPercent(null)).toBe('—');
  });
});

describe('describeDelta - wording and whether it is good news', () => {
  it('counts use relative %, and direction × upIsGood decides the tone', () => {
    expect(describeDelta(d({ changePct: 12.34 }), 'count', true)).toEqual({ text: '▲ 12.3%', direction: 'up', tone: 'good' });
    expect(describeDelta(d({ changePct: -12.34 }), 'count', true)).toEqual({ text: '▼ 12.3%', direction: 'down', tone: 'bad' });
    expect(describeDelta(d({ changePct: 12.34 }), 'count', false)).toMatchObject({ tone: 'bad' });
    expect(describeDelta(d({ changePct: -5 }), 'count', false)).toMatchObject({ tone: 'good' });
  });
  it('volume-like metrics with no good direction stay neutral', () => {
    expect(describeDelta(d({ changePct: 40 }), 'count', null)).toMatchObject({ direction: 'up', tone: 'neutral' });
  });
  it('rates are reported in percentage points, not relative %', () => {
    expect(describeDelta(d({ change: 0.25 }), 'rate', true)).toEqual({ text: '▲ 25 pts', direction: 'up', tone: 'good' });
    expect(describeDelta(d({ change: -0.031 }), 'rate', false)).toEqual({ text: '▼ 3.1 pts', direction: 'down', tone: 'good' });
  });
  it('a faster processing time is good news (duration, down is good)', () => {
    expect(describeDelta(d({ changePct: -50 }), 'duration', false)).toEqual({ text: '▼ 50%', direction: 'down', tone: 'good' });
  });
  it('scores use two decimals of points', () => {
    expect(describeDelta(d({ change: 0.5 }), 'score', true)).toEqual({ text: '▲ 0.50 pts', direction: 'up', tone: 'good' });
  });
  it('a negligible change says "No change" rather than an arrow, and is neutral', () => {
    expect(describeDelta(d({ changePct: 0.2 }), 'count', true)).toEqual({ text: 'No change', direction: 'flat', tone: 'neutral' });
    expect(describeDelta(d({ change: 0.01 }), 'score', true)).toMatchObject({ direction: 'flat', tone: 'neutral' });
    expect(describeDelta(d({ changePct: 0 }), 'count', true)).toMatchObject({ text: 'No change' });
  });
  it('has nothing to say when there is nothing to compare', () => {
    expect(describeDelta(d({ changePct: null }), 'count', true)).toBeNull();
    expect(describeDelta(d({ change: null }), 'rate', true)).toBeNull();
    expect(describeDelta(d({ changePct: Number.NaN }), 'count', true)).toBeNull();
  });
  it('always carries an arrow or words - never colour alone', () => {
    for (const changePct of [-80, -1, 1, 80]) expect(describeDelta(d({ changePct }), 'count', true)!.text).toMatch(/[▲▼]/);
  });
});

describe('topWithOther', () => {
  const rows = (n: number) => Array.from({ length: n }, (_, i) => ({ label: `c${i}`, count: n - i }));
  it('returns everything, sorted, when it fits', () => {
    expect(topWithOther(rows(3)).map((r) => r.label)).toEqual(['c0', 'c1', 'c2']);
  });
  it('folds the tail into one "Other" row and preserves the total', () => {
    const input = rows(12);
    const out = topWithOther(input, 8);
    expect(out).toHaveLength(8);
    expect(out[7].label).toBe(OTHER_LABEL);
    expect(out.reduce((s, r) => s + r.count, 0)).toBe(input.reduce((s, r) => s + r.count, 0));
    expect(out.slice(0, 7).map((r) => r.label)).toEqual(['c0', 'c1', 'c2', 'c3', 'c4', 'c5', 'c6']);
  });
  it('breaks ties by name so the order is stable, and does not mutate its input', () => {
    const input = [{ label: 'b', count: 1 }, { label: 'a', count: 1 }];
    expect(topWithOther(input).map((r) => r.label)).toEqual(['a', 'b']);
    expect(input.map((r) => r.label)).toEqual(['b', 'a']);
  });
  it('handles empty input', () => expect(topWithOther([])).toEqual([]));
});

describe('ordinal scales', () => {
  it('orders priority most-severe first and shows every level, zero included', () => {
    expect(orderPriority([{ label: 'Low', count: 5 }, { label: 'Critical', count: 1 }])).toEqual([
      { label: 'Critical', count: 1 }, { label: 'High', count: 0 }, { label: 'Medium', count: 0 }, { label: 'Low', count: 5 },
    ]);
  });
  it('is case-insensitive and folds unknown labels (and "Unclassified") into one Unclassified row', () => {
    const out = orderPriority([{ label: 'high', count: 2 }, { label: 'Urgent', count: 3 }, { label: 'Unclassified', count: 4 }]);
    expect(out.find((r) => r.label === 'High')!.count).toBe(2);
    expect(out[out.length - 1]).toEqual({ label: 'Unclassified', count: 7 });
  });
  it('omits the Unclassified row when nothing is unclassified', () => {
    expect(orderPriority([]).some((r) => r.label === 'Unclassified')).toBe(false);
  });
  it('orders the sentiment scale most-negative first', () => {
    expect(orderSentiment([{ label: 'Neutral', count: 2 }, { label: 'Frustrated', count: 1 }]).map((r) => r.label)).toEqual(
      ['Frustrated', 'Negative', 'Neutral']
    );
  });
  it('the ordinal rows always sum to the input total', () => {
    const rows = [{ label: 'High', count: 4 }, { label: 'weird', count: 2 }, { label: 'Low', count: 1 }];
    expect(orderPriority(rows).reduce((s, r) => s + r.count, 0)).toBe(7);
  });
});

describe('shares and grids', () => {
  it('computes shares that sum to 1, and zeros for an empty total', () => {
    const s = withShares([{ label: 'a', count: 1 }, { label: 'b', count: 3 }]);
    expect(s.map((x) => x.share)).toEqual([0.25, 0.75]);
    expect(withShares([{ label: 'a', count: 0 }]).map((x) => x.share)).toEqual([0]);
    expect(withShares([])).toEqual([]);
  });
  it('gridMax is at least 1 so an empty heatmap never divides by zero', () => {
    expect(gridMax([[0, 0], [0, 0]])).toBe(1);
    expect(gridMax([[1, 5], [2, 3]])).toBe(5);
    expect(gridMax([])).toBe(1);
  });
});

import { meterSeverity, clampUnit, truncateLabel, shortDate } from './reportCharts';

describe('meterSeverity', () => {
  const higher = { worseWhen: 'higher' as const, warn: 0.3, danger: 0.5 };
  const lower = { worseWhen: 'lower' as const, warn: 0.9, danger: 0.7 };
  it('escalates as a "higher is worse" rate climbs, inclusive at the limits', () => {
    expect([0.1, 0.29, 0.3, 0.49, 0.5, 0.9].map((v) => meterSeverity(v, higher))).toEqual(
      ['normal', 'normal', 'warning', 'warning', 'danger', 'danger']
    );
  });
  it('escalates as a "lower is worse" rate falls, inclusive at the limits', () => {
    expect([0.99, 0.91, 0.9, 0.71, 0.7, 0.2].map((v) => meterSeverity(v, lower))).toEqual(
      ['normal', 'normal', 'warning', 'warning', 'danger', 'danger']
    );
  });
  it('treats no data as normal - a missing measurement is not an alarm', () => {
    expect(meterSeverity(null, higher)).toBe('normal');
    expect(meterSeverity(Number.NaN, lower)).toBe('normal');
  });
});

describe('small helpers', () => {
  it('clampUnit keeps drawing inside the track', () => {
    expect([-0.5, 0, 0.4, 1, 3].map(clampUnit)).toEqual([0, 0, 0.4, 1, 1]);
  });
  it('truncateLabel shortens with an ellipsis only when needed', () => {
    expect(truncateLabel('Refunds')).toBe('Refunds');
    expect(truncateLabel('Billing & Invoicing and Subscription Management', 20)).toBe('Billing & Invoicing…');
    expect(truncateLabel('x'.repeat(24))).toBe('x'.repeat(24));
  });
  it('shortDate formats ISO days and passes anything else through', () => {
    expect(shortDate('2026-09-19')).toBe('Sep 19');
    expect(shortDate('2026-01-05')).toBe('Jan 5');
    expect(shortDate('Week of 2026-08-31')).toBe('Week of 2026-08-31');
  });
});

import { niceScale, axisWidth, lifecycleTakeaway, sentimentTakeaway, priorityTakeaway } from './reportCharts';

describe('niceScale', () => {
  it('produces round ticks, at most five intervals, from zero', () => {
    expect(niceScale(40)).toEqual({ max: 40, ticks: [0, 10, 20, 30, 40] });
    expect(niceScale(41)).toEqual({ max: 50, ticks: [0, 10, 20, 30, 40, 50] });
    expect(niceScale(191)).toEqual({ max: 200, ticks: [0, 50, 100, 150, 200] });
    expect(niceScale(818)).toEqual({ max: 1000, ticks: [0, 200, 400, 600, 800, 1000] });
    expect(niceScale(3)).toEqual({ max: 3, ticks: [0, 1, 2, 3] });
    expect(niceScale(7)).toEqual({ max: 8, ticks: [0, 2, 4, 6, 8] });
    expect(niceScale(172)).toEqual({ max: 200, ticks: [0, 50, 100, 150, 200] });
  });
  it('the maximum is never below the value and every tick is an integer multiple of one step', () => {
    for (const v of [1.5, 2, 6, 13, 27, 99, 101, 250, 999, 1001, 4800, 12345, 1e6]) {
      const s = niceScale(v);
      expect(s.max).toBeGreaterThanOrEqual(v);
      expect(s.ticks.length).toBeLessThanOrEqual(6);
      expect(s.ticks.length).toBeGreaterThanOrEqual(3); // never a bare two-line axis for real data
      expect(s.ticks[0]).toBe(0);
      expect(s.ticks[s.ticks.length - 1]).toBe(s.max);
      const step = s.ticks[1] - s.ticks[0];
      expect(s.ticks.every((t, i) => t === i * step)).toBe(true);
    }
  });
  it('gives an empty chart a usable 0-1 axis, and survives bad input', () => {
    for (const v of [0, 0.4, 1, -5, Number.NaN, Infinity]) expect(niceScale(v)).toEqual({ max: 1, ticks: [0, 1] });
  });
});

describe('axisWidth', () => {
  it('is wide enough for the longest label - "1,000" needs more room than "50"', () => {
    expect(axisWidth(50)).toBe(36);
    expect(axisWidth(1000)).toBeGreaterThan(axisWidth(50));
    expect(axisWidth(1000)).toBeGreaterThanOrEqual('1,000'.length * 8);
    expect(axisWidth(20000)).toBeLessThan(axisWidth(1000)); // '20K' is shorter than '1,000'
  });
});

describe('takeaways', () => {
  it('states the human-review backlog in plain words', () => {
    expect(lifecycleTakeaway(0, 10)).toBe('Nothing is waiting for a human reviewer.');
    expect(lifecycleTakeaway(1, 10)).toBe('1 ticket is waiting for a human reviewer.');
    expect(lifecycleTakeaway(155, 715)).toBe('155 tickets are waiting for a human reviewer.');
    expect(lifecycleTakeaway(0, 0)).toBe('');
  });
  it('computes sentiment over classified tickets only', () => {
    const rows = [{ label: 'Neutral', count: 6 }, { label: 'Negative', count: 3 }, { label: 'Frustrated', count: 1 }, { label: 'Unclassified', count: 50 }];
    expect(sentimentTakeaway(rows)).toBe('40% of classified tickets are negative or frustrated.');
    expect(sentimentTakeaway([{ label: 'Unclassified', count: 5 }])).toBe('');
    expect(sentimentTakeaway([])).toBe('');
  });
  it('computes high/critical priority over classified tickets only', () => {
    const rows = [{ label: 'Critical', count: 1 }, { label: 'High', count: 1 }, { label: 'Medium', count: 4 }, { label: 'Low', count: 4 }, { label: 'Unclassified', count: 9 }];
    expect(priorityTakeaway(rows)).toBe('20% of classified tickets are high or critical priority.');
    expect(priorityTakeaway([])).toBe('');
  });
});
