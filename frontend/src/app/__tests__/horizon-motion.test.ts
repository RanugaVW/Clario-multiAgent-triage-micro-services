import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, it, expect } from 'vitest';

const css = readFileSync(join(__dirname, '..', 'globals.css'), 'utf8');

// Text of the block starting at the 'Landing event horizon' comment (the last block of the file: the hz rules).
const MARKER = 'Landing event horizon';
const markerAt = css.indexOf(MARKER);
const region = markerAt === -1 ? '' : css.slice(css.lastIndexOf('/*', markerAt));

/** The only selectors in the hz block allowed to carry an `animation` declaration. */
const ANIMATABLE = ['.hz-breathe', '.hz-shimmer', '.hz-stars', '.hz-reflect'];

/**
 * Every selector whose rule declares an `animation`/`animation-name`, at any indentation and inside
 * @media blocks too: for each declaration, walk back to the `{` that opens its rule and read the
 * selector list in front of it.
 */
function animatedSelectors(text: string): string[] {
  const found: string[] = [];
  const re = /animation(?:-name)?\s*:/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    const open = text.lastIndexOf('{', m.index);
    if (open === -1) continue;
    const head = text.slice(0, open);
    const comment = head.lastIndexOf('*/');
    const start = Math.max(head.lastIndexOf('{'), head.lastIndexOf('}'), comment === -1 ? -1 : comment + 1);
    for (const sel of head.slice(start + 1).split(',')) {
      const trimmed = sel.trim();
      if (trimmed) found.push(trimmed);
    }
  }
  return found;
}

/** Returns the body of every `@keyframes hz-*` block (prefixed or not), matching braces. */
function hzKeyframeBodies(text: string): string[] {
  const bodies: string[] = [];
  const re = /@(?:-webkit-)?keyframes\s+hz-[\w-]+\s*\{/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    let depth = 1;
    let i = m.index + m[0].length;
    const start = i;
    while (i < text.length && depth > 0) {
      if (text[i] === '{') depth++;
      else if (text[i] === '}') depth--;
      i++;
    }
    bodies.push(text.slice(start, i - 1));
  }
  return bodies;
}

/** Property names declared in a keyframe body (the `name:` before each value, ignoring selectors like `0%, 100%`). */
function declaredProps(body: string): string[] {
  const props: string[] = [];
  const declRe = /(?:^|[{;])\s*([a-zA-Z-]+)\s*:/g;
  let m: RegExpExecArray | null;
  while ((m = declRe.exec(body))) props.push(m[1]);
  return props;
}

describe('landing event horizon CSS', () => {
  it('has the marked block, with every layer the component styles', () => {
    expect(markerAt).toBeGreaterThan(-1);
    for (const selector of ['.hz {', '.hz-svg {', '.hz-overlay {', '.hz-breathe {', '.hz-shimmer {', '.hz-stars {', '.hz-reflect {']) {
      expect(region).toContain(selector);
    }
  });

  it('only .hz-breathe, .hz-shimmer, .hz-stars and .hz-reflect carry an animation', () => {
    // Everything else in the composition sits inside the filtered SVG, where an animation makes the
    // browser re-run every feGaussianBlur per frame. Only the wrapper and the two filter-free
    // overlays (plus the reflection) may animate, at any nesting level, including inside @media.
    expect(animatedSelectors(region).length).toBeGreaterThan(0);
    expect(animatedSelectors(region).filter((sel) => !ANIMATABLE.includes(sel))).toEqual([]);
  });

  it('the animation parser sees indented rules inside a media query (guard self-check)', () => {
    const sample = '@media (max-width: 640px) {\n  .hz-bloom {\n    animation: hz-breathe 9s linear infinite;\n  }\n}\n';
    expect(animatedSelectors(sample)).toEqual(['.hz-bloom']);
    expect(animatedSelectors(sample).filter((sel) => !ANIMATABLE.includes(sel))).toEqual(['.hz-bloom']);
  });

  it('drops the whole decoration under forced colors', () => {
    // Forced colors overrides every SVG fill and stroke, which would repaint the effect as one solid
    // CanvasText mass behind the CTAs.
    const block = /@media \(forced-colors: active\) \{[^}]*\.hz,\s*\n?\s*\.hz-reflect \{\s*display: none;/;
    expect(region).toMatch(block);
  });

  it('defines at least 4 hz keyframes and animates only transform and opacity', () => {
    const bodies = hzKeyframeBodies(css);
    expect(bodies.length).toBeGreaterThanOrEqual(4);
    const props = new Set(bodies.flatMap(declaredProps));
    expect(props.size).toBeGreaterThan(0);
    expect([...props].filter((p) => p !== 'transform' && p !== 'opacity')).toEqual([]);
  });

  it('the property parser catches a disallowed property (guard self-check)', () => {
    const bad = hzKeyframeBodies('@keyframes hz-x { 0%, 100% { opacity: 1; } 50% { filter: blur(2px); } }');
    expect(bad.flatMap(declaredProps)).toContain('filter');
  });

  it('uses no colour literals; every colour goes through a var()', () => {
    // Same set the .tsx guard rejects: hex, the functional syntaxes (including the modern ones),
    // color-mix() and the two named colours that are easy to type by accident.
    const literal =
      /#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?|hwb|oklch|oklab|lab|lch|color|color-mix)\(|\b(?:white|black)\b/;
    // Comments are prose, not values: 'near-white' in a note is not a colour literal.
    expect(region.replace(/\/\*[\s\S]*?\*\//g, '')).not.toMatch(literal);
    for (const bad of [
      'background: #fff',
      'color: rgba(0,0,0,.5)',
      'color: hsl(0 0% 0%)',
      'color: oklch(70% 0.1 250)',
      'color: oklab(70% 0.1 0.1)',
      'color: lab(70% 20 30)',
      'color: lch(70% 30 250)',
      'color: color(display-p3 1 0 0)',
      'background: color-mix(in srgb, var(--a), var(--b))',
      'border-color: white',
      'outline-color: black',
    ]) {
      expect(bad).toMatch(literal); // guard self-check
    }
  });
});
