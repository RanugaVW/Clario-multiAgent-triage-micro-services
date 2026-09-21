// Presentation rules for the admin reports dashboard: how raw report rows become chart-ready data, and how figures are
// worded. Pure - no React, no chart library - so the decisions a reader relies on (ordering, folding, what counts as an
// improvement) are unit-tested rather than buried in JSX.
import type { CountRow, Delta } from './reports';

// ---------------------------------------------------------------- number formatting

const ONE_DECIMAL = new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 });
const INTEGER = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });

/** 1,284 / 12.9K / 4.2M - compact for tiles, exact (thousands-separated) below 10,000. */
export function compactNumber(n: number): string {
  const abs = Math.abs(n);
  if (abs < 10_000) return INTEGER.format(n);
  if (abs < 1_000_000) return `${ONE_DECIMAL.format(n / 1_000)}K`;
  return `${ONE_DECIMAL.format(n / 1_000_000)}M`;
}

export function formatDuration(ms: number | null): string {
  if (ms === null || !Number.isFinite(ms)) return '—';
  if (ms < 1_000) return `${Math.round(ms)} ms`;
  if (ms < 60_000) return `${ONE_DECIMAL.format(ms / 1_000)} s`;
  return `${ONE_DECIMAL.format(ms / 60_000)} min`;
}

export function formatPercent(rate: number | null, digits = 0): string {
  return rate === null || !Number.isFinite(rate) ? '—' : `${(rate * 100).toFixed(digits)}%`;
}

// ---------------------------------------------------------------- deltas

export type DeltaKind = 'count' | 'rate' | 'duration' | 'score';
export type DeltaTone = 'good' | 'bad' | 'neutral';
export type DeltaView = {
  /** "▲ 12%" / "▼ 3.5 pts" / "No change" - always carries an arrow or words, never colour alone. */
  text: string;
  direction: 'up' | 'down' | 'flat';
  tone: DeltaTone;
};

/**
 * How a change is worded and whether it is good news. Tone = direction × whether "up" is good for that metric
 * (more tickets is neither good nor bad; a higher escalation rate is bad; a faster processing time is good).
 * Returns null when there is nothing meaningful to compare against.
 */
export function describeDelta(d: Delta, kind: DeltaKind, upIsGood: boolean | null): DeltaView | null {
  const value = kind === 'count' || kind === 'duration' ? d.changePct : d.change === null ? null : kind === 'rate' ? d.change * 100 : d.change;
  if (value === null || !Number.isFinite(value)) return null;

  const magnitude = Math.abs(value);
  const flat = kind === 'score' ? magnitude < 0.05 : magnitude < 0.5;
  const direction = flat ? 'flat' : value > 0 ? 'up' : 'down';
  const unit = kind === 'rate' ? ' pts' : kind === 'score' ? ' pts' : '%';
  const shown = kind === 'score' ? magnitude.toFixed(2) : ONE_DECIMAL.format(magnitude);

  const text = flat ? 'No change' : `${direction === 'up' ? '▲' : '▼'} ${shown}${unit}`;
  const tone: DeltaTone =
    direction === 'flat' || upIsGood === null ? 'neutral' : (direction === 'up') === upIsGood ? 'good' : 'bad';
  return { text, direction, tone };
}

// ---------------------------------------------------------------- category folding

export const OTHER_LABEL = 'Other';

/**
 * Keeps the biggest `max` rows and folds the tail into one "Other" row, so a long tail never becomes a wall of hairline
 * bars (nor a generated ninth colour). "Unclassified" is a real bucket and is never folded into "Other" implicitly
 * unless it falls outside the top rows.
 */
export function topWithOther(rows: CountRow[], max = 8): CountRow[] {
  const sorted = [...rows].sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
  if (sorted.length <= max) return sorted;
  const head = sorted.slice(0, max - 1);
  const tail = sorted.slice(max - 1);
  return [...head, { label: OTHER_LABEL, count: tail.reduce((s, r) => s + r.count, 0) }];
}

// ---------------------------------------------------------------- ordinal scales

const UNCLASSIFIED = 'Unclassified';

function inOrder(rows: CountRow[], order: readonly string[]): CountRow[] {
  const byLabel = new Map(rows.map((r) => [r.label.toLowerCase(), r]));
  const known = order.map((label) => ({ label, count: byLabel.get(label.toLowerCase())?.count ?? 0 }));
  const knownKeys = new Set(order.map((l) => l.toLowerCase()));
  // Anything outside the vocabulary (and the explicit "Unclassified" bucket) is one honest, de-emphasised row.
  const other = rows.filter((r) => !knownKeys.has(r.label.toLowerCase())).reduce((s, r) => s + r.count, 0);
  return other > 0 ? [...known, { label: UNCLASSIFIED, count: other }] : known;
}

/** Most severe first. Every level is always shown (zero included) so two periods line up. */
export const PRIORITY_ORDER = ['Critical', 'High', 'Medium', 'Low'] as const;
/** The classifier's sentiment scale, most negative first. */
export const SENTIMENT_ORDER = ['Frustrated', 'Negative', 'Neutral'] as const;

