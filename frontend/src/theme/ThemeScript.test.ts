import { describe, expect, it } from 'vitest';
import { parsePreference, resolveMode } from './mode';
import { buildThemeScript } from './ThemeScript';

function run(script: string, opts: { stored: string | null; systemDark: boolean; storageThrows?: boolean; matchMedia?: 'throws' | 'undefined' }) {
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
    { pathname: '/admin' },
    localStorageStub,
    opts.matchMedia === 'undefined'
      ? undefined
      : () => {
          if (opts.matchMedia === 'throws') throw new Error('unavailable');
          return { matches: opts.systemDark };
        }
  );
  return attrs['data-theme'];
}

describe('buildThemeScript', () => {
  const script = buildThemeScript();

  it('always agrees with resolveMode', () => {
    for (const stored of [null, 'light', 'dark', 'system', 'garbage']) {
      for (const systemDark of [true, false]) {
        const expected = resolveMode({ preference: parsePreference(stored), systemDark });
        expect(run(script, { stored, systemDark }), `${stored} ${systemDark}`).toBe(expected);
      }
    }
  });

  it('does not look at the path: a stored light preference wins on any route', () => {
    expect(run(script, { stored: 'light', systemDark: true })).toBe('light');
    expect(script).not.toMatch(/pathname|routes/);
  });

  // A throwing localStorage.getItem must behave like ThemeProvider.readPreference: preference 'system', so the
  // system setting still decides. Landing on dark here would flash the wrong theme before hydration.
  it.each([true, false])('treats blocked storage as the system preference (systemDark=%s)', (systemDark) => {
    const expected = resolveMode({ preference: 'system', systemDark });
    expect(run(script, { stored: 'light', systemDark, storageThrows: true })).toBe(expected);
  });

  // The outer catch must still honour a stored light/dark preference; it only falls back to dark otherwise.
  it.each(['throws', 'undefined'] as const)('honours a stored light preference when matchMedia %s', (matchMedia) => {
    expect(run(script, { stored: 'light', systemDark: true, matchMedia })).toBe('light');
    expect(run(script, { stored: 'dark', systemDark: false, matchMedia })).toBe('dark');
  });

  it.each(['system', null, 'garbage'])('falls back to dark for stored %s when matchMedia throws', (stored) => {
    expect(run(script, { stored, systemDark: false, matchMedia: 'throws' })).toBe('dark');
  });
});
