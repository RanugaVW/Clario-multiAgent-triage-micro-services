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
});
