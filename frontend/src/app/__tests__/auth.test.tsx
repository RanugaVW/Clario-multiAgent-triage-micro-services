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
<<<<<<< HEAD
    vi.mocked(useRouter).mockReturnValue({ push: mockPush } as unknown as ReturnType<typeof useRouter>);
=======
    (useRouter as any).mockReturnValue({ push: mockPush });
>>>>>>> origin/add/voice-to-text-service
  });

  it('renders login form correctly', () => {
    render(<Login />);
    
<<<<<<< HEAD
    expect(screen.getByPlaceholderText('Email address')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Password')).toBeInTheDocument();
=======
    expect(screen.getByPlaceholderText('agent@clario.com')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('••••••••')).toBeInTheDocument();
>>>>>>> origin/add/voice-to-text-service
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('shows error message on failed login', async () => {
    const user = userEvent.setup();
<<<<<<< HEAD
    vi.mocked(supabase.auth.signInWithPassword).mockResolvedValue({
      error: { message: 'Invalid login credentials' },
      data: { user: null },
    } as unknown as Awaited<ReturnType<typeof supabase.auth.signInWithPassword>>);

    render(<Login />);

    await user.type(screen.getByPlaceholderText('Email address'), 'test@example.com');
    await user.type(screen.getByPlaceholderText('Password'), 'wrongpassword');
=======
    (supabase.auth.signInWithPassword as any).mockResolvedValue({
      error: { message: 'Invalid login credentials' },
      data: { user: null },
    });

    render(<Login />);

    await user.type(screen.getByPlaceholderText('agent@clario.com'), 'test@example.com');
    await user.type(screen.getByPlaceholderText('••••••••'), 'wrongpassword');
>>>>>>> origin/add/voice-to-text-service
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText('Invalid login credentials')).toBeInTheDocument();
    });
    
    expect(mockPush).not.toHaveBeenCalled();
  });

  it('routes admin correctly after successful login', async () => {
    const user = userEvent.setup();
    
<<<<<<< HEAD
    vi.mocked(supabase.auth.signInWithPassword).mockResolvedValue({
      error: null,
      data: { user: { id: 'admin-123' } },
    } as unknown as Awaited<ReturnType<typeof supabase.auth.signInWithPassword>>);
=======
    (supabase.auth.signInWithPassword as any).mockResolvedValue({
      error: null,
      data: { user: { id: 'admin-123' } },
    });
>>>>>>> origin/add/voice-to-text-service

    const mockSingle = vi.fn().mockResolvedValue({ data: { role: 'admin' }, error: null });
    const mockEq = vi.fn().mockReturnValue({ single: mockSingle });
    const mockSelect = vi.fn().mockReturnValue({ eq: mockEq });
<<<<<<< HEAD
    vi.mocked(supabase.from).mockReturnValue({ select: mockSelect } as unknown as ReturnType<typeof supabase.from>);

    render(<Login />);

    await user.type(screen.getByPlaceholderText('Email address'), 'admin@example.com');
    await user.type(screen.getByPlaceholderText('Password'), 'password');
=======
    (supabase.from as any).mockReturnValue({ select: mockSelect });

    render(<Login />);

    await user.type(screen.getByPlaceholderText('agent@clario.com'), 'admin@example.com');
    await user.type(screen.getByPlaceholderText('••••••••'), 'password');
>>>>>>> origin/add/voice-to-text-service
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(supabase.from).toHaveBeenCalledWith('users');
      expect(mockPush).toHaveBeenCalledWith('/admin');
    });
  });

  it('routes user correctly after successful login', async () => {
    const user = userEvent.setup();
    
<<<<<<< HEAD
    vi.mocked(supabase.auth.signInWithPassword).mockResolvedValue({
      error: null,
      data: { user: { id: 'user-123' } },
    } as unknown as Awaited<ReturnType<typeof supabase.auth.signInWithPassword>>);
=======
    (supabase.auth.signInWithPassword as any).mockResolvedValue({
      error: null,
      data: { user: { id: 'user-123' } },
    });
>>>>>>> origin/add/voice-to-text-service

    const mockSingle = vi.fn().mockResolvedValue({ data: { role: 'user' }, error: null });
    const mockEq = vi.fn().mockReturnValue({ single: mockSingle });
    const mockSelect = vi.fn().mockReturnValue({ eq: mockEq });
<<<<<<< HEAD
    vi.mocked(supabase.from).mockReturnValue({ select: mockSelect } as unknown as ReturnType<typeof supabase.from>);

    render(<Login />);

    await user.type(screen.getByPlaceholderText('Email address'), 'user@example.com');
    await user.type(screen.getByPlaceholderText('Password'), 'password');
=======
    (supabase.from as any).mockReturnValue({ select: mockSelect });

    render(<Login />);

    await user.type(screen.getByPlaceholderText('agent@clario.com'), 'user@example.com');
    await user.type(screen.getByPlaceholderText('••••••••'), 'password');
>>>>>>> origin/add/voice-to-text-service
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/dashboard');
    });
  });
});
