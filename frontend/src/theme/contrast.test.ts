import { describe, expect, it } from 'vitest';
import { contrastRatio, mixOver } from './contrast';

describe('contrastRatio', () => {
  it('is 21 for black on white and symmetric', () => {
    expect(contrastRatio('#000000', '#FFFFFF')).toBeCloseTo(21, 5);
    expect(contrastRatio('#FFFFFF', '#000000')).toBeCloseTo(21, 5);
  });

  it('is 1 for identical colors', () => {
    expect(contrastRatio('#7C7CFF', '#7C7CFF')).toBeCloseTo(1, 5);
  });

  it('matches a known WCAG reference value (#777777 on white is about 4.48)', () => {
    expect(contrastRatio('#777777', '#FFFFFF')).toBeCloseTo(4.48, 1);
  });

  it('rejects anything that is not #rrggbb', () => {
    expect(() => contrastRatio('rgba(0,0,0,0.5)', '#FFFFFF')).toThrow(/#rrggbb/);
  });
});

describe('mixOver', () => {
  it('composites fg at alpha over bg, rounding each channel to the nearest integer', () => {
    // 0.5 * 255 = 127.5 rounds up to 128 (0x80).
    expect(mixOver('#000000', 0.5, '#FFFFFF')).toBe('#808080');
    expect(mixOver('#FF0000', 0.25, '#000000')).toBe('#400000');
  });

  it('returns bg at alpha 0 and fg at alpha 1, lower-case #rrggbb', () => {
    expect(mixOver('#123456', 0, '#ABCDEF')).toBe('#abcdef');
    expect(mixOver('#123456', 1, '#ABCDEF')).toBe('#123456');
  });

  it('rejects anything that is not #rrggbb, and alpha outside 0..1', () => {
    expect(() => mixOver('rgba(0,0,0,0.5)', 0.5, '#FFFFFF')).toThrow(/#rrggbb/);
    expect(() => mixOver('#000000', 0.5, 'white')).toThrow(/#rrggbb/);
    expect(() => mixOver('#000000', 1.5, '#FFFFFF')).toThrow(/alpha/);
  });
});
