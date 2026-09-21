import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { demo, hero } from './content';
import { Hero } from './Hero';

describe('Hero', () => {
  it('has the one page-level heading', () => {
    render(<Hero />);
    const headings = screen.getAllByRole('heading', { level: 1 });
    expect(headings).toHaveLength(1);
    expect(headings[0]).toHaveTextContent(hero.headline);
  });

  it('shows the lead and both calls to action as links', () => {
    render(<Hero />);
    expect(screen.getByText(hero.lead)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: hero.primary.label })).toHaveAttribute('href', hero.primary.href);
    expect(screen.getByRole('link', { name: hero.secondary.label })).toHaveAttribute('href', hero.secondary.href);
  });

  it('includes the example ticket panel', () => {
    render(<Hero />);
    expect(screen.getByRole('group', { name: demo.ariaLabel })).toBeInTheDocument();
  });

  it('staggers its entrance with consecutive rise indexes', () => {
    const { container } = render(<Hero />);
    const indexes = Array.from(container.querySelectorAll<HTMLElement>('.rise-in')).map((el) => el.style.getPropertyValue('--rise-index'));
    expect(indexes).toEqual(['0', '1', '2', '3']);
  });

  it('renders the decorative horizon as aria-hidden inside the demo wrapper, before the demo card', () => {
    const { container } = render(<Hero />);
    const horizon = container.querySelector('.hz');
    expect(horizon).not.toBeNull();
    expect(horizon).toHaveAttribute('aria-hidden', 'true');

    // Check that the horizon's parent also contains the demo card
    const parent = horizon?.parentElement;
    const demoCard = parent?.querySelector('[role="group"]');
    expect(demoCard).not.toBeNull();

    // Check document order: horizon should precede the demo card
    const horizonPosition = horizon?.compareDocumentPosition(demoCard as Node) ?? 0;
    expect(horizonPosition & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('keeps the horizon out of the accessibility tree and out of the tab order', () => {
    const { container } = render(<Hero />);
    const horizon = container.querySelector('.hz');
    expect(horizon).not.toBeNull();
    expect(horizon).toHaveAttribute('aria-hidden', 'true');
    expect(horizon!.textContent).toBe('');
    expect(
      horizon!.querySelectorAll('a, button, input, select, textarea, iframe, [tabindex]:not([tabindex="-1"])'),
    ).toHaveLength(0);

    // Verify heading and CTAs are still accessible
    const headings = screen.getAllByRole('heading', { level: 1 });
    expect(headings).toHaveLength(1);

    expect(screen.getByRole('link', { name: hero.primary.label })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: hero.secondary.label })).toBeInTheDocument();
  });

  it('has a reflection layer over the card', () => {
    const { container } = render(<Hero />);
    const reflection = container.querySelector('.hz-reflect');
    expect(reflection).not.toBeNull();
    expect(reflection).toHaveAttribute('aria-hidden', 'true');
  });
});
