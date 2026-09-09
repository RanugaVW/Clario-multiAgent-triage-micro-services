import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import DashboardPage from '../dashboard/page';
import { useAuth } from '../../contexts/AuthContext';

// ==================== MOCKS ====================

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: vi.fn(() => ({
    push: vi.fn(),
    refresh: vi.fn(),
  })),
}));

vi.mock('../../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: {
          session: {
            access_token: 'test-access-token',
          },
        },
      }),
      signOut: vi.fn(),
    },
    from: vi.fn(() => ({
      select: vi.fn().mockReturnThis(),
      eq: vi.fn().mockReturnThis(),
      order: vi.fn().mockReturnThis(),
      single: vi.fn().mockResolvedValue({ data: null, error: null }),
      delete: vi.fn().mockReturnThis(),
    })),
  },
}));

// ==================== SIMPLIFIED E2E TESTS ====================

describe('Ticket Submission Pipeline - Simplified E2E', () => {
  const mockUser = {
    id: 'user-123',
    email: 'test@example.com',
  };

  beforeEach(() => {
    vi.clearAllMocks();

    (useAuth as any).mockReturnValue({
      user: mockUser,
      role: 'user',
      loading: false,
      roleLoading: false,
    });

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        id: 'ticket-uuid-123',
        status: 'processing',
      }),
    });
  });

  // ==================== Test 1: Load Dashboard ====================
  it('should load the dashboard for authenticated users', async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    expect(screen.getByText(mockUser.email)).toBeInTheDocument();
  });

  // ==================== Test 2: Render Submit Form ====================
  it('should render the ticket submission form', async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText(/Describe the issue.../i);
    expect(textarea).toBeInTheDocument();

    const submitButton = screen.getByRole('button', { name: /PROCESS_TICKET/i });
    expect(submitButton).toBeInTheDocument();
  });

  // ==================== Test 3: Type in Form ====================
  it('should allow typing in the issue textarea', async () => {
    const user = userEvent.setup();
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText(/Describe the issue.../i) as HTMLTextAreaElement;
    
    await user.clear(textarea);
    await user.type(textarea, 'Test issue description');

    expect(textarea.value).toBe('Test issue description');
  });

  // ==================== Test 4: Submit Ticket ====================
  it('should submit ticket when form is submitted', async () => {
    const user = userEvent.setup();
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        id: 'ticket-test-001',
      }),
    });
    global.fetch = mockFetch;

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText(/Describe the issue.../i);
    await user.clear(textarea);
    await user.type(textarea, 'Test submission');

    const submitButton = screen.getByRole('button', { name: /PROCESS_TICKET/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalled();
      const call = mockFetch.mock.calls.find((c: any) => c[0].includes('/api/tickets'));
      expect(call).toBeDefined();
    });
  });

  // ==================== Test 5: Show Success Modal ====================
  it('should display success modal after submission', async () => {
    const user = userEvent.setup();
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText(/Describe the issue.../i);
    await user.clear(textarea);
    await user.type(textarea, 'Success test');

    const submitButton = screen.getByRole('button', { name: /PROCESS_TICKET/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/Ticket Submitted Successfully/i)).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  // ==================== Test 6: Display Tracking ID ====================
  it('should display the tracking ID in success modal', async () => {
    const user = userEvent.setup();
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText(/Describe the issue.../i);
    await user.clear(textarea);
    await user.type(textarea, 'Tracking ID test');

    const submitButton = screen.getByRole('button', { name: /PROCESS_TICKET/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/ticket-uuid-123/)).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  // ==================== Test 7: Send Correct Headers ====================
  it('should send authorization header with ticket submission', async () => {
    const user = userEvent.setup();
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ id: 'ticket-123' }),
    });
    global.fetch = mockFetch;

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText(/Describe the issue.../i);
    await user.clear(textarea);
    await user.type(textarea, 'Auth test');

    const submitButton = screen.getByRole('button', { name: /PROCESS_TICKET/i });
    await user.click(submitButton);

    await waitFor(() => {
      const call = mockFetch.mock.calls.find((c: any) =>
        c[0].includes('/api/tickets') && c[1]?.method === 'POST'
      );
      expect(call).toBeDefined();
      expect(call[1].headers['Authorization']).toContain('Bearer');
    });
  });

  // ==================== Test 8: Send Correct Payload ====================
  it('should send correct payload with rawText and subject', async () => {
    const user = userEvent.setup();
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ id: 'ticket-123' }),
    });
    global.fetch = mockFetch;

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText(/Describe the issue.../i);
    const testText = 'Payload test content';
    await user.clear(textarea);
    await user.type(textarea, testText);

    const submitButton = screen.getByRole('button', { name: /PROCESS_TICKET/i });
    await user.click(submitButton);

    await waitFor(() => {
      const call = mockFetch.mock.calls.find((c: any) =>
        c[0].includes('/api/tickets') && c[1]?.method === 'POST'
      );
      const payload = JSON.parse(call[1].body);
      expect(payload.rawText).toBe(testText);
      expect(payload.subject).toBe('Support Ticket');
    });
  });

  // ==================== Test 9: Handle Submission Error ====================
  it('should show error message on submission failure', async () => {
    const user = userEvent.setup();
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: 'Server error' }),
    });
    global.fetch = mockFetch;

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText(/Describe the issue.../i);
    await user.clear(textarea);
    await user.type(textarea, 'Error test');

    const submitButton = screen.getByRole('button', { name: /PROCESS_TICKET/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/Failed to submit ticket/i)).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  // ==================== Test 10: Tab Navigation ====================
  it('should have working tab navigation', async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    // Submit tab should be visible
    const submitTab = screen.getByRole('button', { name: /Submit Ticket/i });
    expect(submitTab).toBeInTheDocument();

    // My Tickets tab should exist
    const ticketsTab = screen.getByRole('button', { name: /My Tickets/i });
    expect(ticketsTab).toBeInTheDocument();
  });

  // ==================== Test 11: Copy Tracking ID ====================
  it('should copy tracking ID to clipboard', async () => {
    const user = userEvent.setup();
    const mockWriteText = vi.fn().mockResolvedValue(undefined);

    // Mock clipboard
    const clipboardSpy = vi
      .spyOn(navigator.clipboard, 'writeText')
      .mockImplementation(mockWriteText);

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText(/Describe the issue.../i);
    await user.clear(textarea);
    await user.type(textarea, 'Copy test');

    const submitButton = screen.getByRole('button', { name: /PROCESS_TICKET/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/Ticket Submitted Successfully/i)).toBeInTheDocument();
    }, { timeout: 3000 });

    // Find and click copy button
    const copyButton = screen.getByTitle('Copy to clipboard');
    await user.click(copyButton);

    await waitFor(() => {
      expect(clipboardSpy).toHaveBeenCalled();
    });

    clipboardSpy.mockRestore();
  });

  // ==================== Test 12: Complete Workflow ====================
  it('should complete the full ticket submission workflow', async () => {
    const user = userEvent.setup();
    render(<DashboardPage />);

    // Step 1: Load page
    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    // Step 2: User is logged in
    expect(screen.getByText(mockUser.email)).toBeInTheDocument();

    // Step 3: Submit form
    const textarea = screen.getByPlaceholderText(/Describe the issue.../i);
    await user.clear(textarea);
    await user.type(textarea, 'Full workflow test');

    const submitButton = screen.getByRole('button', { name: /PROCESS_TICKET/i });
    await user.click(submitButton);

    // Step 4: See success
    await waitFor(() => {
      expect(screen.getByText(/Ticket Submitted Successfully/i)).toBeInTheDocument();
      expect(screen.getByText(/ticket-uuid-123/)).toBeInTheDocument();
    }, { timeout: 3000 });

    console.log('✅ Complete ticket submission workflow test passed!');
  });

  // ==================== Test 13: Admin Navigation ====================
  it('should show admin panel for admin users', async () => {
    (useAuth as any).mockReturnValue({
      user: mockUser,
      role: 'admin',
      loading: false,
      roleLoading: false,
    });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    // Should show admin button
    const adminButton = screen.queryByRole('button', { name: /Admin Panel/i });
    expect(adminButton).toBeInTheDocument();
  });

  // ==================== Test 14: Agent Navigation ====================
  it('should show agent workspace for agent users', async () => {
    (useAuth as any).mockReturnValue({
      user: mockUser,
      role: 'agent',
      loading: false,
      roleLoading: false,
    });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    // Should show agent button
    const agentButton = screen.queryByRole('button', { name: /Agent Workspace/i });
    expect(agentButton).toBeInTheDocument();
  });

  // ==================== Test 15: Verify API Endpoint ====================
  it('should call the correct API endpoint', async () => {
    const user = userEvent.setup();
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ id: 'ticket-123' }),
    });
    global.fetch = mockFetch;

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText(/Describe the issue.../i);
    await user.clear(textarea);
    await user.type(textarea, 'Endpoint test');

    const submitButton = screen.getByRole('button', { name: /PROCESS_TICKET/i });
    await user.click(submitButton);

    await waitFor(() => {
      const call = mockFetch.mock.calls.find((c: any) =>
        c[0].includes('/api/tickets') && c[1]?.method === 'POST'
      );
      expect(call[0]).toContain('http://localhost:8080/api/tickets');
    });
  });
});
