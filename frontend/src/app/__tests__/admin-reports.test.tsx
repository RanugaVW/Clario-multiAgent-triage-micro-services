import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import AdminReports from '../admin/reports/page';
import { useAuth } from '../../contexts/AuthContext';
import { aiPerformance, comparePeriods, parseDateRange, ticketAnalytics, type ReportTicket } from '../../lib/reports';

const push = vi.fn();
const router = { push }; // stable, like the real router
vi.mock('../../contexts/AuthContext', () => ({ useAuth: vi.fn() }));
vi.mock('next/navigation', () => ({ useRouter: () => router }));
vi.mock('../../lib/supabase', () => ({
  supabase: { auth: { getSession: vi.fn().mockResolvedValue({ data: { session: { access_token: 'admin-token' } } }), signOut: vi.fn() } },
}));

const t = (id: string, day: string, over: Partial<ReportTicket> = {}): ReportTicket => ({
  id, status: 'open', created_at: `${day}T10:00:00Z`, resolutions: [],
  ticket_classifications: [{ category: 'Refunds', priority: 'High', sentiment: 'Neutral' }], ...over,
});
const TICKETS: ReportTicket[] = [
  t('p1', '2026-09-02', { status: 'resolved', resolutions: [{ escalated: false, total_latency_ms: 4000 }], ticket_validations: [{ passed: true }], response_evaluations: [{ overall_score: 3 }] }),
  t('c1', '2026-09-09', { status: 'resolved', resolutions: [{ escalated: false, total_latency_ms: 2000 }], ticket_validations: [{ passed: true }], response_evaluations: [{ overall_score: 5 }] }),
  t('c2', '2026-09-10', { status: 'escalated', resolutions: [{ escalated: true, total_latency_ms: 12000, escalation_reasons: ['Mandatory Human Review'] }], ticket_validations: [{ passed: false, failure_type: 'policy' }] }),
  t('c3', '2026-09-11'),
];

/** The exact shape GET /api/reports returns, produced by the same functions the server uses. */
function payload(data: ReportTicket[] = TICKETS, from = '2026-09-08', to = '2026-09-14') {
  const r = parseDateRange(from, to);
  if (!r.ok) throw new Error('range');
  return JSON.parse(JSON.stringify({
    range: `${from} to ${to}`,
    analytics: ticketAnalytics(data, r.range),
    ai: aiPerformance(data, r.range),
    comparison: comparePeriods(data, r.range),
  }));
}

function mockApi(handler: (url: string) => { status?: number; body: unknown }) {
  global.fetch = vi.fn(async (url: RequestInfo | URL) => {
    const { status = 200, body } = handler(String(url));
    return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
  }) as unknown as typeof fetch;
}
const asRole = (role: string | null) =>
  vi.mocked(useAuth).mockReturnValue({
    user: role ? { id: 'u', email: 'a@b.c' } : null, role, loading: false, roleLoading: false,
  } as unknown as ReturnType<typeof useAuth>);

