import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import AdminDashboard from '../admin/page';
import { useAuth } from '../../contexts/AuthContext';

const push = vi.fn();
const mockSignOut = vi.hoisted(() => vi.fn());
vi.mock('../../contexts/AuthContext', () => ({ useAuth: vi.fn() }));
const router = { push }; // stable, like the real router
vi.mock('next/navigation', () => ({ useRouter: () => router }));
vi.mock('../../lib/supabase', () => ({
  supabase: {
    auth: { getSession: vi.fn().mockResolvedValue({ data: { session: { access_token: 'tok' } } }), signOut: mockSignOut },
    from: vi.fn(),
  },
}));

const asRole = (role: string | null) =>
  vi.mocked(useAuth).mockReturnValue({
    user: role ? { id: 'a1', email: 'admin@example.com' } : null, role, loading: false, roleLoading: false,
  } as unknown as ReturnType<typeof useAuth>);

// UR-001: the admin console uses the same shell as Reports and Users, with its five tabs as the shell's nav.
describe('Admin console inside the shared navigation shell', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    asRole('admin');
    global.fetch = vi.fn(async () =>
      new Response(JSON.stringify({ data: [] }), { status: 200, headers: { 'content-type': 'application/json' } })
    ) as unknown as typeof fetch;
  });

  it('shows the five console tabs plus Reports and Users in one navigation', async () => {
    render(<AdminDashboard />);
    const nav = await screen.findByRole('navigation', { name: 'Main' });

    for (const name of [/AI Agents/, /Pipeline Nodes/, /Human Review Queue/, /Resolved/, /All Tickets/]) {
      expect(within(nav).getByRole('button', { name })).toBeInTheDocument();
    }
    expect(within(nav).getByRole('link', { name: 'Reports' })).toHaveAttribute('href', '/admin/reports');
    expect(within(nav).getByRole('link', { name: 'Users' })).toHaveAttribute('href', '/admin/users');
    expect(screen.getByRole('link', { name: 'Back to triage' })).toHaveAttribute('href', '/');
    expect(screen.getAllByRole('main')).toHaveLength(1);
  });

  it('moves the current-tab marker when a tab is chosen', async () => {
    const user = userEvent.setup();
    render(<AdminDashboard />);
    const nav = await screen.findByRole('navigation', { name: 'Main' });
    expect(within(nav).getByRole('button', { name: /AI Agents/ })).toHaveAttribute('aria-current', 'page');

    await user.click(within(nav).getByRole('button', { name: /All Tickets/ }));

    expect(within(nav).getByRole('button', { name: /All Tickets/ })).toHaveAttribute('aria-current', 'page');
    expect(within(nav).getByRole('button', { name: /AI Agents/ })).not.toHaveAttribute('aria-current');
  });

  it('signs out through the shell and returns to /login', async () => {
    const user = userEvent.setup();
    render(<AdminDashboard />);
    await user.click(await screen.findByRole('button', { name: /sign out/i }));
    await waitFor(() => expect(push).toHaveBeenCalledWith('/login'));
    expect(mockSignOut).toHaveBeenCalled();
  });

  it('still sends a non-admin to /login', async () => {
    asRole('agent');
    render(<AdminDashboard />);
    await waitFor(() => expect(push).toHaveBeenCalledWith('/login'));
  });

  it('shows the human-review tab count and a warning-toned queue badge with theme tokens', async () => {
    const escalated = {
      id: 't1', raw_text: 'x', subject: 's', customer_email: null, status: 'escalated',
      created_at: '2026-01-01T00:00:00Z', ticket_drafts: [], ticket_classifications: [],
      resolutions: [{ id: 'r1', final_response: null, escalated: true, escalation_reasons: null, resolved_at: '2026-01-01T00:00:00Z', total_reflection_count: 0, ticket_id: 't1' }],
      human_reviews: [], response_evaluations: [], customer_feedback: null,
    };
    global.fetch = vi.fn(async () =>
      new Response(JSON.stringify({ data: [escalated] }), { status: 200, headers: { 'content-type': 'application/json' } })
    ) as unknown as typeof fetch;
    render(<AdminDashboard />);
    const nav = await screen.findByRole('navigation', { name: 'Main' });
    expect(await within(nav).findByRole('button', { name: 'Human Review Queue (1)' })).toBeInTheDocument();
    const badge = screen.getByText('Human review');
    expect(badge).toHaveClass('text-warning');
    expect(badge.parentElement).toHaveClass('bg-surface', 'border-border');
    expect(badge.parentElement?.className).not.toMatch(/gradient|#|white\//);
  });

  it('tones the active priority pills with the same rule as priorityClass', async () => {
    const user = userEvent.setup();
    render(<AdminDashboard />);
    const nav = await screen.findByRole('navigation', { name: 'Main' });
    await user.click(within(nav).getByRole('button', { name: /All Tickets/ }));
    await user.click(screen.getByRole('button', { name: 'high' }));
    expect(screen.getByRole('button', { name: 'high' })).toHaveClass('text-warning');
    await user.click(screen.getByRole('button', { name: 'critical' }));
    expect(screen.getByRole('button', { name: 'critical' })).toHaveClass('text-danger');
  });
});
