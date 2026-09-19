import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import Register from '../register/page';

// Mock Supabase - Register only calls auth.signUp, nothing else.
vi.mock('../../lib/supabase', () => ({
  supabase: {
    auth: {
      signUp: vi.fn(),
    },
  },
}));

describe('Register form accessibility', () => {
  // UR-005: the visible "Email address" / "Password" text on this page was
  // already present, but was not programmatically associated with its input
  // (no htmlFor/id pair) - a screen reader would not announce it, and
  // clicking the label text would not focus the field.
  it('associates the visible labels with their inputs via htmlFor/id', () => {
    render(<Register />);

    const emailInput = screen.getByLabelText('Email address');
    const passwordInput = screen.getByLabelText('Password (min 6 characters)');

    expect(emailInput).toBeInTheDocument();
    expect(emailInput).toHaveAttribute('type', 'email');
    expect(passwordInput).toBeInTheDocument();
    expect(passwordInput).toHaveAttribute('type', 'password');
  });

  it('offers the password visibility toggle', async () => {
    const user = userEvent.setup();
    render(<Register />);

    await user.click(screen.getByRole('button', { name: 'Show password' }));

    expect(screen.getByLabelText('Password (min 6 characters)')).toHaveAttribute('type', 'text');
  });
});
