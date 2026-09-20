import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Reveal } from './Reveal';

describe('Reveal', () => {
  it('renders its children and keeps the caller\'s classes', () => {
    render(
      <Reveal className="md:col-span-2" data-testid="wrap">
        <p>Inside</p>
      </Reveal>
    );
    expect(screen.getByText('Inside')).toBeInTheDocument();
    expect(screen.getByTestId('wrap').className).toContain('md:col-span-2');
  });

  it('starts hidden until scrolled into view, so the reveal has something to animate from', () => {
    render(
      <Reveal data-testid="wrap">
        <p>Inside</p>
      </Reveal>
    );
    expect(screen.getByTestId('wrap')).toHaveStyle({ opacity: '0' });
  });

  it('carries a stable data-reveal hook so a <noscript> stylesheet can force reveals visible without JavaScript', () => {
    render(
      <Reveal data-testid="wrap">
        <p>Inside</p>
      </Reveal>
    );
    expect(screen.getByTestId('wrap')).toHaveAttribute('data-reveal');
  });
});
