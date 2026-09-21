'use client';

import { cx } from '../../lib/cx';
import type { DeltaView } from '../../lib/reportCharts';
import { INK, SERIES, STATUS, SURFACE } from './tokens';

// Delta figures are TEXT (4.5:1), unlike marks (3:1): 'bad' uses the theme's danger text colour, since the chart
// `serious` orange is tuned as a mark colour and reads 3.05:1 on white.
const TONE_COLOR = { good: STATUS.good, bad: 'var(--c-danger)', neutral: INK.secondary } as const;

/** Twelve-ish points, drawn thin and quiet: the trend is context, the number is the point. Decorative (aria-hidden). */
export function Sparkline({ values, width = 96, height = 28 }: { values: number[]; width?: number; height?: number }) {
  if (values.length < 2) return null;
  const pad = 4;
  const max = Math.max(...values, 1);
  const x = (i: number) => pad + (i * (width - pad * 2)) / (values.length - 1);
  const y = (v: number) => height - pad - (v / max) * (height - pad * 2);
  const line = values.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const last = values.length - 1;
  return (
    <svg aria-hidden="true" width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="shrink-0">
      <path d={`${line} L${x(last)},${height - pad} L${x(0)},${height - pad} Z`} fill={INK.muted} opacity={0.1} />
      <path d={line} fill="none" stroke={INK.muted} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={x(last)} cy={y(values[last])} r={4} fill={SERIES.blue} stroke={SURFACE} strokeWidth={2} />
    </svg>
  );
}

/**
 * A stat tile: label, value, optional change against the previous period, optional sparkline. `hero` makes the value the
 * single largest figure on the view (use once). The delta always carries an arrow or words - colour is never alone.
 */
export function StatTile({
  label,
  value,
  hint,
  delta,
  deltaCaption,
  spark,
  hero = false,
}: {
  label: string;
  value: string;
  hint?: string;
  delta?: DeltaView | null;
  deltaCaption?: string;
  spark?: number[];
  hero?: boolean;
}) {
  return (
    <div className={cx('rounded-xl border border-border bg-surface flex flex-col justify-between gap-3 min-w-0', hero ? 'p-7' : 'p-5')}>
      <p className="text-caption font-medium text-fg-muted">{label}</p>
      <div className="flex items-end justify-between gap-3">
        <p
          className={cx('font-semibold leading-none tracking-tight text-fg', hero ? 'text-h1' : 'text-h2')}
          aria-label={`${label}: ${value}`}
        >
          {value}
        </p>
        {spark && <Sparkline values={spark} width={hero ? 168 : 96} height={hero ? 48 : 28} />}
      </div>
      <div className="text-caption space-y-1 text-fg-muted">
        {delta && (
          <p className="flex flex-wrap items-center gap-x-2">
            <span className="font-semibold" style={{ color: TONE_COLOR[delta.tone] }} data-tone={delta.tone}>{delta.text}</span>
            {deltaCaption && <span>{deltaCaption}</span>}
          </p>
        )}
        {/* The hint is context (a rate, a spread, a sample size) and stays visible next to the change, not instead of it. */}
        {hint && <p>{hint}</p>}
      </div>
    </div>
  );
}
