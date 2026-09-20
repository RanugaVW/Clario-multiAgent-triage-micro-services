import { theme } from './theme.config';

export type Bezier = [number, number, number, number];

/**
 * The theme stores easing as CSS (`cubic-bezier(...)`) so stylesheets can use it directly. framer-motion wants the
 * four numbers as an array, so this converts once instead of duplicating the curve in JavaScript.
 */
export function parseCubicBezier(css: string): Bezier {
  const match = /^cubic-bezier\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)$/.exec(css.trim());
  if (!match) throw new Error(`Expected cubic-bezier(x1, y1, x2, y2), got "${css}"`);
  return [Number(match[1]), Number(match[2]), Number(match[3]), Number(match[4])];
}

/** framer-motion measures time in seconds; the theme stores CSS durations such as "600ms". */
export function toSeconds(css: string): number {
  const match = /^([\d.]+)(ms|s)$/.exec(css.trim());
  if (!match) throw new Error(`Expected a duration like "250ms" or "0.25s", got "${css}"`);
  return match[2] === 'ms' ? Number(match[1]) / 1000 : Number(match[1]);
}

export const ease = {
  out: parseCubicBezier(theme.motion.easeOut),
  inOut: parseCubicBezier(theme.motion.easeInOut),
} as const;

export const duration = {
  fast: toSeconds(theme.motion.durationFast),
  base: toSeconds(theme.motion.durationBase),
  slow: toSeconds(theme.motion.durationSlow),
} as const;
