import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockFrom = vi.fn();
// The auth helper also reads the caller's own `users` row (account status, FR-043); "never touched data" means no other table.
const dataQueries = () => mockFrom.mock.calls.filter(([table]: unknown[]) => table !== 'users');
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
      expect(dataQueries()).toEqual([]);
    });

    it('GET with a token that fails verification returns 401', async () => {
      mockGetUser.mockResolvedValue({ data: { user: null }, error: { message: 'bad token' } });
      const res = await GET(req('http://localhost/api/tickets'));
      expect(res.status).toBe(401);
      expect(dataQueries()).toEqual([]);
    });

    it('GET with a valid token but role=user returns 403 and never queries Supabase', async () => {
      mockGetUser.mockResolvedValue({ data: { user: { id: 'u1', email: 'u1@example.com' } }, error: null });
      mockRpc.mockResolvedValue({ data: 'user', error: null });
      const res = await GET(req('http://localhost/api/tickets'));
      expect(res.status).toBe(403);
      expect(dataQueries()).toEqual([]);
    });

    it('DELETE with no Authorization header returns 401 and never deletes anything', async () => {
      const res = await DELETE(req('http://localhost/api/tickets?id=t1', { auth: false }));
      expect(res.status).toBe(401);
      expect(dataQueries()).toEqual([]);
    });

    it('PUT with no Authorization header returns 401 and never writes a resolution', async () => {
      const res = await PUT(req('http://localhost/api/tickets', {
        auth: false,
        method: 'PUT',
        body: JSON.stringify({ id: 't1', final_response: 'forged' }),
      }));
      expect(res.status).toBe(401);
      expect(dataQueries()).toEqual([]);
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
  describe('PUT - resolving a ticket (FR-035/FR-036)', () => {
    let calls: string[];
    let insertedRow: Record<string, unknown> | undefined;
    let deletedResolutionId: string | undefined;
    let reviewUpdate: { id: string; row: Record<string, unknown> } | undefined;

    // Builds a `from()` fake for the three writes PUT performs and records the
    // order they happen in, so the tests can assert ordering and compensation.
    function stubTables(opts: {
      ticket?: {
        id: string;
        status: string;
        resolutions: { id: string; escalated: boolean }[];
        human_reviews?: { id: string; original_draft: string | null; decision: string | null }[];
      } | null;
      lookupError?: string;
      insertError?: string;
      updateError?: string;
      reviewError?: string;
    }) {
      mockFrom.mockImplementation((table: string) => {
        if (table === 'tickets') {
          return {
            select: () => ({
              eq: () => ({
                maybeSingle: async () => {
                  calls.push('lookup');
                  return opts.lookupError
                    ? { data: null, error: { message: opts.lookupError } }
                    : { data: opts.ticket === undefined ? { id: 't1', status: 'escalated', resolutions: [] } : opts.ticket, error: null };
                },
              }),
            }),
            update: () => ({
              eq: async () => {
                calls.push('update-status');
                return { error: opts.updateError ? { message: opts.updateError } : null };
              },
            }),
          };
        }
        if (table === 'resolutions') {
          return {
            insert: (row: Record<string, unknown>) => {
              calls.push('insert-resolution');
              insertedRow = row;
              return {
                select: () => ({
                  single: async () =>
                    opts.insertError
                      ? { data: null, error: { message: opts.insertError } }
                      : { data: { id: 'res-1' }, error: null },
                }),
              };
            },
            delete: () => ({
              eq: async (_col: string, value: string) => {
                calls.push('delete-resolution');
                deletedResolutionId = value;
                return { error: null };
              },
            }),
          };
        }
        if (table === 'human_reviews') {
          return {
            update: (row: Record<string, unknown>) => ({
              eq: async (_col: string, value: string) => {
                calls.push('update-review');
                reviewUpdate = { id: value, row };
                return { error: opts.reviewError ? { message: opts.reviewError } : null };
              },
            }),
          };
        }
        throw new Error(`unexpected table ${table}`);
      });
    }

    const put = (body: unknown) =>
      PUT(req('http://localhost/api/tickets', { method: 'PUT', body: typeof body === 'string' ? body : JSON.stringify(body) }));

    beforeEach(() => {
      calls = [];
      insertedRow = undefined;
      deletedResolutionId = undefined;
      reviewUpdate = undefined;
      mockGetUser.mockResolvedValue({ data: { user: { id: 'agent-7', email: 'a@example.com' } }, error: null });
      mockRpc.mockResolvedValue({ data: 'agent', error: null });
    });

    it('records the verified caller as resolved_by and trims the response', async () => {
      stubTables({});
      const res = await put({ id: 't1', final_response: '  Try resetting your password.  ' });

      expect(res.status).toBe(200);
      expect(insertedRow).toMatchObject({
        ticket_id: 't1',
        final_response: 'Try resetting your password.',
        escalated: false,
        resolved_by: 'agent-7',
      });
    });

    it('does not let the request body choose who resolved the ticket', async () => {
      stubTables({});
      await put({ id: 't1', final_response: 'ok', resolved_by: 'someone-else' });
      expect(insertedRow?.resolved_by).toBe('agent-7');
    });

    it('writes the resolution before flipping the ticket status', async () => {
      stubTables({});
      await put({ id: 't1', final_response: 'ok' });
      expect(calls).toEqual(['lookup', 'insert-resolution', 'update-status']);
    });

    it('takes the resolution back when the status update fails', async () => {
      stubTables({ updateError: 'db down' });
      const res = await put({ id: 't1', final_response: 'ok' });

      expect(res.status).toBe(500);
      expect(calls).toEqual(['lookup', 'insert-resolution', 'update-status', 'delete-resolution']);
      expect(deletedResolutionId).toBe('res-1');
    });

    it('does not touch the status when the resolution insert fails', async () => {
      stubTables({ insertError: 'insert failed' });
      const res = await put({ id: 't1', final_response: 'ok' });

      expect(res.status).toBe(500);
      expect(calls).toEqual(['lookup', 'insert-resolution']);
    });

    it('returns 404 for an unknown ticket and writes nothing', async () => {
      stubTables({ ticket: null });
      const res = await put({ id: 'missing', final_response: 'ok' });

      expect(res.status).toBe(404);
      expect(calls).toEqual(['lookup']);
    });

    it('returns 409 when the ticket is already resolved', async () => {
      stubTables({ ticket: { id: 't1', status: 'resolved', resolutions: [] } });
      const res = await put({ id: 't1', final_response: 'second answer' });

      expect(res.status).toBe(409);
      expect(calls).toEqual(['lookup']);
    });

    it('returns 409 when a non-escalated resolution already exists', async () => {
      stubTables({ ticket: { id: 't1', status: 'escalated', resolutions: [{ id: 'r0', escalated: false }] } });
      const res = await put({ id: 't1', final_response: 'second answer' });

      expect(res.status).toBe(409);
    });

    it('still allows resolving a ticket whose only resolution row is the escalation marker', async () => {
      stubTables({ ticket: { id: 't1', status: 'escalated', resolutions: [{ id: 'r0', escalated: true }] } });
      const res = await put({ id: 't1', final_response: 'human answer' });

      expect(res.status).toBe(200);
    });

    it.each([
      ['missing id', { final_response: 'x' }],
      ['blank response', { id: 't1', final_response: '   ' }],
      ['non-string id', { id: 42, final_response: 'x' }],
    ])('rejects %s with 400 before any database call', async (_name, body) => {
      stubTables({});
      const res = await put(body);

      expect(res.status).toBe(400);
      expect(dataQueries()).toEqual([]);
    });

    it('rejects a malformed JSON body with 400 instead of crashing', async () => {
      stubTables({});
      const res = await put('{not json');

      expect(res.status).toBe(400);
      expect(dataQueries()).toEqual([]);
    });

    describe('recording the human review (learning signal)', () => {
      const pendingReview = [{ id: 'hr-1', original_draft: 'Try resetting your password.', decision: 'pending' }];
      const escalated = (human_reviews: { id: string; original_draft: string | null; decision: string | null }[]) => ({
        id: 't1', status: 'escalated', resolutions: [], human_reviews,
      });

      it('marks a changed reply as edited and stores the final draft, reviewer and time', async () => {
        stubTables({ ticket: escalated(pendingReview) });
        const res = await put({ id: 't1', final_response: 'Please reset your password from the login page.' });

        expect(res.status).toBe(200);
        expect(reviewUpdate?.id).toBe('hr-1');
        expect(reviewUpdate?.row).toMatchObject({
          decision: 'edited',
          final_draft: 'Please reset your password from the login page.',
          reviewer_id: 'agent-7',
        });
        expect(typeof reviewUpdate?.row.reviewed_at).toBe('string');
      });

      it('marks a reply that differs only by whitespace as approved_unchanged', async () => {
        stubTables({ ticket: escalated(pendingReview) });
        await put({ id: 't1', final_response: '  Try   resetting your\npassword.  ' });
        expect(reviewUpdate?.row.decision).toBe('approved_unchanged');
      });

      it('marks a reply equal to the [CUSTOMER RESPONSE] section of the draft as approved_unchanged', async () => {
        stubTables({
          ticket: escalated([{
            id: 'hr-1',
            original_draft: '[INTERNAL TECHNICAL REPORT]\nroot cause X\n\n[CUSTOMER RESPONSE]\nHello, please restart the app.',
            decision: 'pending',
          }]),
        });
        await put({ id: 't1', final_response: 'Hello, please restart the app.' });
        expect(reviewUpdate?.row.decision).toBe('approved_unchanged');
      });

      it('writes nothing to human_reviews when there is no pending review', async () => {
        stubTables({ ticket: escalated([{ id: 'hr-0', original_draft: 'x', decision: 'edited' }]) });
        const res = await put({ id: 't1', final_response: 'ok' });

        expect(res.status).toBe(200);
        expect(calls).not.toContain('update-review');
      });

      it('still resolves the ticket when the human_reviews update fails', async () => {
        stubTables({ ticket: escalated(pendingReview), reviewError: 'db hiccup' });
        const res = await put({ id: 't1', final_response: 'A different answer.' });

        expect(res.status).toBe(200);
        expect(calls).toContain('update-review');
      });

      it('writes the review only after the status flip succeeded', async () => {
        stubTables({ ticket: escalated(pendingReview) });
        await put({ id: 't1', final_response: 'A different answer.' });
        expect(calls).toEqual(['lookup', 'insert-resolution', 'update-status', 'update-review']);
      });

      it('does not touch human_reviews when the status update fails and the resolution is rolled back', async () => {
        stubTables({ ticket: escalated(pendingReview), updateError: 'db down' });
        const res = await put({ id: 't1', final_response: 'A different answer.' });

        expect(res.status).toBe(500);
        expect(calls).not.toContain('update-review');
      });
    });
  });
});
