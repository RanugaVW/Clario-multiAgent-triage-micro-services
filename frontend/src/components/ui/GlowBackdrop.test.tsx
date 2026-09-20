import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { GlowBackdrop } from './GlowBackdrop';

describe('GlowBackdrop', () => {
  it('is decorative: hidden from assistive tech and ignores pointer events', () => {
    const { container } = render(<GlowBackdrop />);
    const root = container.firstElementChild as HTMLElement;
    expect(root).toHaveAttribute('aria-hidden', 'true');
    expect(root.className).toContain('pointer-events-none');
    expect(root.className).toContain('absolute');
  });

  it('draws one glow blob', () => {
    const { container } = render(<GlowBackdrop />);
    expect(container.querySelectorAll('.glow-blob')).toHaveLength(1);
  });

  it('keeps classes passed by the caller', () => {
    const { container } = render(<GlowBackdrop className="opacity-70" />);
    expect((container.firstElementChild as HTMLElement).className).toContain('opacity-70');
  });
});
