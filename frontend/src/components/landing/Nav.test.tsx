import { screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { renderWithTheme } from '../../test/renderWithTheme';
import { theme } from '../../theme/theme.config';
import { nav } from './content';
import { Nav } from './Nav';

vi.mock('next/navigation', () => ({ usePathname: () => '/' }));

describe('Nav', () => {
  it('is the page banner with the brand linking home', () => {
    renderWithTheme(<Nav />);
    expect(screen.getByRole('banner')).toBeInTheDocument();
    const home = screen.getByRole('link', { name: `${theme.brand.name} home` });
    expect(home).toHaveAttribute('href', '/');
  });

  it('lists every in-page section link in a labelled primary navigation', () => {
    renderWithTheme(<Nav />);
    const primary = screen.getByRole('navigation', { name: 'Primary' });
    for (const link of nav.links) {
      expect(within(primary).getByRole('link', { name: link.label })).toHaveAttribute('href', link.href);
    }
  });

  it('offers sign in and get started', () => {
    renderWithTheme(<Nav />);
    expect(screen.getByRole('link', { name: nav.signIn.label })).toHaveAttribute('href', '/login');
    expect(screen.getByRole('link', { name: nav.getStarted.label })).toHaveAttribute('href', '/register');
  });

  it('includes the theme toggle', () => {
    renderWithTheme(<Nav />);
    expect(screen.getByRole('group', { name: 'Color theme' })).toBeInTheDocument();
  });
});
