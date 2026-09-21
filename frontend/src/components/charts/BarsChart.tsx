'use client';

import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { axisWidth, compactNumber, niceScale, truncateLabel } from '../../lib/reportCharts';
import { ChartTooltip } from './ChartTooltip';
import { CHROME, FONT, INK, SERIES } from './tokens';

export type BarDatum = { label: string; count: number; color?: string };

const ROW = 30; // px per bar band; the bar itself is capped at 16px so the leftover is air
const BAR = 16;

/** The category name on the axis, shortened, with the full text kept in a <title> so it is never lost. */
function CategoryTick({ x, y, payload }: { x?: number; y?: number; payload?: { value: string } }) {
  const full = payload?.value ?? '';
  return (
    <text x={(x ?? 0) - 8} y={y} dy={4} textAnchor="end" fontSize={12} fontFamily={FONT} fill={INK.secondary}>
      <title>{full}</title>
      {truncateLabel(full, 24)}
    </text>
  );
}

/**
 * Bars for comparing magnitude. `orientation="rows"` (default) draws horizontal bars with the name on the left and the
 * value at the tip - the right form for many or long category names. `"columns"` draws vertical columns for short, ordered
 * bins (a histogram, a score scale). Nominal categories share ONE colour; only ordinal scales pass per-bar colours.
 */
export function BarsChart({
  data,
  orientation = 'rows',
  color = SERIES.blue,
  ariaLabel,
  unit = 'tickets',
  columnHeight = 220,
}: {
  data: BarDatum[];
  orientation?: 'rows' | 'columns';
  color?: string;
  ariaLabel: string;
  unit?: string;
  columnHeight?: number;
}) {
  const rows = orientation === 'rows';
  const scale = niceScale(Math.max(0, ...data.map((d) => d.count)));
  const height = rows ? Math.max(90, data.length * ROW + 16) : columnHeight;
  const tickStyle = { fill: INK.muted, fontSize: 12, fontFamily: FONT };
  const tooltip = (
    <ChartTooltip
      title={(label) => String(label)}
      rows={(payload) => [{ name: unit, value: compactNumber(Number(payload[0]?.value ?? 0)) }]}
    />
  );

  return (
    <div role="img" aria-label={ariaLabel}>
      <ResponsiveContainer width="100%" height={height} initialDimension={{ width: 640, height }}>
        <BarChart
          data={data}
          layout={rows ? 'vertical' : 'horizontal'}
          margin={rows ? { top: 4, right: 48, bottom: 4, left: 0 } : { top: 20, right: 8, bottom: 0, left: 0 }}
          barCategoryGap={rows ? 10 : '28%'}
        >
          {!rows && <CartesianGrid vertical={false} stroke={CHROME.grid} strokeWidth={1} />}
          {rows ? (
            <>
              <XAxis type="number" hide domain={[0, 'dataMax']} />
              <YAxis type="category" dataKey="label" tickLine={false} axisLine={{ stroke: CHROME.axis }} width={178} tick={<CategoryTick />} interval={0} />
            </>
          ) : (
            <>
              <XAxis dataKey="label" tickLine={false} axisLine={{ stroke: CHROME.axis }} tick={tickStyle} tickMargin={8} interval={0} />
              <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={axisWidth(scale.max, 40)} tick={tickStyle} tickFormatter={(v: number) => compactNumber(v)} domain={[0, scale.max]} ticks={scale.ticks} />
            </>
          )}
          <Tooltip cursor={{ fill: 'rgba(255,255,255,0.04)' }} content={tooltip} />
          <Bar
            dataKey="count"
            name={unit}
            maxBarSize={rows ? BAR : 24}
            // Rounded at the data end only, square where it meets the baseline.
            radius={rows ? [0, 4, 4, 0] : [4, 4, 0, 0]}
            isAnimationActive={false}
            minPointSize={2}
          >
            {data.map((d) => (
              <Cell key={d.label} fill={d.color ?? color} />
            ))}
            <LabelList
              dataKey="count"
              position={rows ? 'right' : 'top'}
              offset={8}
              fill={INK.secondary}
              fontSize={12}
              fontFamily={FONT}
              formatter={(v: unknown) => (typeof v === 'number' && v > 0 ? compactNumber(v) : '')}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
