import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '../../theme/ThemeProvider';
import { ThemeToggle } from './ThemeToggle';

vi.mock('next/navigation', () => ({ usePathname: () => '/design' }));

beforeEach(() => {
  localStorage.clear();
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: true,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia;
});

const setup = () =>
  render(
    <ThemeProvider migratedRoutes={['/design']}>
      <ThemeToggle />
    </ThemeProvider>
  );

describe('ThemeToggle', () => {
  it('is a labelled group of toggle buttons with System, Light and Dark, and System selected by default', () => {
    setup();
    expect(screen.getByRole('group', { name: 'Color theme' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'System' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Light' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: 'Dark' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('selects and persists the chosen theme', async () => {
    setup();
    await userEvent.click(screen.getByRole('button', { name: 'Light' }));
    expect(screen.getByRole('button', { name: 'Light' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'System' })).toHaveAttribute('aria-pressed', 'false');
    expect(localStorage.getItem('theme-preference')).toBe('light');
  });

  it('lets a passed className override its own display utility', () => {
    render(
      <ThemeProvider migratedRoutes={['/design']}>
        <ThemeToggle className="hidden sm:inline-flex" />
      </ThemeProvider>
    );
    const tokens = screen.getByRole('group', { name: 'Color theme' }).className.split(' ');
    expect(tokens).toContain('hidden');
    expect(tokens).toContain('sm:inline-flex');
    expect(tokens).not.toContain('inline-flex');
  });

  it('renders nothing when there is no ThemeProvider above it', () => {
    const { container } = render(<ThemeToggle />);
    expect(container).toBeEmptyDOMElement();
  });
});
