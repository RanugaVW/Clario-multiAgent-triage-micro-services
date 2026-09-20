// WCAG 2.x relative luminance and contrast ratio. Used by theme.config.test.ts so that a company
// re-skinning the product finds out immediately if a palette is unreadable.

function channel(value: number): number {
  const s = value / 255;
  return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
}

export function luminance(hex: string): number {
  const match = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!match) throw new Error(`Expected a #rrggbb color, got "${hex}"`);
  const n = parseInt(match[1], 16);
  return 0.2126 * channel((n >> 16) & 255) + 0.7152 * channel((n >> 8) & 255) + 0.0722 * channel(n & 255);
}

export function contrastRatio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

function parse(hex: string): [number, number, number] {
  const match = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!match) throw new Error(`Expected a #rrggbb color, got "${hex}"`);
  const n = parseInt(match[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** The #rrggbb (lower-case) of `fg` composited at `alpha` (0..1) over the opaque color `bg`. Channels round to nearest. */
export function mixOver(fg: string, alpha: number, bg: string): string {
  const f = parse(fg);
  const b = parse(bg);
  if (!(alpha >= 0 && alpha <= 1)) throw new Error(`Expected alpha between 0 and 1, got ${alpha}`);
  const out = f.map((c, i) => Math.round(c * alpha + b[i] * (1 - alpha)));
  return '#' + out.map((c) => c.toString(16).padStart(2, '0')).join('');
}
