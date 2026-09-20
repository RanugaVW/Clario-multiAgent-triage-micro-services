import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ForgotPassword from '../forgot-password/page';
import { supabase } from '../../lib/supabase';
import { renderWithTheme } from '../../test/renderWithTheme';

vi.mock('../../lib/supabase', () => ({
  supabase: { auth: { resetPasswordForEmail: vi.fn() } },
}));

vi.mock('next/navigation', () => ({ usePathname: () => '/forgot-password' }));

const renderForgot = () => renderWithTheme(<ForgotPassword />, ['/forgot-password']);

describe('Forgot password page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('asks Supabase to email a link that lands on the reset page', async () => {
    const user = userEvent.setup();
    vi.mocked(supabase.auth.resetPasswordForEmail).mockResolvedValue({ data: {}, error: null } as never);
    renderForgot();

    await user.type(screen.getByLabelText('Email address'), 'me@example.com');
    await user.click(screen.getByRole('button', { name: /send reset link/i }));

    await waitFor(() => {
      expect(supabase.auth.resetPasswordForEmail).toHaveBeenCalledWith('me@example.com', {
        redirectTo: `${window.location.origin}/reset-password`,
      });
    });
  });

  it('confirms without revealing whether the address has an account', async () => {
    const user = userEvent.setup();
    vi.mocked(supabase.auth.resetPasswordForEmail).mockResolvedValue({ data: {}, error: null } as never);
    renderForgot();

    await user.type(screen.getByLabelText('Email address'), 'nobody@example.com');
    await user.click(screen.getByRole('button', { name: /send reset link/i }));

    const confirmation = await screen.findByRole('status');
    expect(confirmation).toHaveTextContent(/if an account exists/i);
    expect(confirmation).toHaveFocus();
    expect(confirmation).not.toHaveTextContent(/nobody@example\.com/);
    expect(screen.getByRole('link', { name: /return to sign in/i })).toHaveAttribute('href', '/login');
  });

  it('shows a service error (e.g. rate limiting) and keeps the form usable', async () => {
    const user = userEvent.setup();
    vi.mocked(supabase.auth.resetPasswordForEmail).mockResolvedValue({
      data: null,
      error: { message: 'Email rate limit exceeded' },
    } as never);
    renderForgot();

    await user.type(screen.getByLabelText('Email address'), 'me@example.com');
    await user.click(screen.getByRole('button', { name: /send reset link/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Email rate limit exceeded');
    expect(screen.getByRole('button', { name: /send reset link/i })).toBeEnabled();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('requires an email address before anything is sent', async () => {
    const user = userEvent.setup();
    renderForgot();

    await user.click(screen.getByRole('button', { name: /send reset link/i }));

    expect(supabase.auth.resetPasswordForEmail).not.toHaveBeenCalled();
    expect(screen.getByLabelText('Email address')).toBeRequired();
  });

  it('links back to sign in', () => {
    renderForgot();

    expect(screen.getByRole('link', { name: /back to sign in/i })).toHaveAttribute('href', '/login');
  });

  it('shows the instruction and the back link only before sending', async () => {
    const user = userEvent.setup();
    vi.mocked(supabase.auth.resetPasswordForEmail).mockResolvedValue({ data: {}, error: null } as never);
    renderForgot();

    expect(screen.getByText(/enter the email address/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /back to sign in/i })).toHaveAttribute('href', '/login');

    await user.type(screen.getByLabelText('Email address'), 'me@example.com');
    await user.click(screen.getByRole('button', { name: /send reset link/i }));
    await screen.findByRole('status');

    expect(screen.queryByText(/enter the email address/i)).not.toBeInTheDocument();
    const loginLinks = screen
      .getAllByRole('link', { name: /sign in/i })
      .filter((a) => a.getAttribute('href') === '/login');
    expect(loginLinks).toHaveLength(1);
  });

  it('is the auth layout with one h1', () => {
    renderForgot();
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Reset password');
    expect(screen.getByRole('main')).toBeInTheDocument();
  });
});
