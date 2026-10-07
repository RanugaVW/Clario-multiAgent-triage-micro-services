import { describe, it, expect, vi, beforeEach } from 'vitest';

// A tiny stand-in for the supabase-js query builder: every chain method
// records its call and returns the builder; awaiting it (or .single()/
// .maybeSingle()) resolves to whatever the test queued for that table.
type Result = { data?: unknown; error?: unknown };
const results: Record<string, Result[]> = {};
const calls: { table: string; method: string; args: unknown[] }[] = [];

function builder(table: string) {
  const next = () => Promise.resolve(results[table]?.shift() ?? { data: null, error: null });
  const b: Record<string, unknown> = {};
  for (const method of ['select', 'eq', 'order', 'upsert', 'update']) {
    b[method] = (...args: unknown[]) => {
      calls.push({ table, method, args });
      return b;
    };
  }
  b.single = next;
  b.maybeSingle = next;
  b.then = (resolve: (r: Result) => unknown, reject: (e: unknown) => unknown) => next().then(resolve, reject);
  return b;
}

const mockGetUser = vi.fn();
const mockRpc = vi.fn();
vi.mock('@supabase/supabase-js', () => ({
  createClient: vi.fn(() => ({ from: builder, auth: { getUser: mockGetUser }, rpc: mockRpc })),
}));

const mockStatusAfterReply = vi.fn();
vi.mock('../../../../../lib/ticketThread', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../../../lib/ticketThread')>()),
  statusAfterReply: (...args: unknown[]) => mockStatusAfterReply(...args),
}));

process.env.NEXT_PUBLIC_SUPABASE_URL = 'https://mock.supabase.co';
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'mock-anon-key';
process.env.SUPABASE_SERVICE_ROLE_KEY = 'mock-service-key';

import { GET, POST } from './route';

const TICKET_ID = '11111111-1111-4111-8111-111111111111';
const CLIENT_MSG_ID = '22222222-2222-4222-8222-222222222222';
const SAVED = {
  id: 'm1', ticket_id: TICKET_ID, author_id: 'u1', author_role: 'user',
  body: 'Still broken', client_msg_id: CLIENT_MSG_ID, created_at: '2026-10-01T10:00:00Z',
};

const ctx = (id = TICKET_ID) => ({ params: Promise.resolve({ id }) });

