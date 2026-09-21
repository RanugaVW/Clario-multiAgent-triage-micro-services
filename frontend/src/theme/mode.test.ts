import { describe, expect, it } from 'vitest';
import { parsePreference, resolveMode } from './mode';

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

describe('resolveMode', () => {
  const base = { systemDark: true };
  it('follows the system when the preference is system', () => {
    expect(resolveMode({ ...base, preference: 'system', systemDark: true })).toBe('dark');
    expect(resolveMode({ ...base, preference: 'system', systemDark: false })).toBe('light');
  });
  it('honors an explicit preference', () => {
    expect(resolveMode({ ...base, preference: 'light' })).toBe('light');
    expect(resolveMode({ ...base, preference: 'dark', systemDark: false })).toBe('dark');
  });
  it('has no route gate: the light preference always wins over a dark system', () => {
    expect(resolveMode({ preference: 'light', systemDark: true })).toBe('light');
  });
});
