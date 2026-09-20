import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ResetPassword from '../reset-password/page';
import { supabase } from '../../lib/supabase';
import { renderWithTheme } from '../../test/renderWithTheme';

type AuthCallback = (event: string, session: unknown) => void;
let authCallback: AuthCallback;
const unsubscribe = vi.fn();

vi.mock('../../lib/supabase', () => ({
  supabase: {
    auth: {
      onAuthStateChange: vi.fn(),
      updateUser: vi.fn(),
      signOut: vi.fn(),
    },
  },
}));

vi.mock('next/navigation', () => ({ usePathname: () => '/reset-password' }));

const renderReset = () => renderWithTheme(<ResetPassword />, ['/reset-password']);

function fire(event: string, session: unknown = null) {
  act(() => authCallback(event, session));
}

async function openRecoveryForm() {
  renderReset();
  fire('PASSWORD_RECOVERY', { user: { id: 'u1' } });
  return screen.findByLabelText(/new password \(min/i);
}

describe('Reset password page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(supabase.auth.onAuthStateChange).mockImplementation(((cb: AuthCallback) => {
      authCallback = cb;
      return { data: { subscription: { unsubscribe } } };
    }) as never);
    vi.mocked(supabase.auth.updateUser).mockResolvedValue({ data: {}, error: null } as never);
    vi.mocked(supabase.auth.signOut).mockResolvedValue({ error: null } as never);
  });

  it('says the link is unusable when there is no recovery session, instead of showing a form that cannot work', () => {
    renderReset();
    fire('INITIAL_SESSION', null);

    expect(screen.getByRole('alert')).toHaveTextContent(/invalid or has expired/i);
    expect(screen.getByRole('link', { name: /request a new link/i })).toHaveAttribute('href', '/forgot-password');
    expect(screen.queryByLabelText(/new password \(min/i)).not.toBeInTheDocument();
  });

  it('shows a neutral state while the link is being verified', () => {
    renderReset();

    expect(screen.getByRole('status')).toHaveTextContent(/verifying/i);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('shows the form once Supabase reports a recovery session', async () => {
    await openRecoveryForm();

    expect(screen.getByLabelText(/confirm new password/i)).toBeInTheDocument();
  });

  it('is not knocked back to "invalid" by the initial-session event that follows a recovery event', async () => {
    renderReset();
    fire('PASSWORD_RECOVERY', { user: { id: 'u1' } });
    fire('INITIAL_SESSION', null);

    expect(await screen.findByLabelText(/new password \(min/i)).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('refuses a password that is too short, without calling Supabase', async () => {
    const user = userEvent.setup();
    const field = await openRecoveryForm();

    await user.type(field, 'abc');
    await user.type(screen.getByLabelText(/confirm new password/i), 'abc');
    await user.click(screen.getByRole('button', { name: /update password/i }));

    expect(screen.getByRole('alert')).toHaveTextContent(/at least 6 characters/i);
    expect(supabase.auth.updateUser).not.toHaveBeenCalled();
  });

  it('refuses mismatched passwords, without calling Supabase', async () => {
    const user = userEvent.setup();
    const field = await openRecoveryForm();

    await user.type(field, 'longenough1');
    await user.type(screen.getByLabelText(/confirm new password/i), 'different22');
    await user.click(screen.getByRole('button', { name: /update password/i }));

    expect(screen.getByRole('alert')).toHaveTextContent(/do not match/i);
    expect(supabase.auth.updateUser).not.toHaveBeenCalled();
  });

  it('updates the password, ends the recovery session, and points to sign in', async () => {
    const user = userEvent.setup();
    const field = await openRecoveryForm();

    await user.type(field, 'longenough1');
    await user.type(screen.getByLabelText(/confirm new password/i), 'longenough1');
    await user.click(screen.getByRole('button', { name: /update password/i }));

    await waitFor(() => expect(supabase.auth.updateUser).toHaveBeenCalledWith({ password: 'longenough1' }));
    expect(supabase.auth.signOut).toHaveBeenCalled();
    const done = await screen.findByRole('status');
    expect(done).toHaveTextContent(/password updated/i);
    expect(done).toHaveFocus();
    expect(screen.getByRole('link', { name: /go to sign in/i })).toHaveAttribute('href', '/login');
  });

  it('shows the service error and stays on the form so the user can retry', async () => {
    const user = userEvent.setup();
    vi.mocked(supabase.auth.updateUser).mockResolvedValue({
      data: null,
      error: { message: 'New password should be different from the old password.' },
    } as never);
    const field = await openRecoveryForm();

    await user.type(field, 'longenough1');
    await user.type(screen.getByLabelText(/confirm new password/i), 'longenough1');
    await user.click(screen.getByRole('button', { name: /update password/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/should be different/i);
    expect(supabase.auth.signOut).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: /update password/i })).toBeEnabled();
  });

  it('gives both password fields a visibility toggle', async () => {
    await openRecoveryForm();

    expect(screen.getAllByRole('button', { name: 'Show password' })).toHaveLength(2);
  });

  it('stops listening for auth events when it goes away', () => {
    const { unmount } = renderReset();
    unmount();

    expect(unsubscribe).toHaveBeenCalled();
  });

  it('is the auth layout with one h1 in every state', async () => {
    renderReset();
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Choose a new password');
    expect(screen.getByRole('main')).toBeInTheDocument();
  });

  it('attaches a too-short password error to the password field', async () => {
    const user = userEvent.setup();
    await openRecoveryForm();
    await user.type(screen.getByLabelText(/new password \(min/i), 'abc');
    await user.type(screen.getByLabelText(/confirm new password/i), 'abc');
    await user.click(screen.getByRole('button', { name: /update password/i }));

    const field = screen.getByLabelText(/new password \(min/i);
    expect(field).toHaveAttribute('aria-invalid', 'true');
    expect(field).toHaveAccessibleDescription(/at least 6 characters/i);
    expect(screen.getByLabelText(/confirm new password/i)).not.toHaveAttribute('aria-invalid');
  });

  it('attaches a mismatch error to the confirmation field', async () => {
    const user = userEvent.setup();
    await openRecoveryForm();
    await user.type(screen.getByLabelText(/new password \(min/i), 'longenough1');
    await user.type(screen.getByLabelText(/confirm new password/i), 'different22');
    await user.click(screen.getByRole('button', { name: /update password/i }));

    const confirm = screen.getByLabelText(/confirm new password/i);
    expect(confirm).toHaveAttribute('aria-invalid', 'true');
    expect(confirm).toHaveAccessibleDescription(/do not match/i);
    expect(screen.getByLabelText(/new password \(min/i)).not.toHaveAttribute('aria-invalid');
  });
});
