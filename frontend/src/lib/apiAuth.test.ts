import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockFrom = vi.fn();
const mockGetUser = vi.fn();
const mockRpc = vi.fn();

vi.mock('@supabase/supabase-js', () => ({
  createClient: vi.fn(() => ({ from: mockFrom, auth: { getUser: mockGetUser }, rpc: mockRpc })),
}));

process.env.NEXT_PUBLIC_SUPABASE_URL = 'https://mock.supabase.co';
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'mock-anon-key';

import { requireUser } from './apiAuth';

const req = () => new Request('http://localhost/x', { headers: { Authorization: 'Bearer t' } });
const statusRow = (row: unknown, error: unknown = null) => ({
  select: () => ({ eq: () => ({ maybeSingle: async () => ({ data: row, error }) }) }),
});

describe('requireUser - account status (FR-043)', () => {
  beforeEach(() => {
    [mockFrom, mockGetUser, mockRpc].forEach((m) => m.mockReset());
    mockGetUser.mockResolvedValue({ data: { user: { id: 'u1', email: 'u@example.com' } }, error: null });
    mockRpc.mockResolvedValue({ data: 'agent', error: null });
  });

  it('accepts an active account', async () => {
    mockFrom.mockReturnValue(statusRow({ status: 'active' }));
    expect(await requireUser(req())).toEqual({ id: 'u1', email: 'u@example.com', role: 'agent' });
  });

  it.each(['suspended', 'deactivated'])('rejects a %s account even though its token still verifies', async (status) => {
    mockFrom.mockReturnValue(statusRow({ status }));
    expect(await requireUser(req())).toBeNull();
  });

  it('reads the status of the verified caller, not of anyone else', async () => {
    const eq = vi.fn(() => ({ maybeSingle: async () => ({ data: { status: 'active' }, error: null }) }));
    mockFrom.mockReturnValue({ select: () => ({ eq }) });
    await requireUser(req());
    expect(mockFrom).toHaveBeenCalledWith('users');
    expect(eq).toHaveBeenCalledWith('id', 'u1');
  });

  it.each([
    ['status column not migrated yet (row without status)', statusRow({})],
    ['no users row', statusRow(null)],
    ['lookup error (e.g. column missing)', statusRow(null, { message: 'column users.status does not exist' })],
  ])('fails open on %s - a schema lag must not lock everyone out', async (_n, table) => {
    mockFrom.mockReturnValue(table);
    expect(await requireUser(req())).toMatchObject({ id: 'u1' });
  });

  it('fails open when the lookup throws', async () => {
    mockFrom.mockImplementation(() => { throw new Error('boom'); });
    expect(await requireUser(req())).toMatchObject({ id: 'u1' });
  });

  it('still returns null for a bad token before any status lookup', async () => {
    mockGetUser.mockResolvedValue({ data: { user: null }, error: { message: 'bad' } });
    expect(await requireUser(req())).toBeNull();
    expect(mockFrom).not.toHaveBeenCalled();
  });
});
