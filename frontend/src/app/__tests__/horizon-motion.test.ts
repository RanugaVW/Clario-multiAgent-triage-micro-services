import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, it, expect } from 'vitest';

const css = readFileSync(join(__dirname, '..', 'globals.css'), 'utf8');

// Text of the block starting at the 'Landing event horizon' comment (the last block of the file: the hz rules).
const MARKER = 'Landing event horizon';
const markerAt = css.indexOf(MARKER);
const region = markerAt === -1 ? '' : css.slice(css.lastIndexOf('/*', markerAt));

/** Returns the body of every `@keyframes hz-*` block, matching braces. */
function hzKeyframeBodies(text: string): string[] {
  const bodies: string[] = [];
  const re = /@keyframes\s+hz-[\w-]+\s*\{/g;
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
  it('has the marked block', () => {
    expect(markerAt).toBeGreaterThan(-1);
    expect(region).toContain('.hz-ring');
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
    const literal = /#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(/;
    expect(region).not.toMatch(literal);
    expect('background: #fff').toMatch(literal); // guard self-check
    expect('color: rgba(0,0,0,.5)').toMatch(literal);
  });
});
