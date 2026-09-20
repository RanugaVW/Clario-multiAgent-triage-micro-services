import { describe, expect, it } from 'vitest';
import { themeToCss } from './css';
import { theme } from './theme.config';
import { COLOR_TOKENS } from './types';

const [shared, dark, light] = themeToCss(theme).split('\n');

describe('themeToCss', () => {
  it('emits exactly three rules: shared, dark and light', () => {
    expect(themeToCss(theme).split('\n')).toHaveLength(3);
  });

  it('puts type, radius, space, layout, motion and font variables in the shared rule', () => {
    expect(shared.startsWith(':root{')).toBe(true);
    expect(shared).toContain('--t-h1-size:clamp(');
    expect(shared).toContain('--t-h1-lh:1.1');
    expect(shared).toContain('--t-h1-weight:600');
    expect(shared).toContain('--t-h1-tracking:-0.025em');
    expect(shared).toContain('--r-pill:9999px');
    expect(shared).toContain('--sp-card:1.5rem');
    expect(shared).toContain('--l-container-marketing:75rem');
    expect(shared).toContain('--m-duration-fast:150ms');
    expect(shared).toContain('--f-sans:var(--font-face-sans),');
    expect(shared).toContain('--f-mono:var(--font-face-mono),');
  });

  it('makes dark the default and scopes it to data-theme="dark"', () => {
    expect(dark.startsWith(':root,:root[data-theme="dark"]{')).toBe(true);
    expect(dark).toContain('--c-canvas:#0A0B14');
    expect(dark).toContain('color-scheme:dark');
  });

  it('scopes light to data-theme="light"', () => {
    expect(light.startsWith(':root[data-theme="light"]{')).toBe(true);
    expect(light).toContain('--c-canvas:#F7F8FC');
    expect(light).toContain('color-scheme:light');
  });

  it('emits every color token and both shadows in both modes', () => {
    for (const rule of [dark, light]) {
      for (const token of COLOR_TOKENS) expect(rule).toContain(`--c-${token}:`);
      expect(rule).toContain('--sh-card:');
      expect(rule).toContain('--sh-raised:');
    }
  });
});
