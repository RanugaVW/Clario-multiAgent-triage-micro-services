import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider, useTheme } from './ThemeProvider';

const nav = vi.hoisted(() => ({ pathname: '/design' }));
vi.mock('next/navigation', () => ({ usePathname: () => nav.pathname }));

function stubMatchMedia(dark: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: dark,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

function Probe() {
  const { preference, mode, setPreference } = useTheme();
  return (
    <div>
      <span data-testid="mode">{mode}</span>
      <span data-testid="pref">{preference}</span>
      <button onClick={() => setPreference('light')}>set light</button>
    </div>
  );
}

const attr = () => document.documentElement.getAttribute('data-theme');
const renderProvider = () =>
  render(
    <ThemeProvider migratedRoutes={['/design']}>
      <Probe />
    </ThemeProvider>
  );

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute('data-theme');
  nav.pathname = '/design';
  stubMatchMedia(true);
});

describe('ThemeProvider', () => {
  it('applies the stored preference on a migrated route', () => {
    localStorage.setItem('theme-preference', 'light');
    renderProvider();
    expect(attr()).toBe('light');
    expect(screen.getByTestId('mode')).toHaveTextContent('light');
  });

  it('follows the system setting when nothing is stored', () => {
    stubMatchMedia(false);
    renderProvider();
    expect(attr()).toBe('light');
    expect(screen.getByTestId('pref')).toHaveTextContent('system');
  });

  it('setPreference updates the attribute and persists the choice', async () => {
    renderProvider();
    expect(attr()).toBe('dark');
    await userEvent.click(screen.getByRole('button', { name: 'set light' }));
    expect(attr()).toBe('light');
    expect(localStorage.getItem('theme-preference')).toBe('light');
  });

  it('forces dark on a route that is not migrated but keeps the stored preference', () => {
    nav.pathname = '/login';
    localStorage.setItem('theme-preference', 'light');
    renderProvider();
    expect(attr()).toBe('dark');
    expect(screen.getByTestId('pref')).toHaveTextContent('light');
  });
});

describe('useTheme', () => {
  it('throws a clear error outside a ThemeProvider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<Probe />)).toThrow(/ThemeProvider/);
    spy.mockRestore();
  });
});