describe('Admin reports page - dashboard (FR-051 / FR-052)', () => {
  beforeEach(() => { vi.clearAllMocks(); asRole('admin'); });

  it('loads the last 30 days by default and shows the report, sending the token', async () => {
    mockApi(() => ({ body: payload() }));
    render(<AdminReports />);

    expect(await screen.findByLabelText('Tickets received: 3')).toBeInTheDocument();
    expect(screen.getByText(/Period:/)).toHaveTextContent('2026-09-08 to 2026-09-14');
    expect(screen.getByText(/Compared with 2026-09-01 to 2026-09-07/)).toBeInTheDocument();

    const [url, init] = vi.mocked(global.fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/^\/api\/reports\?from=\d{4}-\d{2}-\d{2}&to=\d{4}-\d{2}-\d{2}$/);
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer admin-token');
  });

  it('renders the whole dashboard: overview cards, charts and AI performance', async () => {
    mockApi(() => ({ body: payload() }));
    render(<AdminReports />);
    await screen.findByLabelText('Tickets received: 3');

    for (const name of ['Overview', 'AI performance', 'Ticket volume', 'Where tickets stand', 'Tickets by category', 'Tickets by priority', 'Customer sentiment', 'When tickets arrive', 'Processing time distribution', 'Judge scores']) {
      expect(screen.getByRole('region', { name })).toBeInTheDocument();
    }
    expect(screen.getByRole('meter', { name: 'Escalation rate' })).toBeInTheDocument();
    expect(screen.getByRole('meter', { name: 'Validation pass rate' })).toBeInTheDocument();
  });

  it('every chart can be read as a table, straight from the page', async () => {
    mockApi(() => ({ body: payload() }));
    const user = userEvent.setup();
    render(<AdminReports />);
    await screen.findByLabelText('Tickets received: 3');

    await user.click(within(screen.getByRole('region', { name: 'Tickets by category' })).getByRole('button', { name: 'table' }));
    expect(within(screen.getByRole('region', { name: 'Tickets by category' })).getByRole('row', { name: /Refunds\s+3/ })).toBeInTheDocument();
  });

  it('re-queries with the chosen dates when Apply is pressed', async () => {
    mockApi(() => ({ body: payload() }));
    const user = userEvent.setup();
    render(<AdminReports />);
    await screen.findByLabelText('Tickets received: 3');

    await user.clear(screen.getByLabelText('From'));
    await user.type(screen.getByLabelText('From'), '2026-01-01');
    await user.clear(screen.getByLabelText('To'));
    await user.type(screen.getByLabelText('To'), '2026-01-31');
    await user.click(screen.getByRole('button', { name: 'Apply' }));

    await waitFor(() => expect(vi.mocked(global.fetch).mock.calls.at(-1)?.[0]).toBe('/api/reports?from=2026-01-01&to=2026-01-31'));
  });

  it('offers 7 / 30 / 90 day presets and “All time” (which sends no bounds)', async () => {
    mockApi(() => ({ body: payload() }));
    const user = userEvent.setup();
    render(<AdminReports />);
    await screen.findByLabelText('Tickets received: 3');

    const presets = within(screen.getByRole('group', { name: 'Quick ranges' }));
    expect(['Last 7 days', 'Last 30 days', 'Last 90 days', 'All time'].every((n) => presets.getByRole('button', { name: n }))).toBe(true);
    await user.click(presets.getByRole('button', { name: 'Last 90 days' }));
    await waitFor(() => expect(String(vi.mocked(global.fetch).mock.calls.at(-1)?.[0])).toMatch(/^\/api\/reports\?from=\d{4}-\d{2}-\d{2}&to=/));
    await user.click(presets.getByRole('button', { name: 'All time' }));
    await waitFor(() => expect(vi.mocked(global.fetch).mock.calls.at(-1)?.[0]).toBe('/api/reports?'));
  });

  it('blocks a reversed range client-side without calling the API', async () => {
    mockApi(() => ({ body: payload() }));
    const user = userEvent.setup();
    render(<AdminReports />);
    await screen.findByLabelText('Tickets received: 3');
    const calls = vi.mocked(global.fetch).mock.calls.length;

    const from = screen.getByLabelText('From');
    await user.clear(from);
    await user.type(from, '2999-01-01');

    expect(screen.getByRole('alert')).toHaveTextContent(/must not be after/);
    expect(screen.getByRole('button', { name: 'Apply' })).toBeDisabled();
    expect(vi.mocked(global.fetch).mock.calls.length).toBe(calls);
  });

  it('keeps the previous render on screen (dimmed) while a new range loads - no flash, no layout jump', async () => {
    let release: () => void = () => {};
    let n = 0;
    global.fetch = vi.fn(async () => {
      if (++n > 1) await new Promise<void>((res) => { release = res; });
      return new Response(JSON.stringify(payload()), { status: 200, headers: { 'content-type': 'application/json' } });
    }) as unknown as typeof fetch;
    const user = userEvent.setup();
    render(<AdminReports />);
    await screen.findByLabelText('Tickets received: 3');

    await user.click(screen.getByRole('button', { name: 'Apply' }));

    const frame = screen.getByLabelText('Tickets received: 3').closest('[aria-busy]')!;
    expect(frame).toHaveAttribute('aria-busy', 'true');
    expect(frame).toHaveClass('opacity-60');
    release();
    await waitFor(() => expect(screen.getByLabelText('Tickets received: 3').closest('[aria-busy]')).toHaveAttribute('aria-busy', 'false'));
  });

  it('says so when the period has no tickets', async () => {
    mockApi(() => ({ body: payload([]) }));
    render(<AdminReports />);
    expect(await screen.findByText(/No tickets were received/)).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Overview' })).not.toBeInTheDocument();
  });

  it('shows the server error instead of stale or empty figures', async () => {
    mockApi(() => ({ status: 500, body: { error: 'boom' } }));
    render(<AdminReports />);
    expect(await screen.findByRole('alert')).toHaveTextContent('boom');
    expect(screen.queryByRole('region', { name: 'Overview' })).not.toBeInTheDocument();
  });

  it.each(['agent', 'user', null])('sends %s to /login without requesting a report', async (role) => {
    asRole(role);
    mockApi(() => ({ body: {} }));
    render(<AdminReports />);
    await waitFor(() => expect(push).toHaveBeenCalledWith('/login'));
    expect(global.fetch).not.toHaveBeenCalled();
  });
});

