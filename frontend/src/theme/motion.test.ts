import { describe, expect, it } from 'vitest';
import { duration, ease, parseCubicBezier, toSeconds } from './motion';
import { theme } from './theme.config';

describe('parseCubicBezier', () => {
  it('turns a CSS cubic-bezier into the array framer-motion accepts', () => {
    expect(parseCubicBezier('cubic-bezier(0.16, 1, 0.3, 1)')).toEqual([0.16, 1, 0.3, 1]);
  });

  it('tolerates extra whitespace and negative values', () => {
    expect(parseCubicBezier('cubic-bezier( 0.2 ,-0.5,  0.8 , 1.4 )')).toEqual([0.2, -0.5, 0.8, 1.4]);
  });

  it('rejects anything that is not a cubic-bezier', () => {
    expect(() => parseCubicBezier('ease-out')).toThrow(/cubic-bezier/);
  });
});

describe('toSeconds', () => {
  it('converts milliseconds and passes seconds through', () => {
    expect(toSeconds('600ms')).toBeCloseTo(0.6, 5);
    expect(toSeconds('0.25s')).toBeCloseTo(0.25, 5);
  });

  it('rejects other units', () => {
    expect(() => toSeconds('2rem')).toThrow(/duration/);
  });
});

describe('theme-derived motion values', () => {
  it('exposes the theme easing curves as arrays', () => {
    expect(ease.out).toEqual(parseCubicBezier(theme.motion.easeOut));
    expect(ease.inOut).toEqual(parseCubicBezier(theme.motion.easeInOut));
  });

  it('exposes the theme durations in seconds', () => {
    expect(duration.fast).toBeCloseTo(toSeconds(theme.motion.durationFast), 5);
    expect(duration.slow).toBeGreaterThan(duration.base);
    expect(duration.base).toBeGreaterThan(duration.fast);
  });
});
