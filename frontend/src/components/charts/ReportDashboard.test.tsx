import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect } from 'vitest';
import { ReportDashboard, partialWeekNote } from './ReportDashboard';
import { aiPerformance, comparePeriods, parseDateRange, ticketAnalytics, volumeSeries, type ReportTicket } from '../../lib/reports';

const mk = (id: string, day: string, hour: number, over: Partial<ReportTicket> & { cat?: string; pri?: string; sent?: string } = {}): ReportTicket => {
  const { cat, pri, sent, ...rest } = over;
  return {
    id,
    status: 'open',
    created_at: `${day}T${String(hour).padStart(2, '0')}:00:00Z`,
    ticket_classifications: [{ category: cat ?? 'Refunds', priority: pri ?? 'High', sentiment: sent ?? 'Neutral' }],
    resolutions: [],
    ...rest,
  };
};

const tickets: ReportTicket[] = [
  // previous week (2026-09-01..07)
  mk('p1', '2026-09-02', 9, { status: 'resolved', resolutions: [{ escalated: false, total_latency_ms: 4000 }], ticket_validations: [{ passed: true }], response_evaluations: [{ overall_score: 3 }] }),
  // current week (2026-09-08..14)
  mk('c1', '2026-09-09', 9, { cat: 'Billing & Invoicing, Refunds', pri: 'Critical', sent: 'Frustrated', status: 'resolved', resolutions: [{ escalated: false, total_latency_ms: 2000, total_llm_calls: 4, total_reflection_count: 1 }], ticket_validations: [{ passed: true }], response_evaluations: [{ overall_score: 5 }] }),
  mk('c2', '2026-09-10', 10, { cat: 'Authentication', pri: 'Low', sent: 'Negative', status: 'escalated', resolutions: [{ escalated: true, total_latency_ms: 12000, escalation_reasons: ['Mandatory Human Review'] }], ticket_validations: [{ passed: false, failure_type: 'policy' }] }),
  mk('c3', '2026-09-11', 10, { cat: 'Refunds', pri: 'Medium' }),
];

function fixture(from = '2026-09-08', to = '2026-09-14', data = tickets) {
  const r = parseDateRange(from, to);
  if (!r.ok) throw new Error('range');
  return { analytics: ticketAnalytics(data, r.range), ai: aiPerformance(data, r.range), comparison: comparePeriods(data, r.range) };
}

const card = (name: string | RegExp) => screen.getByRole('region', { name });

