import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { renderWithTheme } from '../../test/renderWithTheme';
import { theme } from '../../theme/theme.config';
import { footer } from './content';
import { Footer } from './Footer';

vi.mock('next/navigation', () => ({ usePathname: () => '/' }));

describe('Footer', () => {
  it('is the contentinfo landmark with the brand name and current year', () => {
    renderWithTheme(<Footer />);
    const info = screen.getByRole('contentinfo');
    expect(info).toHaveTextContent(theme.brand.name);
    expect(info).toHaveTextContent(String(new Date().getFullYear()));
  });

  it('has a labelled footer navigation with the account links', () => {
    renderWithTheme(<Footer />);
    for (const link of footer.links) {
      expect(screen.getByRole('link', { name: link.label })).toHaveAttribute('href', link.href);
    }
    expect(screen.getByRole('navigation', { name: 'Footer' })).toBeInTheDocument();
  });

  it('carries the theme toggle so it is reachable on phones', () => {
    renderWithTheme(<Footer />);
    expect(screen.getByRole('group', { name: 'Color theme' })).toBeInTheDocument();
  });
});
