import { describe, it, expect } from 'vitest';
import * as tokens from './tokens';
import { theme } from '../../theme/theme.config';

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

const MODES = ['dark', 'light'] as const;
const sorted = (a: number[], dir: 1 | -1) => [...a].sort((x, y) => dir * (x - y));

describe.each(MODES)('chart palette contract, %s mode (re-checked so it cannot drift)', (mode) => {
  const p = theme.charts[mode];
  const surface = theme.colors[mode].surface;
  // dark: severity/magnitude brightens; light: it darkens.
  const dir = mode === 'dark' ? 1 : -1;
  const ordinalScales = (): string[][] => {
    const o = p.ordinal;
    return [[...o], [o[0], o[1], o[2], o[3]], [o[0], o[2], o[3]], [...o]];
  };

  it('every categorical mark clears 3:1 on the chart surface', () => {
    for (const [name, hex] of Object.entries(p.series)) expect(contrast(hex, surface), name).toBeGreaterThanOrEqual(3);
  });
  // Light mode only: the dark series are validated verbatim on colour-vision distance (equal lightness by design).
  it.runIf(mode === 'light')('the four series are distinguishable by lightness as well as hue', () => {
    const ls = Object.values(p.series).map(oklabL).sort((a, b) => a - b);
    for (let i = 1; i < ls.length; i++) expect(ls[i] - ls[i - 1]).toBeGreaterThanOrEqual(0.05);
  });
  it('body text tokens clear WCAG AA (4.5:1) on the surface', () => {
    for (const [name, hex] of Object.entries(p.ink)) expect(contrast(hex, surface), name).toBeGreaterThanOrEqual(4.5);
  });
  it('grid and axis hairlines are distinguishable from the surface (not required to clear 3:1)', () => {
    for (const [name, hex] of Object.entries(p.chrome)) {
      expect(hex.toLowerCase(), name).not.toBe(surface.toLowerCase());
      expect(contrast(hex, surface), name).toBeGreaterThan(1.05);
    }
  });
  it('the ordinal ramp is monotone in the mode direction, distinct, and its least-severe step clears the floor', () => {
    const ls = p.ordinal.map(luminance);
    expect(ls).toEqual(sorted(ls, dir));
    expect(new Set(p.ordinal).size).toBe(5);
    expect(contrast(p.ordinal[0], surface)).toBeGreaterThanOrEqual(mode === 'dark' ? 2 : 1.5);
  });
  it('neighbouring steps of every ordinal scale in use stay >= 0.06 OKLab L apart', () => {
    for (const scale of ordinalScales()) {
      const ls = scale.map(oklabL);
      for (let i = 1; i < ls.length; i++) expect(Math.abs(ls[i] - ls[i - 1]), scale.join()).toBeGreaterThanOrEqual(0.06);
    }
  });
  it('the exported severity scales use those steps, in severity order', () => {
    const idx = (v: string) => tokens.ORDINAL_STEPS.indexOf(v as never);
    expect(Object.values(tokens.PRIORITY_COLOR).map(idx)).toEqual([0, 1, 2, 3]);
    expect(Object.values(tokens.SENTIMENT_COLOR).map(idx)).toEqual([0, 2, 3]);
    expect(Object.values(tokens.SCORE_COLOR).map(idx)).toEqual([0, 1, 2, 3, 4]);
  });
  it('the sequential ramp is monotone in the mode direction, and an empty cell differs from the lowest step', () => {
    const l = p.sequential.map(luminance);
    expect(l).toEqual(sorted(l, dir));
    expect(p.emptyCell.toLowerCase()).not.toBe(p.sequential[0].toLowerCase());
  });
  it('status colours clear 3:1, are distinct from every series colour, and de-emphasis clears 3:1', () => {
    for (const [name, hex] of Object.entries(p.status)) {
      expect(contrast(hex, surface), name).toBeGreaterThanOrEqual(3);
      expect(Object.values(p.series), name).not.toContain(hex);
    }
    expect(contrast(p.deemphasis, surface)).toBeGreaterThanOrEqual(3);
  });
});

describe('chart palette guards', () => {
  it('the guard would have caught the old ramp: its top two steps were too close', () => {
    expect(oklabL('#86b6ef') - oklabL('#6da7ec')).toBeLessThan(0.06);
  });
  it('each lifecycle state owns a distinct categorical slot', () => {
    expect(new Set(Object.values(tokens.LIFECYCLE)).size).toBe(3);
    for (const v of Object.values(tokens.LIFECYCLE)) expect(Object.values(tokens.SERIES)).toContain(v);
  });
  it('tokens.ts exports only CSS variable references', () => {
    const flat = (v: unknown): string[] => (typeof v === 'string' ? [v] : Object.values(v as object).flatMap(flat));
    for (const [name, v] of Object.entries(tokens)) for (const s of flat(v)) expect(s, name).toMatch(/^var\(--(ch|c|f)-/);
  });
});
