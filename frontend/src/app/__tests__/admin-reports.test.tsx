import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import AdminReports from '../admin/reports/page';
import { useAuth } from '../../contexts/AuthContext';

const push = vi.fn();
vi.mock('../../contexts/AuthContext', () => ({ useAuth: vi.fn() }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }));
vi.mock('../../lib/supabase', () => ({
  supabase: { auth: { getSession: vi.fn().mockResolvedValue({ data: { session: { access_token: 'admin-token' } } }) } },
}));

const analytics = (over: Record<string, unknown> = {}) => ({
  range: { from: null, to: null },
  total: 10, resolved: 4, awaitingHuman: 3, inProgress: 3, resolutionRate: 0.4,
  byStatus: [{ label: 'open', count: 6 }, { label: 'resolved', count: 4 }],
  byCategory: [{ label: 'Refunds', count: 7 }, { label: 'Authentication', count: 3 }],
  byPriority: [{ label: 'High', count: 10 }],
  bySentiment: [{ label: 'Neutral', count: 10 }],
  dailyVolume: [{ date: '2026-09-01', count: 6 }, { date: '2026-09-02', count: 4 }],
  ...over,
});

const ai = (over: Record<string, unknown> = {}) => ({
  range: { from: null, to: null },
  ticketsProcessed: 8,
  processingTime: { samples: 8, meanMs: 2400, medianMs: 2000, p95Ms: 5100, maxMs: 6000 },
  avgLlmCalls: 5.5, avgReflections: 1.25,
  escalation: { escalated: 2, rate: 0.25, reasons: [{ label: 'Mandatory Human Review', count: 2 }] },
  validation: { validated: 10, passed: 7, failed: 3, passRate: 0.7, failureTypes: [{ label: 'policy', count: 3 }], judged: 6 },
  judgeScores: { evaluated: 6, meanOverall: 4.25, distribution: [] },
  ...over,
});

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

