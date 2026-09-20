import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Register from '../register/page';
import { renderWithTheme } from '../../test/renderWithTheme';
import { supabase } from '../../lib/supabase';

// Mock Supabase - Register only calls auth.signUp, nothing else.
vi.mock('../../lib/supabase', () => ({
  supabase: {
    auth: {
      signUp: vi.fn(),
    },
  },
}));

vi.mock('next/navigation', () => ({ usePathname: () => '/register' }));

const renderRegister = () => renderWithTheme(<Register />, ['/register']);

describe('Register form accessibility', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // UR-005: the visible "Email address" / "Password" text on this page was
  // already present, but was not programmatically associated with its input
  // (no htmlFor/id pair) - a screen reader would not announce it, and
  // clicking the label text would not focus the field.
  it('associates the visible labels with their inputs via htmlFor/id', () => {
    renderRegister();

    const emailInput = screen.getByLabelText('Email address');
    const passwordInput = screen.getByLabelText('Password (min 6 characters)');

    expect(emailInput).toBeInTheDocument();
    expect(emailInput).toHaveAttribute('type', 'email');
    expect(passwordInput).toBeInTheDocument();
    expect(passwordInput).toHaveAttribute('type', 'password');
  });

  it('offers the password visibility toggle', async () => {
    const user = userEvent.setup();
    renderRegister();

    await user.click(screen.getByRole('button', { name: 'Show password' }));

    expect(screen.getByLabelText('Password (min 6 characters)')).toHaveAttribute('type', 'text');
  });

  it('is the auth layout with one h1', () => {
    renderRegister();
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Create an account');
    expect(screen.getByRole('main')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /sign in/i })).toHaveAttribute('href', '/login');
  });

  it('requires a password of at least six characters and a valid email', () => {
    renderRegister();
    expect(screen.getByLabelText('Email address')).toBeRequired();
    expect(screen.getByLabelText('Password (min 6 characters)')).toHaveAttribute('minlength', '6');
    expect(screen.getByLabelText('Password (min 6 characters)')).toHaveAttribute('autocomplete', 'new-password');
  });

  it('signs up with a redirect back to the login page and then tells the user to check their email', async () => {
    const user = userEvent.setup();
    vi.mocked(supabase.auth.signUp).mockResolvedValue({ data: {}, error: null } as never);
    renderRegister();

    await user.type(screen.getByLabelText('Email address'), 'me@example.com');
    await user.type(screen.getByLabelText('Password (min 6 characters)'), 'longenough1');
    await user.click(screen.getByRole('button', { name: /create account/i }));

    await waitFor(() =>
      expect(supabase.auth.signUp).toHaveBeenCalledWith({
        email: 'me@example.com',
        password: 'longenough1',
        options: { emailRedirectTo: `${window.location.origin}/login` },
      })
    );
    const status = await screen.findByRole('status');
    expect(status).toHaveTextContent(/check your email/i);
    expect(screen.getByRole('link', { name: /return to sign in/i })).toHaveAttribute('href', '/login');
  });

  it('shows a sign-up failure as an alert and keeps the form', async () => {
    const user = userEvent.setup();
    vi.mocked(supabase.auth.signUp).mockResolvedValue({
      data: {},
      error: { message: 'User already registered' },
    } as never);
    renderRegister();

    await user.type(screen.getByLabelText('Email address'), 'me@example.com');
    await user.type(screen.getByLabelText('Password (min 6 characters)'), 'longenough1');
    await user.click(screen.getByRole('button', { name: /create account/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('User already registered');
    expect(screen.getByRole('button', { name: /create account/i })).toBeEnabled();
  });
});
