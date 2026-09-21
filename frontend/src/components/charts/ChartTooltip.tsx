'use client';

import type { ReactNode } from 'react';

type Row = { name?: string | number; value?: string | number | readonly (string | number)[]; color?: string; dataKey?: string | number };

/**
 * The readout Recharts renders on hover/focus. One tooltip lists every series at that position, values lead and names
 * follow, and rows are keyed by a short stroke of the series colour (not a box). Text stays in ink tokens.
 * Labels come from data, so they are only ever rendered as React text (escaped) - never as HTML.
 */
export function ChartTooltip({
  active,
  payload,
  label,
  title,
  format = (v: number) => v.toLocaleString('en-US'),
  rows,
}: {
  active?: boolean;
  payload?: Row[];
  label?: string | number;
  /** Overrides the heading (defaults to the axis label). */
  title?: (label: string | number | undefined, payload: Row[]) => ReactNode;
  format?: (v: number) => string;
  /** Overrides which rows are listed (defaults to every series in the payload). */
  rows?: (payload: Row[]) => { color?: string; name: string; value: string }[];
}) {
  if (!active || !payload || payload.length === 0) return null;
  const list = rows
    ? rows(payload)
    : payload
        .filter((p) => typeof p.value === 'number')
        .map((p) => ({ color: p.color, name: String(p.name ?? p.dataKey ?? ''), value: format(p.value as number) }));
  return (
    <div className="bg-surface-raised border border-border text-fg shadow-raised rounded-lg px-3 py-2 text-caption">
      <div className="mb-1 text-fg-muted">{title ? title(label, payload) : label}</div>
      {list.map((r) => (
        <div key={r.name} className="flex items-center gap-2">
          {r.color && <span aria-hidden="true" className="inline-block h-0.5 w-3 rounded-full" style={{ background: r.color }} />}
          <span className="font-semibold text-fg">{r.value}</span>
          <span>{r.name}</span>
        </div>
      ))}
    </div>
  );
}