describe('Admin reports page (FR-051)', () => {
  beforeEach(() => { vi.clearAllMocks(); asRole('admin'); });

  it('loads the last 30 days by default and shows real figures with the token attached', async () => {
    mockApi(() => ({ body: { range: '2026-08-21 to 2026-09-19', analytics: analytics(), ai: ai() } }));
    render(<AdminReports />);

    expect(await screen.findByText('Tickets received')).toBeInTheDocument();
    expect(screen.getByText('Tickets received').nextElementSibling).toHaveTextContent('10');
    expect(screen.getByText('40% of received')).toBeInTheDocument();
    expect(screen.getByText('2026-08-21 to 2026-09-19')).toBeInTheDocument();

    const [url, init] = vi.mocked(global.fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/^\/api\/reports\?from=\d{4}-\d{2}-\d{2}&to=\d{4}-\d{2}-\d{2}$/);
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer admin-token');
  });

  it('renders the breakdowns and the daily table', async () => {
    mockApi(() => ({ body: { range: 'All time', analytics: analytics(), ai: ai() } }));
    render(<AdminReports />);

    const cat = await screen.findByRole('region', { name: 'By category' });
    expect(cat).toHaveTextContent('Refunds');
    expect(cat).toHaveTextContent('7');
    expect(screen.getByRole('table')).toHaveTextContent('2026-09-02');
  });

  it('re-queries with the chosen dates when Apply is pressed', async () => {
    mockApi(() => ({ body: { range: 'x', analytics: analytics(), ai: ai() } }));
    const user = userEvent.setup();
    render(<AdminReports />);
    await screen.findByText('Tickets received');

    await user.clear(screen.getByLabelText('From'));
    await user.type(screen.getByLabelText('From'), '2026-01-01');
    await user.clear(screen.getByLabelText('To'));
    await user.type(screen.getByLabelText('To'), '2026-01-31');
    await user.click(screen.getByRole('button', { name: 'Apply' }));

    await waitFor(() => expect(vi.mocked(global.fetch).mock.calls.at(-1)?.[0]).toBe('/api/reports?from=2026-01-01&to=2026-01-31'));
  });

  it('“All time” sends no date bounds', async () => {
    mockApi(() => ({ body: { range: 'All time', analytics: analytics(), ai: ai() } }));
    const user = userEvent.setup();
    render(<AdminReports />);
    await screen.findByText('Tickets received');

    await user.click(screen.getByRole('button', { name: 'All time' }));
    await waitFor(() => expect(vi.mocked(global.fetch).mock.calls.at(-1)?.[0]).toBe('/api/reports?'));
  });

  it('blocks a reversed range client-side without calling the API', async () => {
    mockApi(() => ({ body: { range: 'x', analytics: analytics(), ai: ai() } }));
    const user = userEvent.setup();
    render(<AdminReports />);
    await screen.findByText('Tickets received');
    const calls = vi.mocked(global.fetch).mock.calls.length;

    const from = screen.getByLabelText('From');
    await user.clear(from);
    await user.type(from, '2999-01-01');

    expect(screen.getByRole('alert')).toHaveTextContent(/must not be after/);
    expect(screen.getByRole('button', { name: 'Apply' })).toBeDisabled();
    expect(vi.mocked(global.fetch).mock.calls.length).toBe(calls);
  });

  it('shows AI performance: processing time, escalation and validation outcomes (FR-052)', async () => {
    mockApi(() => ({ body: { range: 'All time', analytics: analytics(), ai: ai() } }));
    render(<AdminReports />);

    const median = (await screen.findByText('Median processing time')).parentElement!;
    expect(median).toHaveTextContent('2.0 s');
    expect(median).toHaveTextContent('p95 5.1 s');
    expect(screen.getByText('Escalation rate').parentElement).toHaveTextContent('25%');
    expect(screen.getByText('Escalation rate').parentElement).toHaveTextContent('2 of 8 processed');
    expect(screen.getByText('Validation pass rate').parentElement).toHaveTextContent('70%');
    expect(screen.getByText('Mean judge score').parentElement).toHaveTextContent('4.25 / 5');
    expect(screen.getByRole('region', { name: 'Escalation reasons' })).toHaveTextContent('Mandatory Human Review');
    expect(screen.getByRole('region', { name: 'Validation failures' })).toHaveTextContent('policy');
  });

  it('shows dashes rather than zeros or NaN when nothing was measured', async () => {
    mockApi(() => ({ body: { range: 'x', analytics: analytics(), ai: ai({
      processingTime: null, avgLlmCalls: null, avgReflections: null,
      escalation: { escalated: 0, rate: null, reasons: [] },
      validation: { validated: 0, passed: 0, failed: 0, passRate: null, failureTypes: [], judged: 0 },
      judgeScores: { evaluated: 0, meanOverall: null, distribution: [] },
    }) } }));
    render(<AdminReports />);

    expect((await screen.findByText('Median processing time')).parentElement).toHaveTextContent('—');
    expect(screen.getByText('Validation pass rate').parentElement).toHaveTextContent('—');
    expect(document.body.textContent).not.toMatch(/NaN/);
  });

  it('explains when the pipeline processed nothing in the period', async () => {
    mockApi(() => ({ body: { range: 'x', analytics: analytics(), ai: ai({ ticketsProcessed: 0 }) } }));
    render(<AdminReports />);
    expect(await screen.findByText(/has not processed any tickets/)).toBeInTheDocument();
  });

  describe('export (FR-053)', () => {
    let clicked: { href: string; download: string }[];
    beforeEach(() => {
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
          : new Response(JSON.stringify({ range: 'x', analytics: analytics(), ai: ai() }), { status: 200, headers: { 'content-type': 'application/json' } })
      ) as unknown as typeof fetch;
    }

    it('offers CSV, Excel and PDF', async () => {
      mockApi(() => ({ body: { range: 'x', analytics: analytics(), ai: ai() } }));
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
      await screen.findByText('Tickets received');

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
      await screen.findByText('Tickets received');

      await user.click(screen.getByRole('button', { name: 'PDF' }));

      expect(await screen.findByText(/Export failed: The report could not be generated/)).toBeInTheDocument();
      expect(clicked).toEqual([]);
      expect(screen.getByRole('button', { name: 'PDF' })).toBeEnabled(); // can retry
    });

    it('survives a non-JSON error body', async () => {
      mockWithExport(() => new Response('<html>Bad gateway</html>', { status: 502 }));
      const user = userEvent.setup();
      render(<AdminReports />);
      await screen.findByText('Tickets received');

      await user.click(screen.getByRole('button', { name: 'CSV' }));
      expect(await screen.findByText(/Export failed \(502\)/)).toBeInTheDocument();
    });
  });

  it('says so when the period has no tickets', async () => {
    mockApi(() => ({ body: { range: 'x', analytics: analytics({ total: 0, resolutionRate: null, dailyVolume: [], byCategory: [] }), ai: ai() } }));
    render(<AdminReports />);
    expect(await screen.findByText(/No tickets were received/)).toBeInTheDocument();
  });

  it('shows the server error instead of stale or empty figures', async () => {
    mockApi(() => ({ status: 500, body: { error: 'boom' } }));
    render(<AdminReports />);
    expect(await screen.findByRole('alert')).toHaveTextContent('boom');
    expect(screen.queryByText('Tickets received')).not.toBeInTheDocument();
  });

  it.each(['agent', 'user', null])('sends %s to /login without requesting a report', async (role) => {
    asRole(role);
    mockApi(() => ({ body: {} }));
    render(<AdminReports />);
    await waitFor(() => expect(push).toHaveBeenCalledWith('/login'));
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
