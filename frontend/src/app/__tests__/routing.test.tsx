import { render, screen } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import DashboardPage from '../dashboard/page';
import { useAuth } from '../../contexts/AuthContext';
import { useRouter } from 'next/navigation';

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: vi.fn(),
}));

vi.mock('../../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
      signOut: vi.fn(),
    },
  },
}));

describe('Dashboard Routing', () => {
  const mockPush = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useRouter).mockReturnValue({ push: mockPush, refresh: vi.fn() } as unknown as ReturnType<typeof useRouter>);
    
    // Mock fetch for the history call
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue([]),
    });
  });

  it('redirects to login if user is not authenticated', () => {
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      role: null,
      loading: false,
      roleLoading: false,
    } as unknown as ReturnType<typeof useAuth>);

    render(<DashboardPage />);
    
    expect(mockPush).toHaveBeenCalledWith('/login');
  });

  it('redirects to admin if user role is admin', () => {
    vi.mocked(useAuth).mockReturnValue({
      user: { id: 'admin-123' },
      role: 'admin',
      loading: false,
      roleLoading: false,
    } as unknown as ReturnType<typeof useAuth>);

    render(<DashboardPage />);
    
    expect(mockPush).toHaveBeenCalledWith('/admin');
  });

  it('renders dashboard if user is authenticated as user', () => {
    vi.mocked(useAuth).mockReturnValue({
      user: { id: 'user-123' },
      role: 'user',
      loading: false,
      roleLoading: false,
    } as unknown as ReturnType<typeof useAuth>);

    render(<DashboardPage />);
    
    expect(mockPush).not.toHaveBeenCalledWith('/login');
    expect(mockPush).not.toHaveBeenCalledWith('/admin');
    
    // Verify dashboard renders
    expect(screen.getByText(/New ticket/i)).toBeInTheDocument();
  });
  
  it('shows loading spinner when auth is loading', () => {
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      role: null,
      loading: true,
      roleLoading: true,
    } as unknown as ReturnType<typeof useAuth>);

    const { container } = render(<DashboardPage />);
    
    expect(mockPush).not.toHaveBeenCalled();
    // The spinner div has a class of animate-spin
    expect(container.querySelector('.animate-spin')).toBeInTheDocument();
  });
});
