import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { nav } from '../components/landing/content';
import { renderWithTheme } from '../test/renderWithTheme';
import { theme } from '../theme/theme.config';
import Home, { metadata } from './page';

vi.mock('next/navigation', () => ({ usePathname: () => '/' }));

describe('landing page', () => {
  it('has exactly one h1 and the standard landmarks', () => {
    renderWithTheme(<Home />);
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(screen.getByRole('banner')).toBeInTheDocument();
    expect(screen.getByRole('main')).toBeInTheDocument();
    expect(screen.getByRole('contentinfo')).toBeInTheDocument();
  });

  it('lets keyboard users skip the header', () => {
    renderWithTheme(<Home />);
    const skip = screen.getByRole('link', { name: 'Skip to content' });
    expect(skip).toHaveAttribute('href', '#main');
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main');
  });

  it('keeps the skip link padding on the focus variant, which otherwise resets it', () => {
    renderWithTheme(<Home />);
    const tokens = screen.getByRole('link', { name: 'Skip to content' }).className.split(' ');
    expect(tokens).toContain('focus:px-4');
    expect(tokens).toContain('focus:py-2');
    expect(tokens).not.toContain('px-4');
    expect(tokens).not.toContain('py-2');
  });

  it('lists nav links in the same order as the sections on the page', () => {
    renderWithTheme(<Home />);
    const ids = nav.links.map((l) => l.href.slice(1));
    const els = ids.map((id) => document.getElementById(id) as HTMLElement);
    for (let i = 1; i < els.length; i++) {
      expect(
        els[i - 1].compareDocumentPosition(els[i]) & Node.DOCUMENT_POSITION_FOLLOWING,
        `${ids[i - 1]} should come before ${ids[i]}`,
      ).toBeTruthy();
    }
  });

  it('every in-page nav link lands on a section that is really on the page', () => {
    renderWithTheme(<Home />);
    for (const link of nav.links) {
      expect(document.getElementById(link.href.slice(1)), link.href).not.toBeNull();
    }
  });

  it('renders every section in order', () => {
    renderWithTheme(<Home />);
    const h2s = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent);
    expect(h2s).toEqual([
      'Three specialists, one queue',
      'What happens to a ticket',
      'People stay in charge of the hard cases',
      'Personal details stay out of the drafting step',
      'Send your first ticket',
    ]);
  });

  it('takes its title and description from the theme file', () => {
    expect(String(metadata.title)).toContain(theme.brand.name);
    expect(metadata.description).toBe(theme.brand.description);
  });
});
