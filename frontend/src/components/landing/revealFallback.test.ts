import { describe, expect, it } from 'vitest';
import { REVEAL_FALLBACK_CSS } from './revealFallback';

describe('REVEAL_FALLBACK_CSS', () => {
  it('selects the reveal marker attribute', () => {
    expect(REVEAL_FALLBACK_CSS).toContain('[data-reveal]');
  });

  it('forces both opacity and transform, each !important', () => {
    expect(REVEAL_FALLBACK_CSS).toContain('opacity:1!important');
    expect(REVEAL_FALLBACK_CSS).toContain('transform:none!important');
  });
});
