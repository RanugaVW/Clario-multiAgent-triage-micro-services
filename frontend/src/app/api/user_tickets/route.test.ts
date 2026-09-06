import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockFrom = vi.fn();
const mockGetUser = vi.fn();
const mockRpc = vi.fn();

vi.mock('@supabase/supabase-js', () => ({
  createClient: vi.fn(() => ({
    from: mockFrom,
    auth: { getUser: mockGetUser },
    rpc: mockRpc,
  })),
}));

process.env.NEXT_PUBLIC_SUPABASE_URL = 'https://mock.supabase.co';
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'mock-anon-key';
process.env.SUPABASE_SERVICE_ROLE_KEY = 'mock-service-key';

import { GET } from './route';

function req(url: string, auth: boolean | string = true): Request {
  const headers = new Headers();
  if (auth !== false) headers.set('Authorization', `Bearer ${typeof auth === 'string' ? auth : 'test-token'}`);
  return new Request(url, { headers });
}

function mockTicketsQuery(result: { data: unknown; error: unknown }) {
  const mockOrder = vi.fn().mockResolvedValue(result);
  mockFrom.mockImplementation((table: string) => {
    if (table === 'tickets') return { select: () => ({ eq: () => ({ order: mockOrder }) }) };
    throw new Error(`unexpected table ${table}`);
  });
  return mockOrder;
}

describe('GET /api/user_tickets - IDOR protection', () => {
  beforeEach(() => {
    mockFrom.mockReset();
    mockGetUser.mockReset();
    mockRpc.mockReset();
  });

  it('rejects an unauthenticated request with 401 and never queries Supabase', async () => {
    const res = await GET(req('http://localhost/api/user_tickets?userId=victim-id', false));
    expect(res.status).toBe(401);
    expect(mockFrom).not.toHaveBeenCalled();
  });

  it('rejects a request whose token fails verification with 401', async () => {
    mockGetUser.mockResolvedValue({ data: { user: null }, error: { message: 'bad token' } });
    const res = await GET(req('http://localhost/api/user_tickets?userId=victim-id'));
    expect(res.status).toBe(401);
    expect(mockFrom).not.toHaveBeenCalled();
  });

  it('rejects a plain customer requesting a DIFFERENT userId with 403 (IDOR blocked)', async () => {
    mockGetUser.mockResolvedValue({ data: { user: { id: 'attacker-id' } }, error: null });
    mockRpc.mockResolvedValue({ data: 'user', error: null });

    const res = await GET(req('http://localhost/api/user_tickets?userId=victim-id'));

    expect(res.status).toBe(403);
    expect(mockFrom).not.toHaveBeenCalled();
  });

  it('allows a plain customer requesting their OWN userId (positive control)', async () => {
    mockGetUser.mockResolvedValue({ data: { user: { id: 'u1' } }, error: null });
    mockRpc.mockResolvedValue({ data: 'user', error: null });
    mockTicketsQuery({ data: [{ id: 't1' }], error: null });

    const res = await GET(req('http://localhost/api/user_tickets?userId=u1'));
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.data).toEqual([{ id: 't1' }]);
  });

  it('allows staff (admin role) to request a userId that is not their own', async () => {
    mockGetUser.mockResolvedValue({ data: { user: { id: 'admin-id' } }, error: null });
    mockRpc.mockResolvedValue({ data: 'admin', error: null });
    mockTicketsQuery({ data: [{ id: 't1' }], error: null });

    const res = await GET(req('http://localhost/api/user_tickets?userId=some-customer-id'));

    expect(res.status).toBe(200);
  });

  it('still 400s when userId is missing, for an otherwise-authenticated caller', async () => {
    mockGetUser.mockResolvedValue({ data: { user: { id: 'u1' } }, error: null });
    mockRpc.mockResolvedValue({ data: 'user', error: null });

    const res = await GET(req('http://localhost/api/user_tickets'));

    expect(res.status).toBe(400);
  });
});
