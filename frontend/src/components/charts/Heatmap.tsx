'use client';

import { useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { compactNumber, gridMax } from '../../lib/reportCharts';
import { EMPTY_CELL, INK, SEQUENTIAL } from './tokens';
import { TipLayer, TipRow, useTip } from './tip';

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const FULL_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const CELL = 22;
const GAP = 3;
const LEFT = 36;
const TOP = 6;
const BOTTOM = 22;

/** Maps a count to a step of the sequential ramp. Zero is an empty cell, deliberately not the darkest step. */
export function heatColor(count: number, max: number): string {
  if (count <= 0) return EMPTY_CELL;
  return SEQUENTIAL[Math.min(SEQUENTIAL.length - 1, Math.ceil((count / max) * SEQUENTIAL.length) - 1)];
}

/**
 * Weekday x hour heatmap (UTC). Each cell is its own hover/focus target; arrow keys move between cells (one tab stop for
 * the whole grid), and the same numbers are in the card's table view.
 */
export function Heatmap({ grid, unit = 'ticket' }: { grid: number[][]; unit?: string }) {
  const max = useMemo(() => gridMax(grid), [grid]);
  const total = useMemo(() => grid.flat().reduce((a, b) => a + b, 0), [grid]);
  const containerRef = useRef<HTMLDivElement>(null);
  const cellRefs = useRef<Map<string, SVGRectElement>>(new Map());
  const { tip, showAtElement, hide } = useTip();
  const [active, setActive] = useState<[number, number]>(() => {
    // Start the single tab stop on the busiest cell: that is where a reader's eye goes first.
    let best: [number, number] = [0, 0];
    grid.forEach((row, r) => row.forEach((v, c) => { if (v > grid[best[0]][best[1]]) best = [r, c]; }));
    return best;
  });

  const width = LEFT + 24 * (CELL + GAP);
  const height = TOP + 7 * (CELL + GAP) + BOTTOM;

  const describe = (r: number, c: number) => {
    const n = grid[r][c];
    return `${FULL_DAYS[r]} ${String(c).padStart(2, '0')}:00–${String(c).padStart(2, '0')}:59 UTC: ${n} ${unit}${n === 1 ? '' : 's'}`;
  };

  const focusCell = (r: number, c: number) => {
    setActive([r, c]);
    cellRefs.current.get(`${r}-${c}`)?.focus();
  };

  const onKeyDown = (e: KeyboardEvent, r: number, c: number) => {
    const moves: Record<string, [number, number]> = {
      ArrowRight: [r, Math.min(23, c + 1)],
      ArrowLeft: [r, Math.max(0, c - 1)],
      ArrowDown: [Math.min(6, r + 1), c],
      ArrowUp: [Math.max(0, r - 1), c],
      Home: [r, 0],
      End: [r, 23],
    };
    const to = moves[e.key];
    if (to) {
      e.preventDefault();
      focusCell(to[0], to[1]);
    }
  };

  const cellContent = (r: number, c: number) => (
    <>
      <TipRow label={`${FULL_DAYS[r]}, ${String(c).padStart(2, '0')}:00 UTC`} value={`${compactNumber(grid[r][c])} ${unit}${grid[r][c] === 1 ? '' : 's'}`} />
    </>
  );

  return (
    <div ref={containerRef} className="relative">
      {/* Below ~560px the grid would shrink to unreadable pixels: keep it legible and let it scroll sideways instead. */}
      <div className="overflow-x-auto">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full h-auto min-w-[560px]"
        role="grid"
        aria-label={`Ticket arrivals by weekday and hour, UTC. ${total} ${unit}s in total. Use the arrow keys to move between cells.`}
      >
        {DAYS.map((d, r) => (
          <text key={d} x={LEFT - 8} y={TOP + r * (CELL + GAP) + CELL / 2 + 4} textAnchor="end" fontSize={11} fill={INK.muted}>{d}</text>
        ))}
        {[0, 3, 6, 9, 12, 15, 18, 21].map((h) => (
          <text key={h} x={LEFT + h * (CELL + GAP) + CELL / 2} y={height - 6} textAnchor="middle" fontSize={11} fill={INK.muted}>
            {String(h).padStart(2, '0')}
          </text>
        ))}
        {grid.map((row, r) => (
          <g key={r} role="row">
            {row.map((count, c) => (
              <rect
                key={c}
                ref={(el) => { if (el) cellRefs.current.set(`${r}-${c}`, el); }}
                role="gridcell"
                aria-label={describe(r, c)}
                tabIndex={active[0] === r && active[1] === c ? 0 : -1}
                x={LEFT + c * (CELL + GAP)}
                y={TOP + r * (CELL + GAP)}
                width={CELL}
                height={CELL}
                rx={4}
                fill={heatColor(count, max)}
                className="outline-none transition-[filter] hover:brightness-125 focus-visible:brightness-150"
                onPointerEnter={(e) => showAtElement(containerRef.current, e.currentTarget, cellContent(r, c))}
                onPointerLeave={hide}
                onFocus={(e) => { setActive([r, c]); showAtElement(containerRef.current, e.currentTarget, cellContent(r, c)); }}
                onBlur={hide}
                onKeyDown={(e) => onKeyDown(e, r, c)}
              />
            ))}
          </g>
        ))}
      </svg>
      </div>

      <div className="mt-3 flex items-center justify-end gap-2 text-caption text-fg-muted" aria-hidden="true">
        <span>0</span>
        <span className="h-2 w-40 rounded-full" style={{ background: `linear-gradient(to right, ${SEQUENTIAL[0]}, ${SEQUENTIAL[SEQUENTIAL.length - 1]})` }} />
        <span>{compactNumber(max)}</span>
      </div>
      <TipLayer tip={tip} />
    </div>
  );
}
