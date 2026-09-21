'use client';

import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { axisWidth, compactNumber, niceScale, shortDate } from '../../lib/reportCharts';
import type { VolumeSeries } from '../../lib/reports';
import { ChartTooltip } from './ChartTooltip';
import { CHROME, FONT, INK, SERIES, SURFACE } from './tokens';

const HEIGHT = 260;

/**
 * Ticket volume over time. A single quiet line with a ~10% wash beneath it, plus the trailing 7-day average when the span
 * is plotted daily. The crosshair snaps to the nearest date and one tooltip lists both series - the reader aims at a
 * date, never at a 2px line.
 */
export function TrendChart({ series }: { series: VolumeSeries }) {
  const scale = niceScale(Math.max(0, ...series.points.map((p) => p.count)));
  const hasAverage = series.points.some((p) => p.average !== null);
  const unit = series.granularity === 'week' ? 'per week' : 'per day';
  return (
    <div role="img" aria-label={`Ticket volume ${unit}. The same numbers are in the table view.`}>
      <ResponsiveContainer width="100%" height={HEIGHT} initialDimension={{ width: 640, height: HEIGHT }}>
        <ComposedChart data={series.points} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke={CHROME.grid} strokeWidth={1} />
          <XAxis
            dataKey="date"
            tickLine={false}
            axisLine={{ stroke: CHROME.axis }}
            tick={{ fill: INK.muted, fontSize: 12, fontFamily: FONT }}
            tickFormatter={shortDate}
            minTickGap={36}
            tickMargin={8}
          />
          <YAxis
            allowDecimals={false}
            tickLine={false}
            axisLine={false}
            width={axisWidth(scale.max, 40)}
            tick={{ fill: INK.muted, fontSize: 12, fontFamily: FONT }}
            tickFormatter={(v: number) => compactNumber(v)}
            domain={[0, scale.max]}
            ticks={scale.ticks}
          />
          <Tooltip
            cursor={{ stroke: CHROME.axis, strokeWidth: 1 }}
            content={
              <ChartTooltip
                title={(label, payload) => {
                  if (series.granularity !== 'week') return shortDate(String(label));
                  const days = (payload[0] as { payload?: { days?: number } } | undefined)?.payload?.days ?? 7;
                  // A short final week is not a collapse in demand - say how many days it covers.
                  return days < 7 ? `Week of ${label} (partial: ${days} of 7 days)` : `Week of ${label}`;
                }}
                format={(v) => (Number.isInteger(v) ? v.toLocaleString('en-US') : v.toFixed(1))}
              />
            }
          />
          <Area
            type="linear"
            dataKey="count"
            name="Received"
            stroke={SERIES.blue}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            fill={SERIES.blue}
            fillOpacity={0.1}
            dot={false}
            activeDot={{ r: 4, fill: SERIES.blue, stroke: SURFACE, strokeWidth: 2 }}
            isAnimationActive={false}
          />
          {hasAverage && (
            <Line
              type="linear"
              dataKey="average"
              name="7-day average"
              stroke={SERIES.orange}
              strokeWidth={2}
              strokeLinecap="round"
              dot={false}
              activeDot={{ r: 4, fill: SERIES.orange, stroke: SURFACE, strokeWidth: 2 }}
              connectNulls={false}
              isAnimationActive={false}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export const TREND_LEGEND = [
  { label: 'Received', color: SERIES.blue },
  { label: '7-day average', color: SERIES.orange },
];
