'use client';

import { useId, useState, type ReactNode } from 'react';
import { cx } from '../../lib/cx';

export type TableData = { columns: string[]; rows: (string | number | null)[][] };

/**
 * The container every chart lives in: title and caption, an optional legend, and a Chart / Table toggle. The table view is
 * the accessible twin of the chart - every value in the plot is reachable there without a pointer or colour vision.
 */
export function ChartCard({
  title,
  subtitle,
  legend,
  table,
  empty = false,
  emptyText = 'No data in this period.',
  footer,
  className = '',
  children,
}: {
  title: string;
  subtitle?: string;
  legend?: ReactNode;
  table?: TableData;
  empty?: boolean;
  emptyText?: string;
  /** One factual sentence under the chart (a takeaway, never decoration). Hidden when empty. */
  footer?: string;
  className?: string;
  children: ReactNode;
}) {
  const [view, setView] = useState<'chart' | 'table'>('chart');
  const headingId = useId();

  return (
    <section aria-labelledby={headingId} className={cx('rounded-xl border border-border bg-surface p-5 flex flex-col', className)}>
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="min-w-0">
          <h3 id={headingId} className="text-app font-semibold text-fg">{title}</h3>
          {subtitle && <p className="text-caption mt-0.5 text-fg-muted">{subtitle}</p>}
        </div>
        {table && !empty && (
          <div role="group" aria-label={`${title} view`} className="flex shrink-0 rounded-full bg-surface-raised p-0.5 text-caption">
            {(['chart', 'table'] as const).map((v) => (
              <button
                key={v}
                type="button"
                aria-pressed={view === v}
                onClick={() => setView(v)}
                className={cx(
                  'px-3 py-1 rounded-full capitalize transition-colors outline-none focus-visible:ring-2 focus-visible:ring-brand',
                  view === v ? 'bg-brand-soft text-fg' : 'text-fg-muted hover:text-fg'
                )}
              >
                {v}
              </button>
            ))}
          </div>
        )}
      </div>

      {legend && !empty && view === 'chart' && <div className="mb-3">{legend}</div>}

      {empty ? (
        <p className="flex-1 flex items-center justify-center py-10 text-app text-fg-muted">{emptyText}</p>
      ) : view === 'table' && table ? (
        <DataTable data={table} caption={`${title}${subtitle ? ` - ${subtitle}` : ''}`} />
      ) : (
        <div className="flex-1 min-w-0">{children}</div>
      )}

      {footer && !empty && view === 'chart' && (
        <p className="mt-4 pt-3 border-t border-border text-caption text-fg-muted">{footer}</p>
      )}
    </section>
  );
}

export function DataTable({ data, caption }: { data: TableData; caption: string }) {
  return (
    <div role="region" aria-label={`${caption} (scrollable table)`} tabIndex={0} className="overflow-x-auto max-h-80 overflow-y-auto outline-none focus-visible:ring-2 focus-visible:ring-brand rounded-lg">
      <table className="w-full text-app">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="text-left text-fg-muted">
            {data.columns.map((c, i) => (
              <th key={c} scope="col" className={cx('pb-2 font-medium', i > 0 && 'text-right')}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {data.rows.map((row, r) => (
            <tr key={r}>
              {row.map((cell, i) => (
                <td key={i} className={cx('py-1.5 text-fg', i > 0 && 'text-right tabular-nums')}>
                  {cell === null ? '—' : typeof cell === 'number' ? cell.toLocaleString('en-US') : cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** A legend entry: a short key of the mark's colour beside ink-coloured text (text never wears the data colour). */
export function LegendKey({ color, label, shape = 'line' }: { color: string; label: string; shape?: 'line' | 'box' }) {
  return (
    <span className="inline-flex items-center gap-2 text-caption text-fg-muted">
      <span
        aria-hidden="true"
        className={shape === 'line' ? 'inline-block h-0.5 w-4 rounded-full' : 'inline-block h-2.5 w-2.5 rounded-sm'}
        style={{ background: color }}
      />
      {label}
    </span>
  );
}
