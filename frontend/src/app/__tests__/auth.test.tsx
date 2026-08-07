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
    (useRouter as any).mockReturnValue({ push: mockPush });
  });

  it('renders login form correctly', () => {
    render(<Login />);
    
    expect(screen.getByPlaceholderText('agent@clario.com')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('••••••••')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('shows error message on failed login', async () => {
    const user = userEvent.setup();
    (supabase.auth.signInWithPassword as any).mockResolvedValue({
      error: { message: 'Invalid login credentials' },
      data: { user: null },
    });

    render(<Login />);

    await user.type(screen.getByPlaceholderText('agent@clario.com'), 'test@example.com');
    await user.type(screen.getByPlaceholderText('••••••••'), 'wrongpassword');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText('Invalid login credentials')).toBeInTheDocument();
    });
    
    expect(mockPush).not.toHaveBeenCalled();
  });

  it('routes admin correctly after successful login', async () => {
    const user = userEvent.setup();
    
    (supabase.auth.signInWithPassword as any).mockResolvedValue({
      error: null,
      data: { user: { id: 'admin-123' } },
    });

    const mockSingle = vi.fn().mockResolvedValue({ data: { role: 'admin' }, error: null });
    const mockEq = vi.fn().mockReturnValue({ single: mockSingle });
    const mockSelect = vi.fn().mockReturnValue({ eq: mockEq });
    (supabase.from as any).mockReturnValue({ select: mockSelect });

    render(<Login />);

    await user.type(screen.getByPlaceholderText('agent@clario.com'), 'admin@example.com');
    await user.type(screen.getByPlaceholderText('••••••••'), 'password');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(supabase.from).toHaveBeenCalledWith('users');
      expect(mockPush).toHaveBeenCalledWith('/admin');
    });
  });

  it('routes user correctly after successful login', async () => {
    const user = userEvent.setup();
    
    (supabase.auth.signInWithPassword as any).mockResolvedValue({
      error: null,
      data: { user: { id: 'user-123' } },
    });

    const mockSingle = vi.fn().mockResolvedValue({ data: { role: 'user' }, error: null });
    const mockEq = vi.fn().mockReturnValue({ single: mockSingle });
    const mockSelect = vi.fn().mockReturnValue({ eq: mockEq });
    (supabase.from as any).mockReturnValue({ select: mockSelect });

    render(<Login />);

    await user.type(screen.getByPlaceholderText('agent@clario.com'), 'user@example.com');
    await user.type(screen.getByPlaceholderText('••••••••'), 'password');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/dashboard');
    });
  });
});
