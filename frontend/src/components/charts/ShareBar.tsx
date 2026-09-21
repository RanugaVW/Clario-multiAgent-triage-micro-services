'use client';

import { useRef } from 'react';
import { compactNumber, formatPercent, withShares } from '../../lib/reportCharts';
import { EMPTY_CELL, SURFACE } from './tokens';
import { TipLayer, TipRow, useTip } from './tip';

export type ShareSegment = { label: string; count: number; color: string };

/**
 * Part-to-whole as ONE 100% stacked bar (three states is the honest case for it; a pie of three near-equal slices is
 * harder to read). Segments are separated by a 2px gap in the surface colour - not by a border - with rounded outer ends.
 * Values live in the legend beneath, so no label is ever squeezed into or clipped by a narrow segment.
 */
export function ShareBar({ segments, ariaLabel }: { segments: ShareSegment[]; ariaLabel: string }) {
  const shares = withShares(segments);
  const ref = useRef<HTMLDivElement>(null);
  const { tip, show, showAtElement, hide } = useTip();
  const visible = segments.map((s, i) => ({ ...s, share: shares[i].share })).filter((s) => s.count > 0);

  const content = (s: (typeof visible)[number]) => (
    <>
      <TipRow swatch={s.color} label={s.label} value={`${compactNumber(s.count)} · ${formatPercent(s.share, 1)}`} />
    </>
  );

  return (
    <div ref={ref} className="relative">
      <div role="group" aria-label={ariaLabel} className="flex h-6 w-full overflow-hidden rounded-md" style={{ gap: 2, background: SURFACE }}>
        {visible.map((s) => (
          <div
            key={s.label}
            role="img"
            tabIndex={0}
            aria-label={`${s.label}: ${s.count} (${formatPercent(s.share, 1)})`}
            className="h-full outline-none focus-visible:brightness-125 transition-[filter] hover:brightness-125"
            style={{ flexGrow: s.count, flexBasis: 0, minWidth: 4, background: s.color }}
            onPointerMove={(e) => show(ref.current, e.clientX, e.currentTarget.getBoundingClientRect().top, content(s))}
            onPointerLeave={hide}
            onFocus={(e) => showAtElement(ref.current, e.currentTarget, content(s))}
            onBlur={hide}
          />
        ))}
        {visible.length === 0 && <div className="h-full w-full" style={{ background: EMPTY_CELL }} />}
      </div>

      <ul className="mt-4 grid gap-y-2.5">
        {segments.map((s, i) => (
          <li key={s.label} className="flex items-center gap-2 min-w-0">
            <span aria-hidden="true" className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: s.color }} />
            <span className="text-caption truncate text-fg-muted">{s.label}</span>
            <span className="ml-auto text-app font-semibold tabular-nums text-fg">{compactNumber(s.count)}</span>
            <span className="w-10 text-right text-caption tabular-nums text-fg-muted">{formatPercent(shares[i].share)}</span>
          </li>
        ))}
      </ul>
      <TipLayer tip={tip} />
    </div>
  );
}
