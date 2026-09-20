import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { theme } from '../../theme/theme.config';
import { Logo } from './Logo';

describe('Logo', () => {
  it('shows the brand name from the theme file', () => {
    render(<Logo />);
    expect(screen.getByText(theme.brand.name)).toBeVisible();
  });

  it('keeps the name available to screen readers when only the mark is shown', () => {
    render(<Logo showName={false} />);
    expect(screen.getByText(theme.brand.name)).toHaveClass('sr-only');
  });

  it('draws the mark from theme data and hides it from assistive tech', () => {
    const { container } = render(<Logo />);
    const svg = container.querySelector('svg');
    expect(svg).toHaveAttribute('aria-hidden', 'true');
    expect(svg?.querySelector('path')).toHaveAttribute('d', theme.brand.mark.path);
  });
});
