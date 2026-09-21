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

  it('renders the composition plus its two overlay layers, none of them in the tab order', () => {
    const { container } = render(<EventHorizon />);
    const svgs = container.querySelectorAll('svg.hz-svg');
    expect(svgs).toHaveLength(3);
    for (const svg of svgs) {
      expect(svg).toHaveAttribute('focusable', 'false');
      expect(svg).toHaveAttribute('viewBox', '0 0 1200 420');
    }
    // The animated layers are separate SVGs so the blurred one can stay rasterised.
    expect(container.querySelectorAll('.hz-overlay')).toHaveLength(2);
    expect(container.querySelector('.hz-breathe .hz-shimmer')).toBeNull();
    expect(container.querySelector('.hz-breathe .hz-stars')).toBeNull();
  });

  it('renders each composited layer once', () => {
    const { container } = render(<EventHorizon />);
    for (const layer of ['halo', 'bloom', 'dome', 'rings', 'disc', 'flares', 'line', 'arcs', 'stars', 'shimmer']) {
      expect(container.querySelectorAll(`.hz-${layer}`)).toHaveLength(1);
    }
  });

  it('stacks several blurred copies of the dome so the bloom has depth', () => {
    const { container } = render(<EventHorizon />);
    const bloom = container.querySelectorAll('.hz-bloom path');
    const band = container.querySelectorAll('.hz-dome path');
    expect(bloom.length).toBeGreaterThanOrEqual(3);
    expect(band.length).toBeGreaterThanOrEqual(5);
    for (const el of [...bloom, ...band]) expect(el.getAttribute('filter')).toMatch(/^url\(#hzB\d+\)$/);
  });

  it('takes every colour from a --hz-* variable, never a literal', () => {
    const { container } = render(<EventHorizon />);
    const root = container.firstElementChild as HTMLElement;
    expect(root.innerHTML).not.toMatch(/#[0-9a-fA-F]{3,8}\b(?!\))/);
    for (const el of root.querySelectorAll<SVGElement>('[style]')) {
      expect(el.getAttribute('style')).toMatch(/var\(--hz-|mask-type/);
    }
    const stops = container.querySelectorAll<SVGStopElement>('stop');
    expect(stops.length).toBeGreaterThan(20);
    for (const stop of stops) expect(stop.style.stopColor).toMatch(/^var\(--hz-[a-z0-9-]+\)$/);
  });

  it('draws the dark disc as a circle, so it can never render as a box', () => {
    const { container } = render(<EventHorizon />);
    const disc = container.querySelector('.hz-disc') as SVGCircleElement;
    expect(disc.tagName.toLowerCase()).toBe('circle');
    expect(Number(disc.getAttribute('r'))).toBeGreaterThan(0);
  });

  it('merges className onto the root', () => {
    const { container } = render(<EventHorizon className="extra" />);
    const root = container.firstElementChild as HTMLElement;
    expect(root).toHaveClass('hz');
    expect(root).toHaveClass('extra');
  });
});

describe('EventHorizonReflection', () => {
  it('renders an aria-hidden hz-reflect element with its two layers', () => {
    const { container } = render(<EventHorizonReflection />);
    const el = container.firstElementChild as HTMLElement;
    expect(el).toHaveAttribute('aria-hidden', 'true');
    expect(el).toHaveClass('hz-reflect');
    expect(el.textContent).toBe('');
    expect(el.querySelector('.hz-reflect-core')).not.toBeNull();
    expect(el.querySelector('.hz-reflect-ring')).not.toBeNull();
  });

  it('merges className onto the root', () => {
    const { container } = render(<EventHorizonReflection className="extra" />);
    expect(container.firstElementChild).toHaveClass('extra');
  });
});
