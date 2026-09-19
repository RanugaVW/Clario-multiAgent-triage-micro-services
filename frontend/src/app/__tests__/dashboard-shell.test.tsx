import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import DashboardPage from '../dashboard/page';
import { useAuth } from '../../contexts/AuthContext';

const push = vi.fn();
const refresh = vi.fn();
const mockSignOut = vi.hoisted(() => vi.fn());

vi.mock('../../contexts/AuthContext', () => ({ useAuth: vi.fn() }));
// A stable router object, like the real one: a fresh object per render would re-run the page's effects forever.
const router = { push, refresh };
vi.mock('next/navigation', () => ({ useRouter: () => router }));
vi.mock('../../lib/supabase', () => ({
  supabase: {
    auth: { getSession: vi.fn().mockResolvedValue({ data: { session: { access_token: 'tok' } } }), signOut: mockSignOut },
    from: vi.fn(),
  },
}));

const asRole = (role: string) =>
  vi.mocked(useAuth).mockReturnValue({
    user: { id: 'u1', email: 'cust@example.com' }, role, loading: false, roleLoading: false,
  } as unknown as ReturnType<typeof useAuth>);

// UR-001: the customer dashboard runs inside the same navigation shell as the agent and admin workspaces.
describe('Customer dashboard inside the shared navigation shell', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    asRole('user');
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => [] }) as unknown as typeof fetch;
  });

  it('has the shared landmarks and its two tabs, with "New ticket" current', () => {
    render(<DashboardPage />);
    const nav = screen.getByRole('navigation', { name: 'Main' });
    expect(within(nav).getByRole('button', { name: 'New ticket' })).toHaveAttribute('aria-current', 'page');
    expect(within(nav).getByRole('button', { name: /My tickets/ })).not.toHaveAttribute('aria-current');
    expect(screen.getAllByRole('main')).toHaveLength(1);
    expect(screen.getByText('cust@example.com')).toBeInTheDocument();
  });

  it('switches tab from the shell nav and moves aria-current with it', async () => {
    const user = userEvent.setup();
    render(<DashboardPage />);
    const nav = screen.getByRole('navigation', { name: 'Main' });

    await user.click(within(nav).getByRole('button', { name: /My tickets/ }));

    expect(within(nav).getByRole('button', { name: /My tickets/ })).toHaveAttribute('aria-current', 'page');
    expect(within(nav).getByRole('button', { name: 'New ticket' })).not.toHaveAttribute('aria-current');
    expect(screen.queryByPlaceholderText(/Describe the issue.../i)).not.toBeInTheDocument();
  });

  it('refreshes the ticket history each time the My tickets tab is opened', async () => {
    const user = userEvent.setup();
    global.fetch = vi.fn(async () =>
      new Response(JSON.stringify({ data: [] }), { status: 200, headers: { 'content-type': 'application/json' } })
    ) as unknown as typeof fetch;
    render(<DashboardPage />);
    const historyCalls = () => vi.mocked(global.fetch).mock.calls.filter(([u]) => String(u).startsWith('/api/user_tickets?userId=u1')).length;
    await waitFor(() => expect(historyCalls()).toBeGreaterThan(0)); // the mount-time fetch has landed
    const before = historyCalls();

    await user.click(within(screen.getByRole('navigation', { name: 'Main' })).getByRole('button', { name: /My tickets/ }));

    await waitFor(() => expect(historyCalls()).toBe(before + 1));
  });

  it('signs out through the shell', async () => {
    const user = userEvent.setup();
    render(<DashboardPage />);
    await user.click(screen.getByRole('button', { name: /sign out/i }));
    await waitFor(() => expect(mockSignOut).toHaveBeenCalled());
    expect(refresh).toHaveBeenCalled();
  });

  it.each([
    ['admin', 'Admin panel', '/admin'],
    ['agent', 'Agent workspace', '/agent'],
  ])('shows the %s a link to their workspace, and customers none', (role, label, href) => {
    asRole(role);
    const { unmount } = render(<DashboardPage />);
    expect(screen.getByRole('link', { name: label })).toHaveAttribute('href', href);
    unmount();

    asRole('user');
    render(<DashboardPage />);
    expect(screen.queryByRole('link', { name: label })).not.toBeInTheDocument();
  });
});
