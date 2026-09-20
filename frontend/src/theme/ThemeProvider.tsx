'use client';

import { createContext, useCallback, useContext, useLayoutEffect, useMemo, useSyncExternalStore, type ReactNode } from 'react';
import { usePathname } from 'next/navigation';
import { MIGRATED_ROUTES } from './migrated-routes';
import { THEME_STORAGE_KEY, parsePreference, resolveMode, type Mode, type Preference } from './mode';

interface ThemeContextValue {
  preference: Preference;
  mode: Mode;
  setPreference: (preference: Preference) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

const MEDIA = '(prefers-color-scheme: dark)';
const LOCAL_EVENT = 'theme-preference-change';

// Holds a choice whose localStorage write failed (blocked storage), so it still applies for this session.
// It is null whenever storage is working, which keeps localStorage the source of truth.
let unpersistedPreference: Preference | null = null;

function subscribePreference(notify: () => void) {
  // A storage event means another tab wrote successfully, so storage is authoritative again. Events for
  // other keys are unrelated; key === null means storage.clear(), which does concern us.
  const onStorage = (e: StorageEvent) => {
    if (e.key !== null && e.key !== THEME_STORAGE_KEY) return;
    unpersistedPreference = null;
    notify();
  };
  window.addEventListener('storage', onStorage);
  window.addEventListener(LOCAL_EVENT, notify);
  return () => {
    window.removeEventListener('storage', onStorage);
    window.removeEventListener(LOCAL_EVENT, notify);
  };
}

function readPreference(): Preference {
  if (unpersistedPreference !== null) return unpersistedPreference;
  try {
    return parsePreference(localStorage.getItem(THEME_STORAGE_KEY));
  } catch {
    return 'system';
  }
}

function subscribeSystem(notify: () => void) {
  const query = window.matchMedia(MEDIA);
  query.addEventListener('change', notify);
  return () => query.removeEventListener('change', notify);
}

const readSystemDark = () => window.matchMedia(MEDIA).matches;
const subscribeNever = () => () => {};

export function ThemeProvider({
  children,
  migratedRoutes = MIGRATED_ROUTES,
}: {
  children: ReactNode;
  migratedRoutes?: readonly string[];
}) {
  const pathname = usePathname();
  // The server snapshot is what hydration renders with, so the first client render matches the server HTML.
  const preference = useSyncExternalStore(subscribePreference, readPreference, () => 'system' as Preference);
  const systemDark = useSyncExternalStore(subscribeSystem, readSystemDark, () => true);
  const mounted = useSyncExternalStore(subscribeNever, () => true, () => false);

  const mode = resolveMode({ pathname, preference, systemDark, migratedRoutes });

  // Until mounted, leave the attribute the pre-paint script already set; the hydration snapshot is a guess.
  useLayoutEffect(() => {
    if (mounted) document.documentElement.setAttribute('data-theme', mode);
  }, [mounted, mode]);

  const setPreference = useCallback((next: Preference) => {
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next);
      unpersistedPreference = null;
    } catch {
      // Storage can be blocked (private windows). Keep the choice in memory so it applies until reload.
      unpersistedPreference = next;
    }
    window.dispatchEvent(new Event(LOCAL_EVENT));
  }, []);

  const value = useMemo(() => ({ preference, mode, setPreference }), [preference, mode, setPreference]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useOptionalTheme(): ThemeContextValue | null {
  return useContext(ThemeContext);
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used inside <ThemeProvider>');
  return ctx;
}
