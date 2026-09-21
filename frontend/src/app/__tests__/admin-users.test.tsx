import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import AdminUsers from '../admin/users/page';
import { useAuth } from '../../contexts/AuthContext';

const push = vi.fn();
vi.mock('../../contexts/AuthContext', () => ({ useAuth: vi.fn() }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }));
vi.mock('../../lib/supabase', () => ({
  supabase: { auth: { getSession: vi.fn().mockResolvedValue({ data: { session: { access_token: 'admin-token' } } }), signOut: vi.fn() } },
}));

const USERS = [
  { id: 'admin-1', email: 'me@example.com', role: 'admin', status: 'active' },
  { id: 'u2', email: 'agent@example.com', role: 'agent', status: 'active' },
  { id: 'u3', email: 'gone@example.com', role: 'user', status: 'suspended' },
];

type Handler = (url: string, init?: RequestInit) => { status?: number; body: unknown };
function mockApi(handler: Handler) {
  global.fetch = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const { status = 200, body } = handler(String(url), init);
    return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
  }) as unknown as typeof fetch;
}
const asRole = (role: string | null) =>
  vi.mocked(useAuth).mockReturnValue({
    user: role ? { id: 'admin-1', email: 'me@example.com' } : null, role, loading: false, roleLoading: false,
  } as unknown as ReturnType<typeof useAuth>);

const patches = () =>
  vi.mocked(global.fetch).mock.calls.filter(([, i]) => (i as RequestInit | undefined)?.method === 'PATCH').map(([, i]) => JSON.parse(String((i as RequestInit).body)));

describe('Admin users page (FR-042 / FR-043)', () => {
  beforeEach(() => { vi.clearAllMocks(); asRole('admin'); });

  it('lists users with their role and status, sending the token', async () => {
    mockApi(() => ({ body: { data: USERS } }));
    render(<AdminUsers />);

    expect(await screen.findByText('agent@example.com')).toBeInTheDocument();
    expect(screen.getByLabelText('Role for agent@example.com')).toHaveValue('agent');
    expect(screen.getByLabelText('Account status for gone@example.com')).toHaveValue('suspended');
    const [, init] = vi.mocked(global.fetch).mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer admin-token');
  });

  it('changes a role immediately (no confirmation) and shows the updated value', async () => {
    mockApi((_u, init) => init?.method === 'PATCH' ? { body: { user: { ...USERS[1], role: 'admin' } } } : { body: { data: USERS } });
    const user = userEvent.setup();
    render(<AdminUsers />);

    await user.selectOptions(await screen.findByLabelText('Role for agent@example.com'), 'admin');

    await waitFor(() => expect(screen.getByLabelText('Role for agent@example.com')).toHaveValue('admin'));
    expect(patches()).toEqual([{ id: 'u2', role: 'admin' }]);
    expect(screen.getByRole('status')).toHaveTextContent('Updated agent@example.com');
  });

  it('asks for confirmation before suspending, and does nothing if cancelled', async () => {
    mockApi(() => ({ body: { data: USERS } }));
    const user = userEvent.setup();
    render(<AdminUsers />);

    await user.selectOptions(await screen.findByLabelText('Account status for agent@example.com'), 'suspended');
    const dialog = screen.getByRole('heading', { name: 'Suspend this account?' }).parentElement!;
    expect(dialog).toHaveTextContent('agent@example.com');
    expect(patches()).toEqual([]); // nothing sent yet

    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(patches()).toEqual([]);
    expect(screen.getByLabelText('Account status for agent@example.com')).toHaveValue('active');
  });

  it('the suspend confirmation is an accessible dialog with a described message and Cancel focused', async () => {
    mockApi(() => ({ body: { data: USERS } }));
    const user = userEvent.setup();
    render(<AdminUsers />);

    await user.selectOptions(await screen.findByLabelText('Account status for agent@example.com'), 'suspended');
    const dialog = await screen.findByRole('dialog', { name: 'Suspend this account?' });
    expect(dialog).toHaveAccessibleDescription(/agent@example.com will be signed out/);
    expect(within(dialog).getByRole('button', { name: 'Cancel' })).toHaveFocus();
  });

  it('suspends after confirmation', async () => {
    mockApi((_u, init) => init?.method === 'PATCH' ? { body: { user: { ...USERS[1], status: 'suspended' } } } : { body: { data: USERS } });
    const user = userEvent.setup();
    render(<AdminUsers />);

    await user.selectOptions(await screen.findByLabelText('Account status for agent@example.com'), 'suspended');
    await user.click(screen.getByRole('button', { name: 'Suspend' }));

    await waitFor(() => expect(patches()).toEqual([{ id: 'u2', status: 'suspended' }]));
    await waitFor(() => expect(screen.getByLabelText('Account status for agent@example.com')).toHaveValue('suspended'));
  });

  it('uses a stronger prompt for deactivation', async () => {
    mockApi(() => ({ body: { data: USERS } }));
    const user = userEvent.setup();
    render(<AdminUsers />);
    await user.selectOptions(await screen.findByLabelText('Account status for agent@example.com'), 'deactivated');
    expect(screen.getByRole('heading', { name: 'Deactivate this account?' })).toBeInTheDocument();
  });

  it('reactivation needs no confirmation', async () => {
    mockApi((_u, init) => init?.method === 'PATCH' ? { body: { user: { ...USERS[2], status: 'active' } } } : { body: { data: USERS } });
    const user = userEvent.setup();
    render(<AdminUsers />);
    await user.selectOptions(await screen.findByLabelText('Account status for gone@example.com'), 'active');
    await waitFor(() => expect(patches()).toEqual([{ id: 'u3', status: 'active' }]));
  });

  it('disables changing your own role and status', async () => {
    mockApi(() => ({ body: { data: USERS } }));
    render(<AdminUsers />);
    expect(await screen.findByLabelText('Role for me@example.com')).toBeDisabled();
    expect(screen.getByLabelText('Account status for me@example.com')).toBeDisabled();
    expect(screen.getByText('(you)')).toBeInTheDocument();
  });

  it('shows the server rejection (A1) and leaves the list unchanged', async () => {
    mockApi((_u, init) => init?.method === 'PATCH' ? { status: 400, body: { error: 'role must be one of: user, agent, admin' } } : { body: { data: USERS } });
    const user = userEvent.setup();
    render(<AdminUsers />);

    await user.selectOptions(await screen.findByLabelText('Role for agent@example.com'), 'user');

    expect(await screen.findByRole('alert')).toHaveTextContent('role must be one of');
    expect(screen.getByLabelText('Role for agent@example.com')).toHaveValue('agent');
  });

  it('shows the migration hint from a 503 instead of an empty list', async () => {
    mockApi(() => ({ status: 503, body: { error: 'Account status is not set up in the database yet. Run supabase_user_management.sql in the Supabase SQL Editor.' } }));
    render(<AdminUsers />);
    expect(await screen.findByRole('alert')).toHaveTextContent('supabase_user_management.sql');
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it.each(['agent', 'user', null])('sends %s to /login without loading users', async (r) => {
    asRole(r);
    mockApi(() => ({ body: { data: USERS } }));
    render(<AdminUsers />);
    await waitFor(() => expect(push).toHaveBeenCalledWith('/login'));
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
