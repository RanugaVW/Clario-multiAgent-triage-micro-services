import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import DashboardPage from '../dashboard/page';
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
});
