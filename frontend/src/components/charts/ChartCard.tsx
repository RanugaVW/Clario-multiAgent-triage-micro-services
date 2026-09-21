'use client';

import { useId, useState, type ReactNode } from 'react';
import { INK } from './tokens';

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
    <section aria-labelledby={headingId} className={`glass-panel rounded-[28px] p-6 flex flex-col ${className}`}>
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="min-w-0">
          <h3 id={headingId} className="text-sm font-semibold" style={{ color: INK.primary }}>{title}</h3>
          {subtitle && <p className="text-xs mt-0.5" style={{ color: INK.muted }}>{subtitle}</p>}
        </div>
        {table && !empty && (
          <div role="group" aria-label={`${title} view`} className="flex shrink-0 rounded-full bg-white/[0.05] p-0.5 text-xs">
            {(['chart', 'table'] as const).map((v) => (
              <button
                key={v}
                type="button"
                aria-pressed={view === v}
                onClick={() => setView(v)}
                className={`px-3 py-1 rounded-full capitalize transition-colors outline-none focus-visible:ring-2 focus-visible:ring-[#E8A33D]/60 ${
                  view === v ? 'bg-white/[0.12] text-[#ECECEC]' : 'text-[#8A8F98] hover:text-[#ECECEC]'
                }`}
              >
                {v}
              </button>
            ))}
          </div>
        )}
      </div>

      {legend && !empty && view === 'chart' && <div className="mb-3">{legend}</div>}

      {empty ? (
        <p className="flex-1 flex items-center justify-center py-10 text-sm" style={{ color: INK.muted }}>{emptyText}</p>
      ) : view === 'table' && table ? (
        <DataTable data={table} caption={`${title}${subtitle ? ` - ${subtitle}` : ''}`} />
      ) : (
        <div className="flex-1 min-w-0">{children}</div>
      )}

      {footer && !empty && view === 'chart' && (
        <p className="mt-4 pt-3 border-t border-white/10 text-xs" style={{ color: INK.secondary }}>{footer}</p>
      )}
    </section>
  );
}

export function DataTable({ data, caption }: { data: TableData; caption: string }) {
  return (
    <div role="region" aria-label={`${caption} (scrollable table)`} tabIndex={0} className="overflow-x-auto max-h-80 overflow-y-auto outline-none focus-visible:ring-2 focus-visible:ring-[#E8A33D]/60 rounded-lg">
      <table className="w-full text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr style={{ color: INK.muted }} className="text-left">
            {data.columns.map((c, i) => (
              <th key={c} scope="col" className={`pb-2 font-medium ${i > 0 ? 'text-right' : ''}`}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5">
          {data.rows.map((row, r) => (
            <tr key={r}>
              {row.map((cell, i) => (
                <td key={i} className={`py-1.5 ${i > 0 ? 'text-right tabular-nums' : ''}`} style={{ color: INK.primary }}>
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
    <span className="inline-flex items-center gap-2 text-xs" style={{ color: INK.secondary }}>
      <span
        aria-hidden="true"
        className={shape === 'line' ? 'inline-block h-0.5 w-4 rounded-full' : 'inline-block h-2.5 w-2.5 rounded-[3px]'}
        style={{ background: color }}
      />
      {label}
    </span>
  );
}
