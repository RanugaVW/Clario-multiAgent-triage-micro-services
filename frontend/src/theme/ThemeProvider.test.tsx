import { act, render, screen } from '@testing-library/react';
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

  it('still applies the choice for the session when storage is blocked', async () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError');
    });
    try {
      renderProvider();
      expect(attr()).toBe('dark');
      await userEvent.click(screen.getByRole('button', { name: 'set light' }));
      expect(attr()).toBe('light');
      expect(screen.getByTestId('pref')).toHaveTextContent('light');
    } finally {
      setItem.mockRestore();
      // Another tab's write arrives as a storage event; it clears the in-memory fallback so it cannot leak into later tests.
      act(() => {
        window.dispatchEvent(new StorageEvent('storage', { key: null }));
      });
    }
  });

  describe('storage events while storage is blocked', () => {
    const blockAndChooseLight = async () => {
      const setItem = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
        throw new DOMException('blocked', 'SecurityError');
      });
      renderProvider();
      await userEvent.click(screen.getByRole('button', { name: 'set light' }));
      expect(attr()).toBe('light');
      return setItem;
    };

    it('ignores a storage event for an unrelated key', async () => {
      const setItem = await blockAndChooseLight();
      try {
        act(() => {
          window.dispatchEvent(new StorageEvent('storage', { key: 'something-else' }));
        });
        expect(attr()).toBe('light');
      } finally {
        setItem.mockRestore();
        act(() => {
          window.dispatchEvent(new StorageEvent('storage', { key: null }));
        });
      }
    });

    it('clears the in-memory choice on storage.clear() (key is null)', async () => {
      const setItem = await blockAndChooseLight();
      try {
        act(() => {
          window.dispatchEvent(new StorageEvent('storage', { key: null }));
        });
        expect(attr()).toBe('dark');
      } finally {
        setItem.mockRestore();
      }
    });

    it('clears the in-memory choice when the theme key itself changes', async () => {
      const setItem = await blockAndChooseLight();
      try {
        act(() => {
          window.dispatchEvent(new StorageEvent('storage', { key: 'theme-preference' }));
        });
        expect(attr()).toBe('dark');
      } finally {
        setItem.mockRestore();
      }
    });
  });
});

describe('ThemeProvider default migratedRoutes', () => {
  // No migratedRoutes prop: proves the real MIGRATED_ROUTES list is what the provider uses at runtime.
  const renderDefault = () =>
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>
    );

  it('honours the stored light preference on a migrated route', () => {
    nav.pathname = '/design';
    localStorage.setItem('theme-preference', 'light');
    renderDefault();
    expect(attr()).toBe('light');
  });

  it('forces dark on a route that is not migrated', () => {
    nav.pathname = '/login';
    localStorage.setItem('theme-preference', 'light');
    renderDefault();
    expect(attr()).toBe('dark');
  });
});

describe('useTheme', () => {
  it('throws a clear error outside a ThemeProvider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<Probe />)).toThrow(/ThemeProvider/);
    spy.mockRestore();
  });
});