export const orderPriority = (rows: CountRow[]) => inOrder(rows, PRIORITY_ORDER);
export const orderSentiment = (rows: CountRow[]) => inOrder(rows, SENTIMENT_ORDER);

// ---------------------------------------------------------------- shares

export type Share = { label: string; count: number; share: number };

/** Adds each row's share of the total (0..1). A zero total yields zero shares, never NaN. */
export function withShares(rows: CountRow[]): Share[] {
  const total = rows.reduce((s, r) => s + r.count, 0);
  return rows.map((r) => ({ ...r, share: total === 0 ? 0 : r.count / total }));
}

/** Maximum of a numeric grid, floored at 1 so an empty heatmap does not divide by zero. */
export function gridMax(grid: number[][]): number {
  return Math.max(1, ...grid.map((row) => Math.max(0, ...row)));
}

// ---------------------------------------------------------------- meters

export type MeterSeverity = 'normal' | 'warning' | 'danger';

/**
 * Where a rate sits relative to its limits. `worseWhen: 'higher'` (escalation rate) escalates as the value climbs;
 * `'lower'` (validation pass rate) escalates as it falls. A missing value is "normal": no data is not an alarm.
 */
export function meterSeverity(
  value: number | null,
  opts: { worseWhen: 'higher' | 'lower'; warn: number; danger: number }
): MeterSeverity {
  if (value === null || !Number.isFinite(value)) return 'normal';
  const past = (limit: number) => (opts.worseWhen === 'higher' ? value >= limit : value <= limit);
  if (past(opts.danger)) return 'danger';
  if (past(opts.warn)) return 'warning';
  return 'normal';
}

/** Clamps a rate into 0..1 for drawing; the number shown to the reader is never clamped. */
export const clampUnit = (v: number) => Math.min(1, Math.max(0, v));

/** Long labels are shortened for axes; the full text stays available in the tooltip and the table view. */
export function truncateLabel(label: string, max = 24): string {
  return label.length <= max ? label : `${label.slice(0, max - 1).trimEnd()}…`;
}

/** "2026-09-19" -> "Sep 19". Falls back to the input for anything that is not a plain ISO date. */
export function shortDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return iso;
  return new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]))).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  });
}

export type AxisScale = { max: number; ticks: number[] };

/**
 * A round axis: steps of 1, 2 or 5 x 10^n, at most five intervals, starting at 0 - so ticks read 0 / 50 / 100 / 150 / 200
 * rather than 0 / 45 / 90 / 135 / 180 (or 0 / 15 / 30 / 50, which is what a chart library produces on its own). Never
 * returns a maximum below the value, and a chart with no data still gets a usable 0-1 axis.
 */
export function niceScale(value: number): AxisScale {
  if (!Number.isFinite(value) || value <= 1) return { max: 1, ticks: [0, 1] };
  const power = 10 ** Math.floor(Math.log10(value));
  // Finest step first (0.1, 0.2, 0.5, 1, 2, 5, 10 x the magnitude) that still fits in five intervals: 4-5 gridlines, not 2.
  const step = [0.1, 0.2, 0.5, 1, 2, 5, 10].map((m) => m * power).find((st) => Math.ceil(value / st) <= 5) as number;
  const intervals = Math.ceil(value / step);
  return { max: step * intervals, ticks: Array.from({ length: intervals + 1 }, (_, i) => i * step) };
}

/** Width in px for a value axis: wide enough for its longest tick label, so "1,000" is never clipped to ",000". */
export function axisWidth(max: number, minWidth = 36): number {
  return Math.max(minWidth, compactNumber(max).length * 8 + 14);
}

// ---------------------------------------------------------------- takeaways

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/** One factual sentence about the human-review backlog. */
export function lifecycleTakeaway(awaitingHuman: number, total: number): string {
  if (total === 0) return '';
  return awaitingHuman === 0
    ? 'Nothing is waiting for a human reviewer.'
    : `${plural(awaitingHuman, 'ticket')} ${awaitingHuman === 1 ? 'is' : 'are'} waiting for a human reviewer.`;
}

/** Share of *classified* tickets that carry negative or frustrated sentiment. Unclassified tickets are not counted either way. */
export function sentimentTakeaway(rows: CountRow[]): string {
  const count = (label: string) => rows.find((r) => r.label === label)?.count ?? 0;
  const classified = count('Frustrated') + count('Negative') + count('Neutral');
  if (classified === 0) return '';
  const negative = count('Frustrated') + count('Negative');
  return `${formatPercent(negative / classified)} of classified tickets are negative or frustrated.`;
}

/** Share of *classified* tickets that are high or critical priority. */
export function priorityTakeaway(rows: CountRow[]): string {
  const count = (label: string) => rows.find((r) => r.label === label)?.count ?? 0;
  const classified = count('Critical') + count('High') + count('Medium') + count('Low');
  if (classified === 0) return '';
  return `${formatPercent((count('Critical') + count('High')) / classified)} of classified tickets are high or critical priority.`;
}
