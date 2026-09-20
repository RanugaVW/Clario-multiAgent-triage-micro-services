import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import Login from '../login/page';
import { supabase } from '../../lib/supabase';
import { useRouter } from 'next/navigation';

// Mock Next.js navigation
vi.mock('next/navigation', () => ({
  useRouter: vi.fn(),
}));

// Mock Supabase
vi.mock('../../lib/supabase', () => ({
  supabase: {
    auth: {
      signInWithPassword: vi.fn(),
    },
    from: vi.fn(() => ({
      select: vi.fn(() => ({
        eq: vi.fn(() => ({
          single: vi.fn(),
        })),
      })),
    })),
  },
}));

describe('Login Authentication', () => {
  const mockPush = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useRouter).mockReturnValue({ push: mockPush } as unknown as ReturnType<typeof useRouter>);
  });

  it('renders login form correctly', () => {
    render(<Login />);

    expect(screen.getByPlaceholderText('Email address')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Password')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  // UR-005: form controls must have descriptive, programmatically-associated
  // labels, not just placeholder text (placeholders disappear on input and
  // are not reliably announced by all screen readers).
  it('associates an accessible label with the email and password inputs', () => {
    render(<Login />);

    const emailInput = screen.getByLabelText('Email address');
    const passwordInput = screen.getByLabelText('Password');

    expect(emailInput).toBeInTheDocument();
    expect(emailInput).toHaveAttribute('type', 'email');
    expect(passwordInput).toBeInTheDocument();
    expect(passwordInput).toHaveAttribute('type', 'password');
  });

  // SRS 3.9.1 (Authentication Interface): Forgot Password option + visibility toggle.
  it('links to the forgot-password page', () => {
    render(<Login />);

    expect(screen.getByRole('link', { name: /forgot password/i })).toHaveAttribute('href', '/forgot-password');
  });

  it('lets the user reveal the password they are typing, without submitting the form', async () => {
    const user = userEvent.setup();
    render(<Login />);

    await user.type(screen.getByPlaceholderText('Password'), 'secret-pw');
    expect(screen.getByPlaceholderText('Password')).toHaveAttribute('type', 'password');

    await user.click(screen.getByRole('button', { name: 'Show password' }));

    expect(screen.getByPlaceholderText('Password')).toHaveAttribute('type', 'text');
    expect(supabase.auth.signInWithPassword).not.toHaveBeenCalled();
  });

  it('shows error message on failed login', async () => {
    const user = userEvent.setup();
    vi.mocked(supabase.auth.signInWithPassword).mockResolvedValue({
      error: { message: 'Invalid login credentials' },
      data: { user: null },
    } as unknown as Awaited<ReturnType<typeof supabase.auth.signInWithPassword>>);

    render(<Login />);

    await user.type(screen.getByPlaceholderText('Email address'), 'test@example.com');
    await user.type(screen.getByPlaceholderText('Password'), 'wrongpassword');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText('Invalid login credentials')).toBeInTheDocument();
    });
    
    expect(mockPush).not.toHaveBeenCalled();
  });

  it('explains a suspended account instead of showing the raw "User is banned" message (FR-043)', async () => {
    const user = userEvent.setup();
    vi.mocked(supabase.auth.signInWithPassword).mockResolvedValue({
      error: { message: 'User is banned' },
      data: { user: null },
    } as unknown as Awaited<ReturnType<typeof supabase.auth.signInWithPassword>>);

    render(<Login />);
    await user.type(screen.getByPlaceholderText('Email address'), 'gone@example.com');
    await user.type(screen.getByPlaceholderText('Password'), 'whatever');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByText(/suspended or deactivated.*contact an administrator/i)).toBeInTheDocument();
    expect(screen.queryByText('User is banned')).not.toBeInTheDocument();
    expect(mockPush).not.toHaveBeenCalled();
  });

  it('routes admin correctly after successful login', async () => {
    const user = userEvent.setup();
    
    vi.mocked(supabase.auth.signInWithPassword).mockResolvedValue({
      error: null,
      data: { user: { id: 'admin-123' } },
    } as unknown as Awaited<ReturnType<typeof supabase.auth.signInWithPassword>>);

    const mockSingle = vi.fn().mockResolvedValue({ data: { role: 'admin' }, error: null });
    const mockEq = vi.fn().mockReturnValue({ single: mockSingle });
    const mockSelect = vi.fn().mockReturnValue({ eq: mockEq });
    vi.mocked(supabase.from).mockReturnValue({ select: mockSelect } as unknown as ReturnType<typeof supabase.from>);

    render(<Login />);

    await user.type(screen.getByPlaceholderText('Email address'), 'admin@example.com');
    await user.type(screen.getByPlaceholderText('Password'), 'password');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(supabase.from).toHaveBeenCalledWith('users');
      expect(mockPush).toHaveBeenCalledWith('/admin');
    });
  });

  it('routes user correctly after successful login', async () => {
    const user = userEvent.setup();
    
    vi.mocked(supabase.auth.signInWithPassword).mockResolvedValue({
      error: null,
      data: { user: { id: 'user-123' } },
    } as unknown as Awaited<ReturnType<typeof supabase.auth.signInWithPassword>>);

    const mockSingle = vi.fn().mockResolvedValue({ data: { role: 'user' }, error: null });
    const mockEq = vi.fn().mockReturnValue({ single: mockSingle });
    const mockSelect = vi.fn().mockReturnValue({ eq: mockEq });
    vi.mocked(supabase.from).mockReturnValue({ select: mockSelect } as unknown as ReturnType<typeof supabase.from>);

    render(<Login />);

    await user.type(screen.getByPlaceholderText('Email address'), 'user@example.com');
    await user.type(screen.getByPlaceholderText('Password'), 'password');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/dashboard');
    });
  });
});
