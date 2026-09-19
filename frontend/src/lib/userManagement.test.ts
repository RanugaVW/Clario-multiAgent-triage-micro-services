import { describe, it, expect } from 'vitest';
import { validateChange, isActive, banDurationFor, type ManagedUser } from './userManagement';

const target: ManagedUser = { id: 'u2', email: 'u2@example.com', role: 'user', status: 'active' };
const actor = 'admin-1';

describe('validateChange', () => {
  it('accepts a role change and reports only what changes', () => {
    expect(validateChange(actor, { id: 'u2', role: 'agent' }, target)).toEqual({ ok: true, change: { id: 'u2', role: 'agent' } });
  });
  it('accepts a status change, and both together', () => {
    expect(validateChange(actor, { id: 'u2', status: 'suspended' }, target)).toEqual({ ok: true, change: { id: 'u2', status: 'suspended' } });
    expect(validateChange(actor, { id: 'u2', role: 'admin', status: 'deactivated' }, target)).toEqual({
      ok: true, change: { id: 'u2', role: 'admin', status: 'deactivated' },
    });
  });
  it('drops the parts that would not change anything', () => {
    expect(validateChange(actor, { id: 'u2', role: 'user', status: 'suspended' }, target)).toEqual({ ok: true, change: { id: 'u2', status: 'suspended' } });
  });
  it('rejects a request that changes nothing', () => {
    const r = validateChange(actor, { id: 'u2', role: 'user', status: 'active' }, target);
    expect(r).toMatchObject({ ok: false, httpStatus: 400 });
  });

  it.each([
    ['missing id', { role: 'agent' }],
    ['non-string id', { id: 5, role: 'agent' }],
    ['nothing to change', { id: 'u2' }],
    ['unknown role', { id: 'u2', role: 'superuser' }],
    ['role of the wrong type', { id: 'u2', role: 1 }],
    ['unknown status', { id: 'u2', status: 'banned' }],
    ['prototype-ish role', { id: 'u2', role: 'constructor' }],
    ['empty-string role', { id: 'u2', role: '' }],
  ])('A1: rejects %s with 400', (_n, body) => {
    expect(validateChange(actor, body, target)).toMatchObject({ ok: false, httpStatus: 400 });
  });

  it('rejects an unknown user with 404 (after the input itself is validated)', () => {
    expect(validateChange(actor, { id: 'ghost', role: 'agent' }, null)).toMatchObject({ ok: false, httpStatus: 404 });
    expect(validateChange(actor, { id: 'ghost', role: 'nope' }, null)).toMatchObject({ ok: false, httpStatus: 400 });
  });

  it('forbids changing your own role or status, whatever the values', () => {
    const self: ManagedUser = { ...target, id: actor, role: 'admin' };
    expect(validateChange(actor, { id: actor, role: 'user' }, self)).toMatchObject({ ok: false, httpStatus: 403 });
    expect(validateChange(actor, { id: actor, status: 'suspended' }, self)).toMatchObject({ ok: false, httpStatus: 403 });
  });
});

describe('account helpers', () => {
  it('isActive is true only for active, and for a not-yet-migrated (missing) status', () => {
    expect(isActive('active')).toBe(true);
    expect(isActive(undefined)).toBe(true);
    expect(isActive(null)).toBe(true);
    expect(isActive('suspended')).toBe(false);
    expect(isActive('deactivated')).toBe(false);
    expect(isActive('weird')).toBe(false);
  });
  it('bans for anything but active and lifts the ban on activation', () => {
    expect(banDurationFor('active')).toBe('none');
    expect(banDurationFor('suspended')).not.toBe('none');
    expect(banDurationFor('deactivated')).not.toBe('none');
  });
});
