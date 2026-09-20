import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockFrom = vi.fn();
// The auth helper also reads the caller's own `users` row (account status, FR-043); "never touched data" means no other table.
const dataQueries = () => mockFrom.mock.calls.filter(([table]: unknown[]) => table !== 'users');
const mockGetUser = vi.fn();
const mockRpc = vi.fn();

vi.mock('@supabase/supabase-js', () => ({
  createClient: vi.fn(() => ({ from: mockFrom, auth: { getUser: mockGetUser }, rpc: mockRpc })),
}));

process.env.NEXT_PUBLIC_SUPABASE_URL = 'https://mock.supabase.co';
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'mock-anon-key';
process.env.SUPABASE_SERVICE_ROLE_KEY = 'mock-service-key';

import { GET } from './route';

const req = (qs = '', auth = true) =>
  new Request(`http://localhost/api/reports${qs}`, { headers: auth ? { Authorization: 'Bearer t' } : {} });

function asRole(role: string) {
  mockGetUser.mockResolvedValue({ data: { user: { id: 'u1', email: 'u@example.com' } }, error: null });
  mockRpc.mockResolvedValue({ data: role, error: null });
}

// Fake of the chained query builder that records the filters applied and serves rows page by page.
function stubTickets(rows: unknown[], opts: { error?: string } = {}) {
  const filters: Record<string, string> = {};
  const ranges: [number, number][] = [];
  const selects: string[] = [];
  const builder: Record<string, unknown> = {};
  builder.select = (cols: string) => (selects.push(cols), builder);
  builder.order = () => builder;
  builder.gte = (_c: string, v: string) => ((filters.gte = v), builder);
  builder.lte = (_c: string, v: string) => ((filters.lte = v), builder);
  builder.range = async (from: number, to: number) => {
    ranges.push([from, to]);
    return opts.error ? { data: null, error: { message: opts.error } } : { data: rows.slice(from, to + 1), error: null };
  };
  mockFrom.mockImplementation((table: string) => {
    if (table !== 'tickets') throw new Error(`unexpected table ${table}`);
    return builder;
  });
  return { filters, ranges, selects };
}

const ticket = (i: number) => ({
  id: `t${i}`, status: 'open', created_at: '2026-09-01T10:00:00Z', ticket_classifications: [], resolutions: [],
});

describe('GET /api/reports (FR-051)', () => {
  beforeEach(() => { mockFrom.mockReset(); mockGetUser.mockReset(); mockRpc.mockReset(); });

  it('401 without a token, before touching data', async () => {
    const res = await GET(req('', false));
    expect(res.status).toBe(401);
    expect(dataQueries()).toEqual([]);
  });

  it.each(['user', 'agent'])('403 for role %s - reports are administrator-only', async (role) => {
    asRole(role);
    const res = await GET(req());
    expect(res.status).toBe(403);
    expect(dataQueries()).toEqual([]);
  });

  it('400 for a bad date, before touching data', async () => {
    asRole('admin');
    const res = await GET(req('?from=yesterday'));
    expect(res.status).toBe(400);
    expect((await res.json()).error).toMatch(/from/);
    expect(dataQueries()).toEqual([]);
  });

  it('returns analytics and pushes the date range down to the database query', async () => {
    asRole('admin');
    const { filters } = stubTickets([ticket(1), ticket(2)]);
    const res = await GET(req('?from=2026-09-01&to=2026-09-30'));
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.range).toBe('2026-09-01 to 2026-09-30');
    expect(body.analytics.total).toBe(2);
    expect(filters).toEqual({ gte: '2026-09-01T00:00:00.000Z', lte: '2026-09-30T23:59:59.999Z' });
  });

  it('asks the database for every relation the reports read - a missing one would silently zero a report', async () => {
    asRole('admin');
    const { selects } = stubTickets([ticket(1)]);
    await GET(req());
    for (const relation of ['ticket_classifications', 'resolutions', 'ticket_validations', 'response_evaluations']) {
      expect(selects[0]).toContain(relation);
    }
  });

  it('also returns AI performance for the same cohort (FR-052)', async () => {
    asRole('admin');
    stubTickets([{
      id: 't1', status: 'resolved', created_at: '2026-09-01T10:00:00Z', ticket_classifications: [],
      resolutions: [{ escalated: true, total_latency_ms: 1500, escalation_reasons: ['Mandatory Human Review'] }],
      ticket_validations: [{ passed: false, failure_type: 'policy', judge_ran: true }],
      response_evaluations: [{ overall_score: 3 }],
    }]);
    const body = await (await GET(req())).json();

    expect(body.ai.ticketsProcessed).toBe(1);
    expect(body.ai.processingTime.medianMs).toBe(1500);
    expect(body.ai.escalation.reasons).toEqual([{ label: 'Mandatory Human Review', count: 1 }]);
    expect(body.ai.validation.failed).toBe(1);
    expect(body.ai.judgeScores.meanOverall).toBe(3);
  });

  it('pages past the 1000-row PostgREST limit instead of silently truncating', async () => {
    asRole('admin');
    const { ranges } = stubTickets(Array.from({ length: 2500 }, (_, i) => ticket(i)));
    const res = await GET(req());

    expect((await res.json()).analytics.total).toBe(2500);
    expect(ranges).toEqual([[0, 999], [1000, 1999], [2000, 2999]]);
  });

  it('fetches one more page when the total is an exact multiple of the page size', async () => {
    asRole('admin');
    const { ranges } = stubTickets(Array.from({ length: 1000 }, (_, i) => ticket(i)));
    const res = await GET(req());

    expect((await res.json()).analytics.total).toBe(1000);
    expect(ranges).toEqual([[0, 999], [1000, 1999]]);
  });

  it('500 with the database message when a page fails - never a partial report', async () => {
    asRole('admin');
    stubTickets([], { error: 'boom' });
    const res = await GET(req());

    expect(res.status).toBe(500);
    expect((await res.json()).error).toBe('boom');
  });
});
