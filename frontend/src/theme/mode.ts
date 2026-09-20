export type Preference = 'system' | 'light' | 'dark';
export type Mode = 'light' | 'dark';

export const THEME_STORAGE_KEY = 'theme-preference';

export function parsePreference(raw: string | null): Preference {
  return raw === 'light' || raw === 'dark' || raw === 'system' ? raw : 'system';
}

export function isMigrated(pathname: string, routes: readonly string[]): boolean {
  return routes.some((r) => (r === '/' ? pathname === '/' : pathname === r || pathname.startsWith(`${r}/`)));
}

export function resolveMode(input: {
  pathname: string;
  preference: Preference;
  systemDark: boolean;
  migratedRoutes: readonly string[];
}): Mode {
  if (!isMigrated(input.pathname, input.migratedRoutes)) return 'dark';
  if (input.preference === 'system') return input.systemDark ? 'dark' : 'light';
  return input.preference;
}
