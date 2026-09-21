import { describe, expect, it } from 'vitest';
import { contrastRatio, mixOver } from './contrast';
import { theme } from './theme.config';
import { COLOR_TOKENS, type ColorSet } from './types';

const MODES = ['light', 'dark'] as const;

describe('theme completeness', () => {
  it('defines the brand name, tagline and page description', () => {
    expect(theme.brand.name).toBeTruthy();
    expect(theme.brand.tagline).toBeTruthy();
    expect(theme.brand.description).toBeTruthy();
  });

  it.each(MODES)('%s mode defines every color token', (mode) => {
    for (const token of COLOR_TOKENS) {
      expect(theme.colors[mode][token], `${mode}.${token}`).toBeTruthy();
    }
  });
});

// Every text color must be readable on every surface it can sit on (WCAG AA, 4.5:1). A company that
// changes a token and breaks a pair sees which pair failed and by how much.
const SURFACES = ['canvas', 'surface', 'surface-raised'] as const;
const TEXT = ['fg', 'fg-muted', 'fg-subtle', 'brand', 'accent', 'success', 'warning', 'danger', 'info'] as const;

function check(colors: ColorSet, fg: keyof ColorSet, bg: keyof ColorSet, min: number) {
  const ratio = contrastRatio(colors[fg], colors[bg]);
  expect(ratio, `${fg} ${colors[fg]} on ${bg} ${colors[bg]} is ${ratio.toFixed(2)}:1, needs ${min}:1`).toBeGreaterThanOrEqual(min);
}

describe.each(MODES)('%s mode contrast', (mode) => {
  const colors = theme.colors[mode];

  for (const fg of TEXT) {
    for (const bg of SURFACES) {
      it(`${fg} on ${bg} is at least 4.5:1`, () => check(colors, fg, bg, 4.5));
    }
  }

  it('brand-fg on brand is at least 4.5:1', () => check(colors, 'brand-fg', 'brand', 4.5));
  it('brand-fg on brand-hover is at least 4.5:1', () => check(colors, 'brand-fg', 'brand-hover', 4.5));
  it('brand-fg on danger is at least 4.5:1 (destructive button text)', () => check(colors, 'brand-fg', 'danger', 4.5));
  it('focus ring is at least 3:1 on canvas, surface and surface-raised', () => {
    check(colors, 'focus', 'canvas', 3);
    check(colors, 'focus', 'surface', 3);
    check(colors, 'focus', 'surface-raised', 3);
  });

  // WCAG 1.4.11 non-text contrast (3:1). border-strong is the only thing that outlines Inputs and
  // secondary Buttons, so it must be visible on every surface. The hairline `border` token is decorative
  // (card and divider edges) and deliberately exempt.
  for (const bg of SURFACES) {
    it(`border-strong on ${bg} is at least 3:1`, () => check(colors, 'border-strong', bg, 3));
  }

  // brand-soft is a translucent brand wash. Its effective color is brand at the token's alpha over the
  // surface. Icons and other non-text marks may sit on it (3:1); TEXT must never sit on brand-soft.
  for (const bg of SURFACES) {
    it(`brand over the brand-soft wash on ${bg} is at least 3:1 (icons only, never text)`, () => {
      const match = /^rgba\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*([0-9.]+)\s*\)$/.exec(colors['brand-soft']);
      expect(match, `brand-soft "${colors['brand-soft']}" must be rgba(r, g, b, a)`).not.toBeNull();
      const wash = mixOver(colors.brand, Number(match![1]), colors[bg]);
      const ratio = contrastRatio(colors.brand, wash);
      expect(ratio, `brand ${colors.brand} on soft wash ${wash} over ${bg} is ${ratio.toFixed(2)}:1, needs 3:1`).toBeGreaterThanOrEqual(3);
    });
  }
});

describe('chart palettes', () => {
  it.each(MODES)('%s palette has 5 ordinal and 10 sequential hex steps, ordinal distinct', (mode) => {
    const c = theme.charts[mode];
    expect(c.ordinal).toHaveLength(5);
    expect(c.sequential).toHaveLength(10);
    expect(new Set(c.ordinal).size).toBe(5);
    const all = [...Object.values(c.ink), ...Object.values(c.chrome), ...Object.values(c.series), ...c.ordinal, ...c.sequential, c.emptyCell, c.deemphasis, ...Object.values(c.status)];
    for (const v of all) expect(v).toMatch(/^#[0-9a-fA-F]{6}$/);
  });
});

describe('horizon palettes', () => {
  it.each(MODES)('%s mode has horizon palette', (mode) => {
    expect(theme.horizon[mode]).toBeTruthy();
  });

  it.each(MODES)('%s mode horizon values are valid CSS colors (except reflect)', (mode) => {
    const h = theme.horizon[mode];
    const hexOrRgba = /^(#[0-9a-fA-F]{6}|rgba\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*[0-9.]+\s*\))$/;
    const colors = Object.entries(h).filter(([name]) => name !== 'reflect');
    expect(colors.length).toBeGreaterThanOrEqual(13);
    for (const [name, value] of colors) {
      expect(`${name}=${value}`).toMatch(new RegExp(`^${name}=(#[0-9a-fA-F]{6}|rgba\\(.*\\))$`));
      expect(value).toMatch(hexOrRgba);
    }
  });

  it('the bloom ramp core -> glow1..glow4 is defined in both modes', () => {
    for (const mode of MODES) {
      const h = theme.horizon[mode];
      for (const key of ['core', 'glow1', 'glow2', 'glow3', 'glow4'] as const) {
        expect(h[key]).toBeTruthy();
      }
      // The ramp must actually be a ramp, not one colour repeated.
      expect(new Set([h.core, h.glow1, h.glow2, h.glow3, h.glow4]).size).toBe(5);
    }
  });

  it('every horizon colour differs between light and dark', () => {
    const dark = theme.horizon.dark;
    const light = theme.horizon.light;
    const keys = (Object.keys(dark) as (keyof typeof dark)[]).filter((k) => k !== 'reflect');
    expect(keys.length).toBeGreaterThanOrEqual(13);
    for (const key of keys) {
      expect(`${key}:${dark[key]}`).not.toBe(`${key}:${light[key]}`);
    }
  });

  it.each(MODES)('%s mode horizon reflect parses to a number in [0, 1]', (mode) => {
    const h = theme.horizon[mode];
    const reflect = Number(h.reflect);
    expect(reflect).toBeGreaterThanOrEqual(0);
    expect(reflect).toBeLessThanOrEqual(1);
  });

  it('dark ring is not equal to light ring', () => {
    expect(theme.horizon.dark.ring).not.toBe(theme.horizon.light.ring);
  });

  it('light reflect is "0"', () => {
    expect(theme.horizon.light.reflect).toBe('0');
  });
});
