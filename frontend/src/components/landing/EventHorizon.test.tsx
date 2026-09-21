import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { EventHorizon, EventHorizonReflection } from './EventHorizon';

describe('EventHorizon', () => {
  it('is decorative: aria-hidden, no text, nothing focusable', () => {
    const { container } = render(<EventHorizon />);
    const root = container.firstElementChild as HTMLElement;
    expect(root).toHaveAttribute('aria-hidden', 'true');
    expect(root.textContent).toBe('');
    expect(root.querySelectorAll('a, button, input, select, textarea, [tabindex]')).toHaveLength(0);
  });

  it('renders every layer once and five streaks with --x and --d set inline', () => {
    const { container } = render(<EventHorizon />);
    for (const layer of ['halo', 'stars', 'outer', 'ring', 'sweep', 'ring-alt', 'void', 'line']) {
      expect(container.querySelectorAll(`.hz-${layer}`)).toHaveLength(1);
    }
    const streaks = container.querySelectorAll<HTMLElement>('.hz-streak');
    expect(streaks).toHaveLength(5);
    streaks.forEach((s) => {
      expect(s.style.getPropertyValue('--x')).not.toBe('');
      expect(s.style.getPropertyValue('--d')).not.toBe('');
    });
  });

  it('merges className onto the root', () => {
    const { container } = render(<EventHorizon className="extra" />);
    const root = container.firstElementChild as HTMLElement;
    expect(root).toHaveClass('hz');
    expect(root).toHaveClass('extra');
  });
});

describe('EventHorizonReflection', () => {
  it('renders an aria-hidden hz-reflect element', () => {
    const { container } = render(<EventHorizonReflection />);
    const el = container.firstElementChild as HTMLElement;
    expect(el).toHaveAttribute('aria-hidden', 'true');
    expect(el).toHaveClass('hz-reflect');
  });
});
