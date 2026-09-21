// Thin adapter over `theme.charts` (src/theme/theme.config.ts). Every colour is a CSS variable that css.ts emits per mode
// (--ch-*), so charts follow the light/dark switch without any component knowing a hex. The palettes themselves are
// validated per mode by tokens.test.ts (contrast, ordering, ordinal step gaps, colour-vision separation).

export const SURFACE = 'var(--c-surface)'; // the chart sits on the card surface

export const INK = {
  primary: 'var(--ch-ink-primary)',
  secondary: 'var(--ch-ink-secondary)',
  muted: 'var(--ch-ink-muted)',
} as const;

export const CHROME = {
  grid: 'var(--ch-grid)', // hairline, one step off the surface
  axis: 'var(--ch-axis)',
  ring: SURFACE, // the 2px surface gap/ring that separates touching marks (never a border)
} as const;

/** Categorical slots in their FIXED order - assigned to entities, never cycled, never re-ranked. */
export const SERIES = {
  blue: 'var(--ch-blue)', // slot 1
  orange: 'var(--ch-orange)', // slot 2
  aqua: 'var(--ch-aqua)', // slot 3
  yellow: 'var(--ch-yellow)', // slot 4
} as const;

/** Ticket lifecycle states. Each state owns a slot, so filtering never repaints the survivors. */
export const LIFECYCLE = {
  resolved: SERIES.blue,
  awaitingHuman: SERIES.orange,
  inProgress: SERIES.aqua,
} as const;

/**
 * Ordinal ramp, one hue. Index 0 is the least severe. Dark mode brightens with severity, light mode darkens; the
 * direction lives in the palette, not here.
 */
export const ORDINAL_STEPS = [
  'var(--ch-ordinal-1)', 'var(--ch-ordinal-2)', 'var(--ch-ordinal-3)', 'var(--ch-ordinal-4)', 'var(--ch-ordinal-5)',
] as const;

/** Severity scales: index 0 is the least severe. */
export const PRIORITY_COLOR: Record<string, string> = {
  Low: ORDINAL_STEPS[0],
  Medium: ORDINAL_STEPS[1],
  High: ORDINAL_STEPS[2],
  Critical: ORDINAL_STEPS[3],
};
export const SENTIMENT_COLOR: Record<string, string> = {
  Neutral: ORDINAL_STEPS[0],
  Negative: ORDINAL_STEPS[2],
  Frustrated: ORDINAL_STEPS[3],
};
/** Judge score 1..5: higher = better, so the ramp steps up with the score. */
export const SCORE_COLOR: Record<string, string> = {
  '1': ORDINAL_STEPS[0],
  '2': ORDINAL_STEPS[1],
  '3': ORDINAL_STEPS[2],
  '4': ORDINAL_STEPS[3],
  '5': ORDINAL_STEPS[4],
};

/** De-emphasis for "Unclassified" / "Other": present, honest, and visibly not one of the categories. */
export const DEEMPHASIS = 'var(--ch-deemphasis)';

/** Sequential ramp for magnitude (heatmap): more = more prominent against the surface. Zero is an empty cell, not the lowest step. */
export const SEQUENTIAL = [
  'var(--ch-seq-1)', 'var(--ch-seq-2)', 'var(--ch-seq-3)', 'var(--ch-seq-4)', 'var(--ch-seq-5)',
  'var(--ch-seq-6)', 'var(--ch-seq-7)', 'var(--ch-seq-8)', 'var(--ch-seq-9)', 'var(--ch-seq-10)',
] as const;
export const EMPTY_CELL = 'var(--ch-empty)';

/** Status - reserved for good/bad meaning, always paired with an arrow or words. */
export const STATUS = {
  good: 'var(--ch-good)',
  warning: 'var(--ch-warning)',
  serious: 'var(--ch-serious)',
  critical: 'var(--ch-critical)',
} as const;

export const FONT = 'var(--f-sans)';
