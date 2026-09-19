import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import ExcelJS from 'exceljs';

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

const req = (qs: string, auth = true) =>
  new Request(`http://localhost/api/reports/export${qs}`, { headers: auth ? { Authorization: 'Bearer t' } : {} });

function asRole(role: string) {
  mockGetUser.mockResolvedValue({ data: { user: { id: 'admin-1', email: 'a@example.com' } }, error: null });
  mockRpc.mockResolvedValue({ data: role, error: null });
}

function stubTickets(rows: unknown[], error?: string) {
  const b: Record<string, unknown> = {};
  b.select = () => b; b.order = () => b; b.gte = () => b; b.lte = () => b;
  b.range = async (from: number, to: number) => (error ? { data: null, error: { message: error } } : { data: rows.slice(from, to + 1), error: null });
  mockFrom.mockReturnValue(b);
}

const TICKETS = [
  { id: 't1', status: 'resolved', created_at: '2026-09-01T10:00:00Z',
    ticket_classifications: [{ category: 'Refunds', priority: 'High', sentiment: 'Neutral' }],
    resolutions: [{ escalated: false, total_latency_ms: 1200 }] },
];

describe('GET /api/reports/export (FR-053)', () => {
  let info: ReturnType<typeof vi.spyOn>;
  let error: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    mockFrom.mockReset(); mockGetUser.mockReset(); mockRpc.mockReset();
    info = vi.spyOn(console, 'info').mockImplementation(() => {});
    error = vi.spyOn(console, 'error').mockImplementation(() => {});
  });
  afterEach(() => { info.mockRestore(); error.mockRestore(); });

  const logged = (spy: ReturnType<typeof vi.spyOn>) => spy.mock.calls.map((c: unknown[]) => JSON.parse(String(c[0])));

  it('401 without a token', async () => {
    expect((await GET(req('?format=csv', false))).status).toBe(401);
    expect(dataQueries()).toEqual([]);
  });

  it.each(['user', 'agent'])('403 for %s, no data read, and the denial is logged', async (role) => {
    asRole(role);
    const res = await GET(req('?format=csv'));
    expect(res.status).toBe(403);
    expect(dataQueries()).toEqual([]);
    expect(logged(error)).toMatchObject([{ event: 'report.export', outcome: 'denied', role }]);
  });

  it.each([[''], ['?format=docx'], ['?format=__proto__']])('400 for unsupported format %j before reading data', async (qs) => {
    asRole('admin');
    const res = await GET(req(qs));
    expect(res.status).toBe(400);
    expect((await res.json()).error).toMatch(/csv, xlsx, pdf/);
    expect(dataQueries()).toEqual([]);
  });

  it('400 for a bad date range', async () => {
    asRole('admin');
    expect((await GET(req('?format=csv&from=nope'))).status).toBe(400);
  });

  it('streams a CSV attachment with safe headers and the report contents', async () => {
    asRole('admin');
    stubTickets(TICKETS);
    const res = await GET(req('?format=csv&from=2026-09-01&to=2026-09-30'));
    const text = await res.text();

    expect(res.status).toBe(200);
    expect(res.headers.get('Content-Type')).toBe('text/csv; charset=utf-8');
    expect(res.headers.get('Content-Disposition')).toBe('attachment; filename="clario-report-2026-09-01_2026-09-30.csv"');
    expect(res.headers.get('Cache-Control')).toBe('no-store');
    expect(text).toContain('Tickets received,1');
    expect(text).toContain('Refunds,1');
  });

  it('produces a readable Excel workbook', async () => {
    asRole('admin');
    stubTickets(TICKETS);
    const res = await GET(req('?format=xlsx'));
    const wb = new ExcelJS.Workbook();
    await wb.xlsx.load(await res.arrayBuffer());

    expect(res.headers.get('Content-Type')).toContain('spreadsheetml.sheet');
    expect(res.headers.get('Content-Disposition')).toContain('clario-report-start_today.xlsx');
    expect(wb.getWorksheet('Ticket summary')!.getRow(3).values).toEqual([undefined, 'Tickets received', 1]);
  });

  it('produces a PDF', async () => {
    asRole('admin');
    stubTickets(TICKETS);
    const res = await GET(req('?format=pdf'));
    expect(res.headers.get('Content-Type')).toBe('application/pdf');
    expect(new TextDecoder().decode((await res.arrayBuffer()).slice(0, 5))).toBe('%PDF-');
  });

  it('logs every successful generation with who, what, size - and no report contents', async () => {
    asRole('admin');
    stubTickets(TICKETS);
    await (await GET(req('?format=csv&from=2026-09-01&to=2026-09-30'))).arrayBuffer();

    const [line] = logged(info);
    expect(line).toMatchObject({ event: 'report.export', outcome: 'success', userId: 'admin-1', format: 'csv', period: '2026-09-01 to 2026-09-30', tickets: 1 });
    expect(line.bytes).toBeGreaterThan(0);
    expect(JSON.stringify(line)).not.toContain('Refunds');
  });

  it('A1: a data failure returns a friendly error (no internals) and is logged as a failure', async () => {
    asRole('admin');
    stubTickets([], 'relation "secret_table" exploded');
    const res = await GET(req('?format=pdf'));
    const body = await res.json();

    expect(res.status).toBe(500);
    expect(body.error).toBe('The report could not be generated. Please try again.');
    expect(JSON.stringify(body)).not.toContain('secret_table');
    expect(logged(error)).toMatchObject([{ event: 'report.export', outcome: 'failure', format: 'pdf', error: expect.stringContaining('exploded') }]);
  });
});
