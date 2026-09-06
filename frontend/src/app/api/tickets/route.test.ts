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

import { GET, PUT, DELETE } from './route';

function req(url: string, init: RequestInit & { auth?: boolean | string } = {}): Request {
  const { auth, ...rest } = init;
  const headers = new Headers(rest.headers);
  if (auth !== false) headers.set('Authorization', `Bearer ${typeof auth === 'string' ? auth : 'test-token'}`);
  return new Request(url, { ...rest, headers });
}

describe('/api/tickets - staff-only authorization', () => {
  beforeEach(() => {
    mockFrom.mockReset();
    mockGetUser.mockReset();
    mockRpc.mockReset();
  });

  describe('unauthenticated / unauthorized callers are rejected before touching data', () => {
    it('GET with no Authorization header returns 401 and never queries Supabase', async () => {
      const res = await GET(req('http://localhost/api/tickets', { auth: false }));
      expect(res.status).toBe(401);
      expect(mockFrom).not.toHaveBeenCalled();
    });

    it('GET with a token that fails verification returns 401', async () => {
      mockGetUser.mockResolvedValue({ data: { user: null }, error: { message: 'bad token' } });
      const res = await GET(req('http://localhost/api/tickets'));
      expect(res.status).toBe(401);
      expect(mockFrom).not.toHaveBeenCalled();
    });

    it('GET with a valid token but role=user returns 403 and never queries Supabase', async () => {
      mockGetUser.mockResolvedValue({ data: { user: { id: 'u1', email: 'u1@example.com' } }, error: null });
      mockRpc.mockResolvedValue({ data: 'user', error: null });
      const res = await GET(req('http://localhost/api/tickets'));
      expect(res.status).toBe(403);
      expect(mockFrom).not.toHaveBeenCalled();
    });

    it('DELETE with no Authorization header returns 401 and never deletes anything', async () => {
      const res = await DELETE(req('http://localhost/api/tickets?id=t1', { auth: false }));
      expect(res.status).toBe(401);
      expect(mockFrom).not.toHaveBeenCalled();
    });

    it('PUT with no Authorization header returns 401 and never writes a resolution', async () => {
      const res = await PUT(req('http://localhost/api/tickets', {
        auth: false,
        method: 'PUT',
        body: JSON.stringify({ id: 't1', final_response: 'forged' }),
      }));
      expect(res.status).toBe(401);
      expect(mockFrom).not.toHaveBeenCalled();
    });
  });

  describe('staff (admin/agent) role is let through', () => {
    beforeEach(() => {
      mockGetUser.mockResolvedValue({ data: { user: { id: 'staff-1', email: 'staff@example.com' } }, error: null });
      mockRpc.mockResolvedValue({ data: 'admin', error: null });
    });

    it('GET returns the ticket list for an admin-role caller', async () => {
      const mockOrder = vi.fn().mockResolvedValue({ data: [{ id: 't1' }], error: null });
      mockFrom.mockImplementation((table: string) => {
        if (table === 'tickets') return { select: () => ({ order: mockOrder }) };
        throw new Error(`unexpected table ${table}`);
      });

      const res = await GET(req('http://localhost/api/tickets'));
      const body = await res.json();

      expect(res.status).toBe(200);
      expect(body.data).toEqual([{ id: 't1' }]);
    });

    it('agent role (not just admin) is also let through', async () => {
      mockRpc.mockResolvedValue({ data: 'agent', error: null });
      const mockOrder = vi.fn().mockResolvedValue({ data: [], error: null });
      mockFrom.mockImplementation(() => ({ select: () => ({ order: mockOrder }) }));

      const res = await GET(req('http://localhost/api/tickets'));
      expect(res.status).toBe(200);
    });
  });
});
