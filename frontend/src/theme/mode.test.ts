import { describe, expect, it } from 'vitest';
import { isMigrated, parsePreference, resolveMode } from './mode';

describe('parsePreference', () => {
  it('accepts the three valid values', () => {
    expect(parsePreference('light')).toBe('light');
    expect(parsePreference('dark')).toBe('dark');
    expect(parsePreference('system')).toBe('system');
  });
  it('falls back to system for anything else', () => {
    expect(parsePreference(null)).toBe('system');
    expect(parsePreference('purple')).toBe('system');
  });
});

describe('isMigrated', () => {
  const routes = ['/', '/design'];
  it('matches "/" only exactly, so it does not migrate every route', () => {
    expect(isMigrated('/', routes)).toBe(true);
    expect(isMigrated('/login', routes)).toBe(false);
  });
  it('matches a route and its children but not look-alike prefixes', () => {
    expect(isMigrated('/design', routes)).toBe(true);
    expect(isMigrated('/design/tokens', routes)).toBe(true);
    expect(isMigrated('/designer', routes)).toBe(false);
  });
});

describe('resolveMode', () => {
  const base = { pathname: '/design', systemDark: true, migratedRoutes: ['/design'] };
  it('follows the system when the preference is system', () => {
    expect(resolveMode({ ...base, preference: 'system', systemDark: true })).toBe('dark');
    expect(resolveMode({ ...base, preference: 'system', systemDark: false })).toBe('light');
  });
  it('honors an explicit preference on a migrated route', () => {
    expect(resolveMode({ ...base, preference: 'light' })).toBe('light');
    expect(resolveMode({ ...base, preference: 'dark', systemDark: false })).toBe('dark');
  });
  it('forces dark on routes that have not been redesigned yet', () => {
    expect(resolveMode({ ...base, pathname: '/login', preference: 'light', systemDark: false })).toBe('dark');
  });
});
