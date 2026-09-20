import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import DashboardPage, { UserTicketRow } from '../dashboard/page';
import { useAuth } from '../../contexts/AuthContext';

vi.mock('../../contexts/AuthContext', () => ({ useAuth: vi.fn() }));
const router = { push: vi.fn(), refresh: vi.fn() };
vi.mock('next/navigation', () => ({ useRouter: () => router }));
vi.mock('../../lib/supabase', () => ({
  supabase: {
    auth: { getSession: vi.fn().mockResolvedValue({ data: { session: { access_token: 'tok' } } }), signOut: vi.fn() },
    storage: { from: vi.fn() },
  },
}));

describe('customer dashboard - accessible structure', () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue({
      user: { id: 'u1', email: 'cust@example.com' }, role: 'user', loading: false, roleLoading: false,
    } as unknown as ReturnType<typeof useAuth>);
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ data: [] }) }) as unknown as typeof fetch;
  });

  it('binds every form label to its control', () => {
    render(<DashboardPage />);
    expect(screen.getByLabelText('Describe the issue')).toBeInstanceOf(HTMLTextAreaElement);
    expect(screen.getByLabelText('Attach a screenshot (optional)')).toHaveAttribute('type', 'file');
  });

  it('shows the submit error as an alert', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 400, json: async () => ({ error: 'Nope' }) }) as unknown as typeof fetch;
    const user = userEvent.setup();
    render(<DashboardPage />);
    await user.type(screen.getByLabelText('Describe the issue'), 'help');
    await user.click(screen.getByRole('button', { name: /submit ticket/i }));
    const alert = await screen.findByText(/Nope/);
    expect(alert.closest('[role="alert"]')).not.toBeNull();
  });

  it('announces the success dialog by its title', async () => {
    global.fetch = vi.fn().mockImplementation(async (url: string) =>
      String(url).includes('/api/v1/tickets')
        ? { ok: true, status: 200, json: async () => ({ id: 'abc-123' }) }
        : { ok: true, json: async () => ({ data: [] }) }
    ) as unknown as typeof fetch;
    const user = userEvent.setup();
    render(<DashboardPage />);
    await user.type(screen.getByLabelText('Describe the issue'), 'help');
    await user.click(screen.getByRole('button', { name: /submit ticket/i }));
    const dialog = await screen.findByRole('dialog', { name: 'Ticket submitted successfully!' });
    await waitFor(() => expect(dialog).toHaveTextContent('abc-123'));
  });

  it('closes the success dialog and refetches tickets from its View my tickets button', async () => {
    global.fetch = vi.fn().mockImplementation(async (url: string) =>
      String(url).includes('/api/v1/tickets')
        ? { ok: true, status: 200, json: async () => ({ id: 'abc-123' }) }
        : { ok: true, json: async () => ({ data: [] }) }
    ) as unknown as typeof fetch;
    const user = userEvent.setup();
    render(<DashboardPage />);
    await user.type(screen.getByLabelText('Describe the issue'), 'help');
    await user.click(screen.getByRole('button', { name: /submit ticket/i }));
    const dialog = await screen.findByRole('dialog', { name: 'Ticket submitted successfully!' });
    // Let the submit-triggered history fetch settle, then start from a clean baseline
    // so only a fetch caused by the click can satisfy the assertion below.
    await waitFor(() => expect(vi.mocked(global.fetch).mock.calls.some(
      ([u]) => String(u).startsWith('/api/user_tickets?userId=u1')
    )).toBe(true));
    await new Promise((r) => setTimeout(r, 50));
    vi.mocked(global.fetch).mockClear();
    await user.click(within(dialog).getByRole('button', { name: /view my tickets/i }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    await waitFor(() => expect(vi.mocked(global.fetch).mock.calls.some(
      ([u]) => String(u).startsWith('/api/user_tickets?userId=u1')
    )).toBe(true));
  });
});

const ticket = {
  id: 'abcd1234-0000-0000-0000-000000000000',
  raw_text: 'My invoice is wrong',
  created_at: '2026-01-02T10:00:00Z',
  status: 'processing',
  subject: 'Invoice',
  resolutions: [],
};

describe('UserTicketRow - accessible structure', () => {
  it('expands through a real button that reports aria-expanded', async () => {
    const user = userEvent.setup();
    render(<UserTicketRow ticket={ticket} onDelete={vi.fn()} userId="u1" />);
    const toggle = screen.getByRole('button', { name: /My invoice is wrong/ });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await user.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('Ticket details')).toBeInTheDocument();
    await user.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
  });

  it('keeps Delete outside the expand button and does not toggle the row', async () => {
    const onDelete = vi.fn();
    const user = userEvent.setup();
    render(<UserTicketRow ticket={ticket} onDelete={onDelete} userId="u1" />);
    const toggle = screen.getByRole('button', { name: /My invoice is wrong/ });
    const del = screen.getByRole('button', { name: /delete/i });
    expect(toggle.contains(del)).toBe(false);
    await user.click(del);
    expect(onDelete).toHaveBeenCalledWith(ticket.id);
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
  });

  it('shows the in-progress state as a neutral badge', () => {
    render(<UserTicketRow ticket={ticket} onDelete={vi.fn()} userId="u1" />);
    expect(screen.getByText('In progress')).toBeInTheDocument();
  });
});