describe('Admin reports page - export (FR-053)', () => {
  let clicked: { href: string; download: string }[];
  beforeEach(() => {
    vi.clearAllMocks();
    asRole('admin');
    clicked = [];
    URL.createObjectURL = vi.fn(() => 'blob:mock');
    URL.revokeObjectURL = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      clicked.push({ href: this.href, download: this.download });
    });
  });

  function mockWithExport(exportResponse: () => Response) {
    global.fetch = vi.fn(async (url: RequestInfo | URL) =>
      String(url).startsWith('/api/reports/export')
        ? exportResponse()
        : new Response(JSON.stringify(payload()), { status: 200, headers: { 'content-type': 'application/json' } })
    ) as unknown as typeof fetch;
  }

  it('offers CSV, Excel and PDF', async () => {
    mockApi(() => ({ body: payload() }));
    render(<AdminReports />);
    const group = await screen.findByRole('group', { name: 'Export report' });
    expect(group).toHaveTextContent('CSV');
    expect(group).toHaveTextContent('Excel');
    expect(group).toHaveTextContent('PDF');
  });

  it('downloads the file for the period on screen, using the server file name and the token', async () => {
    mockWithExport(() => new Response('data', { status: 200, headers: { 'Content-Disposition': 'attachment; filename="clario-report-a_b.xlsx"' } }));
    const user = userEvent.setup();
    render(<AdminReports />);
    await screen.findByLabelText('Tickets received: 3');

    // Typing new dates without pressing Apply must not change what gets exported.
    await user.clear(screen.getByLabelText('From'));
    await user.type(screen.getByLabelText('From'), '2001-01-01');
    await user.click(screen.getByRole('button', { name: 'Excel' }));

    await waitFor(() => expect(clicked).toEqual([{ href: 'blob:mock', download: 'clario-report-a_b.xlsx' }]));
    const [url, init] = vi.mocked(global.fetch).mock.calls.at(-1) as [string, RequestInit];
    expect(url).toMatch(/^\/api\/reports\/export\?format=xlsx&from=\d{4}-\d{2}-\d{2}&to=/);
    expect(url).not.toContain('2001-01-01');
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer admin-token');
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock');
  });

  it('A1: shows the server error and downloads nothing when generation fails', async () => {
    mockWithExport(() => new Response(JSON.stringify({ error: 'The report could not be generated. Please try again.' }), { status: 500, headers: { 'content-type': 'application/json' } }));
    const user = userEvent.setup();
    render(<AdminReports />);
    await screen.findByLabelText('Tickets received: 3');

    await user.click(screen.getByRole('button', { name: 'PDF' }));

    expect(await screen.findByText(/Export failed: The report could not be generated/)).toBeInTheDocument();
    expect(clicked).toEqual([]);
    expect(screen.getByRole('button', { name: 'PDF' })).toBeEnabled(); // can retry
  });

  it('survives a non-JSON error body', async () => {
    mockWithExport(() => new Response('<html>Bad gateway</html>', { status: 502 }));
    const user = userEvent.setup();
    render(<AdminReports />);
    await screen.findByLabelText('Tickets received: 3');

    await user.click(screen.getByRole('button', { name: 'CSV' }));
    expect(await screen.findByText(/Export failed \(502\)/)).toBeInTheDocument();
  });
});
