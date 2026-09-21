export type Preference = 'system' | 'light' | 'dark';
export type Mode = 'light' | 'dark';

export const THEME_STORAGE_KEY = 'theme-preference';

export function parsePreference(raw: string | null): Preference {
  return raw === 'light' || raw === 'dark' || raw === 'system' ? raw : 'system';
}

export function resolveMode(input: {
  preference: Preference;
  systemDark: boolean;
}): Mode {
  if (input.preference === 'system') return input.systemDark ? 'dark' : 'light';
  return input.preference;
}
