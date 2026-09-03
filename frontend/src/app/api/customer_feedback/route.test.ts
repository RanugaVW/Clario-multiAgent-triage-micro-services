import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockSingle = vi.fn();
const mockUpsert = vi.fn();
const mockFrom = vi.fn();

vi.mock('@supabase/supabase-js', () => ({
  createClient: vi.fn(() => ({
    from: mockFrom,
  })),
}));

process.env.NEXT_PUBLIC_SUPABASE_URL = 'https://mock.supabase.co';
process.env.SUPABASE_SERVICE_ROLE_KEY = 'mock-service-key';

import { POST } from './route';

function jsonRequest(body: unknown): Request {
  return new Request('http://localhost/api/customer_feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

describe('POST /api/customer_feedback', () => {
  beforeEach(() => {
    mockFrom.mockReset();
    mockSingle.mockReset();
    mockUpsert.mockReset();
  });

  it('rejects a score outside 1-5 with 400', async () => {
    const res = await POST(jsonRequest({ ticketId: 't1', userId: 'u1', score: 7 }));
    expect(res.status).toBe(400);
  });

  it('rejects a non-integer score with 400', async () => {
    const res = await POST(jsonRequest({ ticketId: 't1', userId: 'u1', score: 3.5 }));
    expect(res.status).toBe(400);
  });

  it('returns 403 when the ticket does not belong to the user', async () => {
    mockFrom.mockImplementation((table: string) => {
      if (table === 'tickets') {
        return { select: () => ({ eq: () => ({ eq: () => ({ single: mockSingle }) }) }) };
      }
      throw new Error(`unexpected table ${table}`);
    });
    mockSingle.mockResolvedValue({ data: null, error: null });

    const res = await POST(jsonRequest({ ticketId: 't1', userId: 'u1', score: 4 }));

    expect(res.status).toBe(403);
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

    const res = await POST(jsonRequest({ ticketId: 't1', userId: 'u1', score: 4, comment: 'Helpful' }));
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

    const res = await POST(jsonRequest({ ticketId: 't1', userId: 'u1', score: 4 }));

    expect(res.status).toBe(500);
  });
});
