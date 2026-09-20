import { describe, expect, it } from 'vitest';
import { parsePreference, resolveMode } from './mode';
import { buildThemeScript } from './ThemeScript';

const ROUTES = ['/', '/design'];

function run(script: string, opts: { pathname: string; stored: string | null; systemDark: boolean; storageThrows?: boolean }) {
  const attrs: Record<string, string> = {};
  const documentStub = { documentElement: { setAttribute: (k: string, v: string) => (attrs[k] = v) } };
  const localStorageStub = {
    getItem: () => {
      if (opts.storageThrows) throw new Error('blocked');
      return opts.stored;
    },
  };
  new Function('document', 'location', 'localStorage', 'matchMedia', script)(
    documentStub,
    { pathname: opts.pathname },
    localStorageStub,
    () => ({ matches: opts.systemDark })
  );
  return attrs['data-theme'];
}

describe('buildThemeScript', () => {
  const script = buildThemeScript(ROUTES);

  it('always agrees with resolveMode', () => {
    for (const pathname of ['/', '/design', '/design/x', '/login', '/designer']) {
      for (const stored of [null, 'light', 'dark', 'system', 'garbage']) {
        for (const systemDark of [true, false]) {
          const expected = resolveMode({
            pathname,
            preference: parsePreference(stored),
            systemDark,
            migratedRoutes: ROUTES,
          });
          expect(run(script, { pathname, stored, systemDark }), `${pathname} ${stored} ${systemDark}`).toBe(expected);
        }
      }
    }
  });

  it('falls back to dark when storage is blocked', () => {
    expect(run(script, { pathname: '/design', stored: 'light', systemDark: false, storageThrows: true })).toBe('dark');
  });
});
