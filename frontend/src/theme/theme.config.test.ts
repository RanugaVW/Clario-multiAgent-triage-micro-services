import { describe, expect, it } from 'vitest';
import { contrastRatio } from './contrast';
import { theme } from './theme.config';
import { COLOR_TOKENS, type ColorSet } from './types';

const MODES = ['light', 'dark'] as const;

describe('theme completeness', () => {
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
  it('focus ring is at least 3:1 on canvas and surface', () => {
    check(colors, 'focus', 'canvas', 3);
    check(colors, 'focus', 'surface', 3);
  });
});
