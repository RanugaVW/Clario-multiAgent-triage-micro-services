// Design tokens for the reporting charts. The app is dark-only, so these are the dark-mode values of the data-viz
// palette, validated against the real chart surface (the glass panel over the #08090D page, ~#111216):
//   categorical (first 4, adjacent): PASS - worst CVD dE 8.4, normal-vision dE 19.8, all >= 3:1 on the surface
//   ordinal ramp: PASS as the full 5 steps AND as the 4-step (priority) and 3-step (sentiment) subsets actually used -
//   monotone lightness, step gaps >= 0.06 dL, least-severe step 2.31:1 on the surface. (An earlier 5-step ramp FAILED: its top
//   two steps were only 0.047 dL apart - re-stepped.)
// `charts.tokens.test.ts` re-checks the contrast and ordering rules so the palette cannot drift unnoticed.

export const SURFACE = '#111216';

export const INK = {
  primary: '#ECECEC',
  secondary: '#C3C2B7',
  muted: '#898781',
} as const;

export const CHROME = {
  grid: '#2c2c2a', // hairline, one step off the surface
  axis: '#383835',
  ring: SURFACE, // the 2px surface gap/ring that separates touching marks (never a border)
} as const;

/** Categorical slots in their FIXED order - assigned to entities, never cycled, never re-ranked. */
export const SERIES = {
  blue: '#3987e5', // slot 1
  orange: '#d95926', // slot 2
  aqua: '#199e70', // slot 3
  yellow: '#c98500', // slot 4
} as const;

/** Ticket lifecycle states. Each state owns a slot, so filtering never repaints the survivors. */
export const LIFECYCLE = {
  resolved: SERIES.blue,
  awaitingHuman: SERIES.orange,
  inProgress: SERIES.aqua,
} as const;

/**
 * Ordinal ramp, one hue. On a dark surface the least-severe step sits nearest the surface (darkest) and severity climbs
 * toward the brightest step - the anchor flips in dark mode.
 */
export const ORDINAL_STEPS = ['#184f95', '#256abf', '#3987e5', '#86b6ef', '#b7d3f6'] as const;

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
/** Judge score 1..5: higher = better, so lightness climbs with the score. */
export const SCORE_COLOR: Record<string, string> = {
  '1': ORDINAL_STEPS[0],
  '2': ORDINAL_STEPS[1],
  '3': ORDINAL_STEPS[2],
  '4': ORDINAL_STEPS[3],
  '5': ORDINAL_STEPS[4],
};

/** De-emphasis for "Unclassified" / "Other": present, honest, and visibly not one of the categories. */
export const DEEMPHASIS = '#5b5f68';

/** Sequential ramp for magnitude (heatmap): more = brighter on dark. Zero is drawn as an empty cell, not the darkest step. */
export const SEQUENTIAL = ['#0d366b', '#104281', '#184f95', '#1c5cab', '#256abf', '#2a78d6', '#3987e5', '#5598e7', '#6da7ec', '#86b6ef'] as const;
export const EMPTY_CELL = '#1a1b21';

/** Status - reserved for good/bad meaning, always paired with an arrow or words. */
export const STATUS = {
  good: '#0ca30c',
  warning: '#fab219',
  serious: '#ec835a',
  critical: '#d03b3b',
} as const;

export const FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif';
