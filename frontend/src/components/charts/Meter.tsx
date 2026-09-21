'use client';

import { clampUnit, formatPercent, type MeterSeverity } from '../../lib/reportCharts';
import { INK, SERIES, STATUS } from './tokens';

const FILL: Record<MeterSeverity, string> = { normal: SERIES.blue, warning: STATUS.warning, danger: STATUS.critical };
const WORDS: Record<MeterSeverity, string> = { normal: '', warning: 'Needs attention', danger: 'Critical' };

/**
 * A single rate against its limits. The fill carries severity (accent -> warning -> danger); the unfilled track is the
 * same colour, faint, so the whole bar reads as one state. Severity is also written out in words - never colour alone.
 */
export function Meter({
  label,
  value,
  severity = 'normal',
  detail,
}: {
  label: string;
  value: number | null;
  severity?: MeterSeverity;
  detail?: string;
}) {
  const fill = FILL[severity];
  const text = formatPercent(value);
  return (
    <div className="min-w-0">
      <div className="flex items-baseline justify-between gap-3 mb-2">
        <span className="text-sm" style={{ color: INK.secondary }}>{label}</span>
        <span className="text-sm font-semibold" style={{ color: INK.primary }}>
          {text}
          {WORDS[severity] && <span className="ml-2 text-xs font-medium" style={{ color: severity === 'danger' ? STATUS.serious : STATUS.warning }}>{WORDS[severity]}</span>}
        </span>
      </div>
      <div
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value === null ? undefined : Math.round(value * 100)}
        aria-valuetext={value === null ? 'No data' : `${text}${WORDS[severity] ? `, ${WORDS[severity].toLowerCase()}` : ''}`}
        className="h-2 rounded-full overflow-hidden"
        style={{ background: `${fill}2e` }}
      >
        <div className="h-full rounded-full" style={{ width: `${value === null ? 0 : clampUnit(value) * 100}%`, background: fill }} />
      </div>
      {detail && <p className="text-xs mt-1.5" style={{ color: INK.muted }}>{detail}</p>}
    </div>
  );
}
