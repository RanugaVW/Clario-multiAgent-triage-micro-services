import { readFileSync } from 'fs';
import path from 'path';
import { describe, expect, it } from 'vitest';

const layout = readFileSync(path.join(__dirname, 'layout.tsx'), 'utf8');

// Guards the no-JavaScript fallback: without it the scroll reveals would leave content invisible.
describe('root layout injects the no-JS reveal fallback', () => {
  it('imports the fallback CSS and renders it in a <noscript>', () => {
    expect(layout).toContain("from '../components/landing/revealFallback'");
    expect(layout).toContain('REVEAL_FALLBACK_CSS');
    expect(layout).toContain('<noscript>');
  });

  it('puts the <noscript> inside <head>', () => {
    const noscript = layout.indexOf('<noscript>');
    expect(layout.indexOf('<head>')).toBeGreaterThan(-1);
    expect(noscript).toBeGreaterThan(layout.indexOf('<head>'));
    expect(noscript).toBeLessThan(layout.indexOf('</head>'));
  });
});
