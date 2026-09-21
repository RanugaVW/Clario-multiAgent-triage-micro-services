import { describe, it, expect } from 'vitest';
import {
  SURFACE, SERIES, ORDINAL_STEPS, SEQUENTIAL, PRIORITY_COLOR, SENTIMENT_COLOR, SCORE_COLOR, LIFECYCLE, INK, STATUS, EMPTY_CELL,
} from './tokens';

// WCAG relative luminance and contrast ratio.
const lin = (c: number) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const luminance = (hex: string) => {
  const n = parseInt(hex.slice(1), 16);
  return 0.2126 * lin(((n >> 16) & 255) / 255) + 0.7152 * lin(((n >> 8) & 255) / 255) + 0.0722 * lin((n & 255) / 255);
};
const contrast = (a: string, b: string) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

// OKLab lightness (Ottosson) - the space the dataviz validator measures step gaps in.
const oklabL = (hex: string) => {
  const n = parseInt(hex.slice(1), 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => lin(v / 255));
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return 0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s;
};

describe('chart palette contract (validated with the dataviz validator; re-checked here so it cannot drift)', () => {
  it('every categorical mark clears 3:1 on the chart surface', () => {
    for (const [name, hex] of Object.entries(SERIES)) expect(contrast(hex, SURFACE), name).toBeGreaterThanOrEqual(3);
  });
  it('body text tokens clear WCAG AA (4.5:1) on the surface', () => {
    for (const [name, hex] of Object.entries({ primary: INK.primary, secondary: INK.secondary, muted: INK.muted })) {
      expect(contrast(hex, SURFACE), name).toBeGreaterThanOrEqual(4.5);
    }
  });
  it('the ordinal ramp brightens monotonically and its least-severe step still clears 2:1', () => {
    const ls = ORDINAL_STEPS.map(luminance);
    expect([...ls].sort((a, b) => a - b)).toEqual(ls);
    expect(new Set(ORDINAL_STEPS).size).toBe(ORDINAL_STEPS.length);
    expect(contrast(ORDINAL_STEPS[0], SURFACE)).toBeGreaterThanOrEqual(2);
  });
  it('neighbouring steps of every ordinal scale in use stay >= 0.06 OKLab L apart (the validator rule that once failed)', () => {
    for (const scale of [[...ORDINAL_STEPS], ...[PRIORITY_COLOR, SENTIMENT_COLOR, SCORE_COLOR].map((s) => Object.values(s))]) {
      const ls = scale.map(oklabL).sort((a, b) => a - b);
      for (let i = 1; i < ls.length; i++) expect(ls[i] - ls[i - 1], scale.join()).toBeGreaterThanOrEqual(0.06);
    }
  });
  it('the guard would have caught the old ramp: its top two steps were too close', () => {
    expect(oklabL('#86b6ef') - oklabL('#6da7ec')).toBeLessThan(0.06);
  });
  it('every severity scale is ordered by lightness (more severe = brighter)', () => {
    const inSeverityOrder = (scale: Record<string, string>, keys: string[]) => {
      const l = keys.map((k) => luminance(scale[k]));
      expect([...l].sort((a, b) => a - b)).toEqual(l);
    };
    inSeverityOrder(PRIORITY_COLOR, ['Low', 'Medium', 'High', 'Critical']);
    inSeverityOrder(SENTIMENT_COLOR, ['Neutral', 'Negative', 'Frustrated']);
    inSeverityOrder(SCORE_COLOR, ['1', '2', '3', '4', '5']);
  });
  it('the sequential ramp is monotone, and an empty cell is distinguishable from the lowest step', () => {
    const l = SEQUENTIAL.map(luminance);
    expect([...l].sort((a, b) => a - b)).toEqual(l);
    expect(EMPTY_CELL).not.toBe(SEQUENTIAL[0]);
  });
  it('each lifecycle state owns a distinct categorical slot', () => {
    expect(new Set(Object.values(LIFECYCLE)).size).toBe(3);
    for (const hex of Object.values(LIFECYCLE)) expect(Object.values(SERIES)).toContain(hex);
  });
  it('status colours are distinct from every categorical slot', () => {
    for (const s of Object.values(STATUS)) expect(Object.values(SERIES)).not.toContain(s);
  });
});
