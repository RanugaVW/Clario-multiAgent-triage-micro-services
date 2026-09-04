import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockSingle = vi.fn();
const mockUpsert = vi.fn();
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

import { POST } from './route';

const CALLER_ID = 'u1';

function jsonRequest(body: unknown, opts: { auth?: boolean } = { auth: true }): Request {
  return new Request('http://localhost/api/customer_feedback', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(opts.auth === false ? {} : { Authorization: 'Bearer test-token' }),
    },
    body: JSON.stringify(body),
  });
}

describe('POST /api/customer_feedback', () => {
  beforeEach(() => {
    mockFrom.mockReset();
    mockSingle.mockReset();
    mockUpsert.mockReset();
    mockGetUser.mockReset();
    mockRpc.mockReset();
    // Default: a valid, authenticated plain customer - individual tests
    // override this to exercise the auth-rejection paths.
    mockGetUser.mockResolvedValue({ data: { user: { id: CALLER_ID, email: 'u1@example.com' } }, error: null });
    mockRpc.mockResolvedValue({ data: 'user', error: null });
  });

  it('rejects a request with no Authorization header with 401', async () => {
    const res = await POST(jsonRequest({ ticketId: 't1', score: 4 }, { auth: false }));
    expect(res.status).toBe(401);
    expect(mockFrom).not.toHaveBeenCalled();
  });

  it('rejects a request whose token fails verification with 401', async () => {
    mockGetUser.mockResolvedValue({ data: { user: null }, error: { message: 'invalid token' } });

    const res = await POST(jsonRequest({ ticketId: 't1', score: 4 }));

    expect(res.status).toBe(401);
    expect(mockFrom).not.toHaveBeenCalled();
  });

  it('rejects a score outside 1-5 with 400', async () => {
    const res = await POST(jsonRequest({ ticketId: 't1', score: 7 }));
    expect(res.status).toBe(400);
  });

  it('rejects a non-integer score with 400', async () => {
    const res = await POST(jsonRequest({ ticketId: 't1', score: 3.5 }));
    expect(res.status).toBe(400);
  });

  it('returns 403 when the ticket does not belong to the authenticated caller', async () => {
    mockFrom.mockImplementation((table: string) => {
      if (table === 'tickets') {
        return { select: () => ({ eq: () => ({ eq: () => ({ single: mockSingle }) }) }) };
      }
      throw new Error(`unexpected table ${table}`);
    });
    mockSingle.mockResolvedValue({ data: null, error: null });

    const res = await POST(jsonRequest({ ticketId: 't1', score: 4 }));

    expect(res.status).toBe(403);
  });

  it('ignores a client-supplied userId and scopes ownership to the verified caller only', async () => {
    mockFrom.mockImplementation((table: string) => {
      if (table === 'tickets') {
        return {
          select: () => ({
            eq: () => ({
              eq: (col: string, value: string) => {
                expect(col).toBe('user_id');
                expect(value).toBe(CALLER_ID); // never the spoofed body.userId below
                return { single: mockSingle };
              },
            }),
          }),
        };
      }
      if (table === 'customer_feedback') {
        return { upsert: mockUpsert };
      }
      throw new Error(`unexpected table ${table}`);
    });
    mockSingle.mockResolvedValue({ data: { id: 't1' }, error: null });
    mockUpsert.mockResolvedValue({ data: [{ id: 'f1', ticket_id: 't1', score: 4 }], error: null });

    // Body claims a different user entirely - the route must not trust this.
    const res = await POST(jsonRequest({ ticketId: 't1', userId: 'someone-else', score: 4 }));

    expect(res.status).toBe(200);
  });

  it('upserts feedback on ticket_id when ownership check passes', async () => {
    mockFrom.mockImplementation((table: string) => {
      if (table === 'tickets') {
        return { select: () => ({ eq: () => ({ eq: () => ({ single: mockSingle }) }) }) };
      }
      if (table === 'customer_feedback') {
        return { upsert: mockUpsert };
      }
      throw new Error(`unexpected table ${table}`);
    });
    mockSingle.mockResolvedValue({ data: { id: 't1' }, error: null });
    mockUpsert.mockResolvedValue({ data: [{ id: 'f1', ticket_id: 't1', score: 4 }], error: null });

    const res = await POST(jsonRequest({ ticketId: 't1', score: 4, comment: 'Helpful' }));
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.data).toEqual([{ id: 'f1', ticket_id: 't1', score: 4 }]);
    expect(mockUpsert).toHaveBeenCalledWith(
      expect.objectContaining({ ticket_id: 't1', score: 4, comment: 'Helpful' }),
      expect.objectContaining({ onConflict: 'ticket_id' })
    );
  });

  it('returns 500 when the upsert itself fails', async () => {
    mockFrom.mockImplementation((table: string) => {
      if (table === 'tickets') {
        return { select: () => ({ eq: () => ({ eq: () => ({ single: mockSingle }) }) }) };
      }
      if (table === 'customer_feedback') {
        return { upsert: mockUpsert };
      }
      throw new Error(`unexpected table ${table}`);
    });
    mockSingle.mockResolvedValue({ data: { id: 't1' }, error: null });
    mockUpsert.mockResolvedValue({ data: null, error: { message: 'db exploded' } });

    const res = await POST(jsonRequest({ ticketId: 't1', score: 4 }));

    expect(res.status).toBe(500);
  });
});