function request(method: 'GET' | 'POST', body?: unknown, auth = true): Request {
  return new Request(`http://localhost/api/tickets/${TICKET_ID}/messages`, {
    method,
    headers: { 'Content-Type': 'application/json', ...(auth ? { Authorization: 'Bearer t' } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

function signedInAs(id: string, role: 'user' | 'agent' | 'admin') {
  mockGetUser.mockResolvedValue({ data: { user: { id, email: `${id}@example.com` } }, error: null });
  mockRpc.mockResolvedValue({ data: role, error: null });
}

function queue(table: string, ...r: Result[]) {
  (results[table] ??= []).push(...r);
}

const ownTicket = (status = 'resolved') => ({ data: { id: TICKET_ID, user_id: 'u1', status }, error: null });
const writesTo = (table: string) => calls.filter((c) => c.table === table && (c.method === 'upsert' || c.method === 'update'));

describe('/api/tickets/[id]/messages', () => {
  beforeEach(() => {
    for (const k of Object.keys(results)) delete results[k];
    calls.length = 0;
    mockStatusAfterReply.mockReset().mockReturnValue(null);
    signedInAs('u1', 'user');
    // apiAuth's account-status check reads the caller's users row.
    queue('users', { data: { status: 'active' }, error: null });
  });

  it('rejects an unauthenticated caller with 401 before touching any ticket data', async () => {
    const res = await GET(request('GET', undefined, false), ctx());

    expect(res.status).toBe(401);
    expect(calls.filter((c) => c.table !== 'users')).toEqual([]);
  });

  it("answers 404 for another customer's ticket, same as for a missing one", async () => {
    queue('tickets', { data: { id: TICKET_ID, user_id: 'someone-else', status: 'resolved' }, error: null });

    const res = await GET(request('GET'), ctx());

    expect(res.status).toBe(404);
    expect(calls.some((c) => c.table === 'ticket_messages')).toBe(false);
  });

  it('returns the thread to the ticket owner', async () => {
    queue('tickets', ownTicket());
    queue('ticket_messages', { data: [SAVED], error: null });

    const res = await GET(request('GET'), ctx());

    expect(res.status).toBe(200);
    expect((await res.json()).data).toEqual([SAVED]);
  });

  it("lets staff read any customer's thread", async () => {
    signedInAs('agent-1', 'agent');
    queue('tickets', { data: { id: TICKET_ID, user_id: 'u1', status: 'resolved' }, error: null });
    queue('ticket_messages', { data: [], error: null });

    expect((await GET(request('GET'), ctx())).status).toBe(200);
  });

  it('rejects a blank message with 400 and writes nothing', async () => {
    queue('tickets', ownTicket());

    const res = await POST(request('POST', { body: '   ', clientMsgId: CLIENT_MSG_ID }), ctx());

    expect(res.status).toBe(400);
    expect(writesTo('ticket_messages')).toEqual([]);
  });

  it('rejects a missing or malformed clientMsgId with 400', async () => {
    queue('tickets', ownTicket());

    const res = await POST(request('POST', { body: 'hi', clientMsgId: 'abc' }), ctx());

    expect(res.status).toBe(400);
  });

  it('takes the author from the verified token, ignoring anything the client claims', async () => {
    queue('tickets', ownTicket());
    queue('ticket_messages', { data: null, error: null }, { data: SAVED, error: null });

    const res = await POST(
      request('POST', { body: '  Still broken  ', clientMsgId: CLIENT_MSG_ID, author_role: 'admin', author_id: 'x' }),
      ctx()
    );

    expect(res.status).toBe(201);
    const [upsert] = writesTo('ticket_messages');
    expect(upsert.args[0]).toEqual({
      ticket_id: TICKET_ID, author_id: 'u1', author_role: 'user', body: 'Still broken', client_msg_id: CLIENT_MSG_ID,
    });
    // A retried send must be a no-op, not a duplicate.
    expect(upsert.args[1]).toEqual({ onConflict: 'ticket_id,client_msg_id', ignoreDuplicates: true });
  });

  it("never passes a customer's markResolved through to the status rule", async () => {
    queue('tickets', ownTicket());
    queue('ticket_messages', { data: null, error: null }, { data: SAVED, error: null });

    await POST(request('POST', { body: 'hi', clientMsgId: CLIENT_MSG_ID, markResolved: true }), ctx());

    expect(mockStatusAfterReply).toHaveBeenCalledWith('resolved', 'user', false);
  });

  it('moves the ticket to whatever status the rule returns and reports it back', async () => {
    mockStatusAfterReply.mockReturnValue('reopened');
    queue('tickets', ownTicket('resolved'), { data: null, error: null });
    queue('ticket_messages', { data: null, error: null }, { data: SAVED, error: null });

    const res = await POST(request('POST', { body: 'hi', clientMsgId: CLIENT_MSG_ID }), ctx());

    expect((await res.json()).ticketStatus).toBe('reopened');
    expect(writesTo('tickets')[0].args[0]).toMatchObject({ status: 'reopened' });
  });

  it('leaves the ticket alone when the rule returns null', async () => {
    queue('tickets', ownTicket('processing'));
    queue('ticket_messages', { data: null, error: null }, { data: SAVED, error: null });

    const res = await POST(request('POST', { body: 'hi', clientMsgId: CLIENT_MSG_ID }), ctx());

    expect(res.status).toBe(201);
    expect(writesTo('tickets')).toEqual([]);
  });
});