describe('ReportDashboard', () => {
  it('has an Overview and an AI performance section, each a labelled region', () => {
    render(<ReportDashboard {...fixture()} />);
    expect(screen.getByRole('region', { name: 'Overview' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'AI performance' })).toBeInTheDocument();
  });

  it('leads with exactly one hero figure and compares it with the previous period', () => {
    const { container } = render(<ReportDashboard {...fixture()} />);
    expect(container.querySelectorAll('.text-5xl')).toHaveLength(1);
    expect(screen.getByLabelText('Tickets received: 3')).toHaveClass('text-5xl');
    // 3 this week vs 1 the week before: +200%, worded with an arrow and the comparison window.
    expect(screen.getByText('▲ 200%')).toBeInTheDocument();
    expect(screen.getAllByText('vs 2026-09-01 to 2026-09-07').length).toBeGreaterThan(0);
  });

  it('for an open-ended range there is no comparison, and the tile says how to get one', () => {
    const r = ticketAnalytics(tickets, { from: null, to: null });
    render(<ReportDashboard analytics={r} ai={aiPerformance(tickets, { from: null, to: null })} comparison={null} />);
    expect(screen.getByText('Pick a date range to compare with the previous period')).toBeInTheDocument();
    expect(screen.queryByText(/vs 20/)).not.toBeInTheDocument();
  });

  it('shows the lifecycle split with a takeaway about the human-review backlog', () => {
    render(<ReportDashboard {...fixture()} />);
    const c = card('Where tickets stand');
    expect(within(c).getByText('Resolved')).toBeInTheDocument();
    expect(within(c).getByText('Awaiting human review')).toBeInTheDocument();
    expect(within(c).getByText('1 ticket is waiting for a human reviewer.')).toBeInTheDocument();
  });

  describe('every chart has a table twin that matches the numbers', () => {
    const open = async (name: string | RegExp) => {
      await userEvent.setup().click(within(card(name)).getByRole('button', { name: 'table' }));
      return within(card(name)).getByRole('table');
    };

    it('category: a multi-category ticket is counted under each category', async () => {
      render(<ReportDashboard {...fixture()} />);
      const t = await open('Tickets by category');
      expect(within(t).getByRole('row', { name: /Refunds\s+2/ })).toBeInTheDocument();
      expect(within(t).getByRole('row', { name: /Billing & Invoicing\s+1/ })).toBeInTheDocument();
      expect(within(t).getByRole('row', { name: /Authentication\s+1/ })).toBeInTheDocument();
    });

    it('priority: most severe first, every level present, zero included', async () => {
      render(<ReportDashboard {...fixture()} />);
      const rows = within(await open('Tickets by priority')).getAllByRole('row').slice(1).map((r) => r.textContent);
      expect(rows).toEqual(['Critical1', 'High0', 'Medium1', 'Low1']);
    });

    it('sentiment: most negative first', async () => {
      render(<ReportDashboard {...fixture()} />);
      const rows = within(await open('Customer sentiment')).getAllByRole('row').slice(1).map((r) => r.textContent);
      expect(rows).toEqual(['Frustrated1', 'Negative1', 'Neutral1']);
    });

    it('arrivals: a 7-row weekday x 24-hour table whose cells add up to the ticket count', async () => {
      render(<ReportDashboard {...fixture()} />);
      const t = await open('When tickets arrive');
      const body = within(t).getAllByRole('row').slice(1);
      expect(body).toHaveLength(7);
      expect(within(t).getAllByRole('columnheader')).toHaveLength(25);
      const total = body.flatMap((r) => within(r).getAllByRole('cell').slice(1).map((c) => Number(c.textContent))).reduce((a, b) => a + b, 0);
      expect(total).toBe(3);
    });

    it('processing time distribution and judge scores agree with the report', async () => {
      render(<ReportDashboard {...fixture()} />);
      const latency = within(await open('Processing time distribution')).getAllByRole('row').slice(1).map((r) => r.textContent);
      expect(latency).toEqual(['<1 s0', '1–2 s0', '2–5 s1', '5–10 s0', '10–30 s1', '30 s+0']);
      const scores = within(await open('Judge scores')).getAllByRole('row').slice(1).map((r) => r.textContent);
      // Only the current week's single 5-score counts (the 3 belongs to the previous week). Rows read score then count.
      expect(scores).toEqual(['10', '20', '30', '40', '51']);
    });

    it('volume: one row per day with the 7-day average column', async () => {
      render(<ReportDashboard {...fixture()} />);
      const t = await open('Ticket volume');
      expect(within(t).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Date', 'Received', '7-day average']);
      expect(within(t).getAllByRole('row').slice(1)).toHaveLength(3); // 9th, 10th, 11th (days with tickets, zero-filled between)
    });
  });

  describe('AI performance', () => {
    it('reports the median (nearest rank) with its spread, and a faster time than last period as good news', () => {
      render(<ReportDashboard {...fixture()} />);
      // Latencies this week: 2 s and 12 s -> median 2 s. Previous week: 4 s -> 2 s is 50% faster.
      expect(screen.getByLabelText('Median processing time: 2 s')).toBeInTheDocument();
      expect(screen.getByText('95th percentile 12 s · 2 measured')).toBeInTheDocument();
      const delta = screen.getByText('▼ 50%', { selector: '[data-tone]' });
      expect(delta).toHaveAttribute('data-tone', 'good'); // down is good for a duration
    });

    it('meters carry value and severity in words: a 50% escalation rate is critical, a 50% pass rate too', () => {
      render(<ReportDashboard {...fixture()} />);
      expect(screen.getByRole('meter', { name: 'Escalation rate' })).toHaveAttribute('aria-valuenow', '50');
      expect(screen.getByRole('meter', { name: 'Escalation rate' })).toHaveAttribute('aria-valuetext', '50%, critical');
      expect(screen.getByRole('meter', { name: 'Validation pass rate' })).toHaveAttribute('aria-valuetext', '50%, critical');
    });

    it('explains the pipeline processed nothing instead of drawing empty charts', () => {
      const f = fixture('2026-09-15', '2026-09-21');
      render(<ReportDashboard {...f} analytics={{ ...f.analytics, total: 3 }} />);
      expect(screen.getByText('The AI pipeline has not processed any tickets in this period.')).toBeInTheDocument();
      expect(screen.queryByRole('meter')).not.toBeInTheDocument();
    });

    it('empty sub-charts say why rather than showing a blank plot', () => {
      const none = [mk('x', '2026-09-09', 9, { status: 'resolved', resolutions: [{ escalated: false }] })]; // processed, but no latency, no escalations, no validations
      render(<ReportDashboard {...fixture('2026-09-08', '2026-09-14', none)} />);
      expect(screen.getByText('No processing times were recorded in this period.')).toBeInTheDocument();
      expect(screen.getByText('No responses were scored in this period.')).toBeInTheDocument();
      expect(screen.getByText('No tickets were escalated in this period.')).toBeInTheDocument();
      expect(screen.getByText('No validations failed in this period.')).toBeInTheDocument();
    });
  });

  it('never renders NaN or "undefined" anywhere, even with sparse data', () => {
    const sparse = [mk('s', '2026-09-09', 9, { cat: '', pri: '', sent: '' })];
    const { container } = render(<ReportDashboard {...fixture('2026-09-08', '2026-09-14', sparse)} />);
    expect(container.textContent).not.toMatch(/NaN|undefined|null/);
  });
});

describe('partialWeekNote', () => {
  const daily = (n: number) => Array.from({ length: n }, (_, i) => ({ date: new Date(Date.UTC(2026, 4, 1 + i)).toISOString().slice(0, 10), count: 1 }));
  it('explains a short final week so the dip is not read as a collapse', () => {
    expect(partialWeekNote(volumeSeries(daily(101)))).toBe('The final point covers only 3 of 7 days, so it is lower by construction.');
  });
  it('says nothing when every block is complete, or when the series is daily', () => {
    expect(partialWeekNote(volumeSeries(daily(98)))).toBe('');
    expect(partialWeekNote(volumeSeries(daily(30)))).toBe('');
    expect(partialWeekNote({ granularity: 'week', points: [] })).toBe('');
  });
});
