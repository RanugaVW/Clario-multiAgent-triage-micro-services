import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import DashboardPage from '../dashboard/page';
import { useAuth } from '../../contexts/AuthContext';

// ==================== SETUP MOCKS ====================

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
        data: { session: { access_token: 'test-token' } },
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

// ==================== USER WORKFLOW TESTS ====================

describe('User Workflow Scenarios', () => {
  const mockUser = { id: 'user-123', email: 'testuser@clario.com' };

  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(useAuth).mockReturnValue({
      user: mockUser,
      role: 'user',
      loading: false,
      roleLoading: false,
    } as unknown as ReturnType<typeof useAuth>);

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ id: 'ticket-123' }),
    });
  });

  // ==================== Scenario 1: First Time User ====================
  it('should guide first-time user through ticket submission', async () => {
    const user = userEvent.setup();
    render(<DashboardPage />);

    // Page loads
    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    // User sees welcome description
    expect(screen.getByText(/Submit a support ticket/i)).toBeInTheDocument();

    // User reads the placeholder text
    const textarea = screen.getByPlaceholderText(/Describe the issue.../i);
    expect(textarea).toBeInTheDocument();

    // User starts typing their issue
    await user.type(textarea, 'First ticket: My password is not working');

    // User submits
    const submitBtn = screen.getByRole('button', { name: /submit ticket/i });
    await user.click(submitBtn);

    // User sees success confirmation
    await waitFor(() => {
      expect(screen.getByText('Ticket submitted successfully!')).toBeInTheDocument();
    });

    // User can copy their tracking ID
    const trackingId = screen.getByText(/ticket-/);
    expect(trackingId).toBeInTheDocument();
  });

  // ==================== Scenario 2: Multiple Submissions ====================
  it('should allow user to submit multiple tickets in sequence', async () => {
    const user = userEvent.setup();
    let callCount = 0;

    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/user_tickets')) {
        return Promise.resolve({
          ok: true,
          headers: { get: (name: string) => (name === 'content-type' ? 'application/json' : null) },
          json: () => Promise.resolve({ data: [] }),
        });
      }
      callCount++;
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            id: `ticket-${callCount}`,
          }),
      });
    });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    // First submission
    let textarea = screen.getByPlaceholderText(/Describe the issue.../i);
    await user.clear(textarea);
    await user.type(textarea, 'First issue');

    let submitBtn = screen.getByRole('button', { name: /submit ticket/i });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('ticket-1')).toBeInTheDocument();
    });

    // Close success modal (lands on the history tab) and return to submit form
    const viewTicketsBtn = screen.getByRole('button', { name: /View My Tickets/i });
    await user.click(viewTicketsBtn);

    await waitFor(() => {
      expect(screen.queryByText(/Ticket submitted successfully/i)).not.toBeInTheDocument();
    });

    const newTicketTab = screen.getByRole('button', { name: /New ticket/i });
    await user.click(newTicketTab);

    // Second submission
    textarea = screen.getByPlaceholderText(/Describe the issue.../i);
    await user.clear(textarea);
    await user.type(textarea, 'Second issue');

    submitBtn = screen.getByRole('button', { name: /submit ticket/i });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('ticket-2')).toBeInTheDocument();
    });

    expect(callCount).toBe(2);
  });

  // ==================== Scenario 3: Review Past Tickets ====================
  it('should allow user to review their ticket history', async () => {
    const user = userEvent.setup();

    const mockHistory = [
      {
        id: 'ticket-past-1',
        raw_text: 'Login issue',
        created_at: new Date(Date.now() - 86400000).toISOString(),
        status: 'resolved',
        resolutions: [
          {
            final_response: 'Password reset sent',
            resolved_by: 'automated',
            escalated: false,
          },
        ],
      },
    ];

    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/user_tickets')) {
        return Promise.resolve({
          ok: true,
          headers: { get: (name: string) => (name === 'content-type' ? 'application/json' : null) },
          json: () => Promise.resolve({ data: mockHistory }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ id: 'ticket-new' }),
      });
    });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    // Click on History tab
    const historyTab = screen.getByRole('button', { name: /My Tickets/i });
    await user.click(historyTab);

    // See previous ticket
    await waitFor(() => {
      expect(screen.getByText(/Login issue/i)).toBeInTheDocument();
    });

    // Verify ticket details are shown (statuses render as plain-language labels)
    expect(screen.getByText('Resolved')).toBeInTheDocument();
  });

  // ==================== Scenario 4: Retry After Error ====================
  it('should allow user to retry after submission failure', async () => {
    const user = userEvent.setup();
    let attemptCount = 0;

    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/user_tickets')) {
        return Promise.resolve({
          ok: true,
          headers: { get: (name: string) => (name === 'content-type' ? 'application/json' : null) },
          json: () => Promise.resolve({ data: [] }),
        });
      }
      attemptCount++;
      if (attemptCount === 1) {
        // First attempt fails
        return Promise.resolve({
          ok: false,
          status: 500,
          json: () =>
            Promise.resolve({ error: 'Server error' }),
        });
      }
      // Second attempt succeeds
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({ id: 'ticket-retry-success' }),
      });
    });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText(/Describe the issue.../i);
    await user.clear(textarea);
    await user.type(textarea, 'Test retry');

    let submitBtn = screen.getByRole('button', { name: /submit ticket/i });
    await user.click(submitBtn);

    // See error
    await waitFor(() => {
      expect(screen.getByText(/Failed to submit/i)).toBeInTheDocument();
    });

    // Retry
    await user.clear(textarea);
    await user.type(textarea, 'Test retry again');

    submitBtn = screen.getByRole('button', { name: /submit ticket/i });
    await user.click(submitBtn);

    // Success this time
    await waitFor(() => {
      expect(screen.getByText(/Ticket submitted successfully/i)).toBeInTheDocument();
    });

    expect(attemptCount).toBe(2);
  });

  // ==================== Scenario 5: Compose and Cancel ====================
  it('should allow user to type but not submit until ready', async () => {
    const user = userEvent.setup();
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText(/Describe the issue.../i);

    // Type some text
    await user.type(textarea, 'Drafting my issue... ');

    // Can still edit before submitting
    expect((textarea as HTMLTextAreaElement).value).toContain('Drafting');

    // Add more text
    await user.type(textarea, 'Adding more details...');

    expect((textarea as HTMLTextAreaElement).value).toContain('Adding more details');

    // The text is not submitted until the button is clicked
    expect(screen.queryByText(/Ticket submitted successfully/i)).not.toBeInTheDocument();
  });

  // ==================== Scenario 6: Image Upload Workflow ====================
  it('should handle user image upload workflow', async () => {
    const user = userEvent.setup();

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    // User describes issue
    const textarea = screen.getByPlaceholderText(/Describe the issue.../i);
    await user.clear(textarea);
    await user.type(textarea, 'Bug shown in screenshot');

    // User uploads image
    const imageFile = new File(['image'], 'bug-screenshot.png', {
      type: 'image/png',
    });

    const fileInput = screen.getByLabelText(/Attach a screenshot/i) as HTMLInputElement;
    await user.upload(fileInput, imageFile);

    // User submits
    const submitBtn = screen.getByRole('button', { name: /submit ticket/i });
    await user.click(submitBtn);

    // Success
    await waitFor(() => {
      expect(screen.getByText(/Ticket submitted successfully/i)).toBeInTheDocument();
    });
  });

  // ==================== Scenario 7: User Info Display ====================
  it('should display user information in header', async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    // Check user email is displayed
    expect(screen.getByText(mockUser.email)).toBeInTheDocument();

    // Check "Logged in as" text
    expect(screen.getByText(/Logged in as/i)).toBeInTheDocument();
  });

  // ==================== Scenario 8: Tab Persistence ====================
  it('should maintain active tab state during interactions', async () => {
    const user = userEvent.setup();

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    // Click history tab
    const historyTab = screen.getByRole('button', { name: /My Tickets/i });
    await user.click(historyTab);

    // Wait for tab to be active
    await waitFor(() => {
      const tab = screen.getByRole('button', { name: /My Tickets/i });
      // Check if it's highlighted (contains the active-tab gold gradient)
      expect(tab.className).toContain('E8A33D');
    });

    // History content should be visible
    expect(screen.getByText(/Ticket history/i)).toBeInTheDocument();
  });

  // ==================== Scenario 9: Sequential Ticket Review ====================
  it('should allow user to review and interact with multiple tickets', async () => {
    const user = userEvent.setup();

    const mockTickets = [
      {
        id: 'ticket-1',
        raw_text: 'First issue - payment',
        created_at: new Date(Date.now() - 86400000 * 2).toISOString(),
        status: 'resolved',
        resolutions: [
          {
            final_response: 'Refund processed',
            resolved_by: 'automated',
            escalated: false,
          },
        ],
      },
      {
        id: 'ticket-2',
        raw_text: 'Second issue - account',
        created_at: new Date(Date.now() - 86400000).toISOString(),
        status: 'escalated',
        resolutions: [
          {
            final_response: 'Escalated to specialist',
            resolved_by: 'escalation',
            escalated: true,
          },
        ],
      },
    ];

    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/user_tickets')) {
        return Promise.resolve({
          ok: true,
          headers: { get: (name: string) => (name === 'content-type' ? 'application/json' : null) },
          json: () => Promise.resolve({ data: mockTickets }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      });
    });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    // Go to history
    const historyTab = screen.getByRole('button', { name: /My Tickets/i });
    await user.click(historyTab);

    // See all tickets
    await waitFor(() => {
      expect(screen.getByText(/First issue/i)).toBeInTheDocument();
      expect(screen.getByText(/Second issue/i)).toBeInTheDocument();
    });

    // Can view status (statuses render as plain-language labels)
    expect(screen.getByText('Resolved')).toBeInTheDocument();
    expect(screen.getByText('Needs review')).toBeInTheDocument();
  });

  // ==================== Scenario 10: Complete Journey ====================
  it('should complete full user journey from signup to ticket review', async () => {
    const user = userEvent.setup();
    let submissionCount = 0;

    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/tickets') && url.includes('http://localhost')) {
        submissionCount++;
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: `ticket-journey-${submissionCount}`,
            }),
        });
      }
      if (url.includes('/api/user_tickets')) {
        return Promise.resolve({
          ok: true,
          headers: { get: (name: string) => (name === 'content-type' ? 'application/json' : null) },
          json: () =>
            Promise.resolve({
              data: [
                {
                  id: `ticket-journey-${submissionCount}`,
                  raw_text: 'Journey test ticket',
                  created_at: new Date().toISOString(),
                  status: 'processing',
                  resolutions: [],
                },
              ],
            }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      });
    });

    render(<DashboardPage />);

    // Step 1: User lands on dashboard
    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    expect(screen.getByText(mockUser.email)).toBeInTheDocument();

    // Step 2: User submits a ticket
    const textarea = screen.getByPlaceholderText(/Describe the issue.../i);
    await user.clear(textarea);
    await user.type(textarea, 'My complete journey test issue');

    const submitBtn = screen.getByRole('button', { name: /submit ticket/i });
    await user.click(submitBtn);

    // Step 3: See success confirmation
    await waitFor(() => {
      expect(screen.getByText(/Ticket submitted successfully/i)).toBeInTheDocument();
    });

    const trackingId = screen.getByText(/ticket-journey/);
    expect(trackingId).toBeInTheDocument();

    // Step 4: View tickets
    const viewBtn = screen.getByRole('button', { name: /View My Tickets/i });
    await user.click(viewBtn);

    // Step 5: See ticket in history
    await waitFor(() => {
      expect(screen.getByText(/Journey test/i)).toBeInTheDocument();
    });

    console.log('✅ Complete user journey test passed!');
  });
});

// ==================== ERROR RECOVERY TESTS ====================

describe('Error Recovery Workflows', () => {
  const mockUser = { id: 'user-123', email: 'test@clario.com' };

  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(useAuth).mockReturnValue({
      user: mockUser,
      role: 'user',
      loading: false,
      roleLoading: false,
    } as unknown as ReturnType<typeof useAuth>);
  });

  // ==================== Network Timeout ====================
  it('should handle network timeout gracefully', async () => {
    const user = userEvent.setup();

    global.fetch = vi.fn().mockImplementation(() =>
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Network timeout')), 50)
      )
    );

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText(/Describe the issue.../i);
    await user.clear(textarea);
    await user.type(textarea, 'Timeout test');

    const submitBtn = screen.getByRole('button', { name: /submit ticket/i });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/error|failed|unable|timeout/i)).toBeInTheDocument();
    });
  });

  // ==================== API Gateway Down ====================
  it('should handle API Gateway being down', async () => {
    const user = userEvent.setup();

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: () =>
        Promise.resolve({ error: 'Service Unavailable' }),
    });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText(/Describe the issue.../i);
    await user.clear(textarea);
    await user.type(textarea, 'Gateway down test');

    const submitBtn = screen.getByRole('button', { name: /submit ticket/i });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/Failed to submit/i)).toBeInTheDocument();
    });

    // User can retry
    const textarea2 = screen.getByPlaceholderText(/Describe the issue.../i);
    expect(textarea2).toBeInTheDocument();
  });

  // ==================== Authentication Expired ====================
  it('should handle expired authentication', async () => {
    const user = userEvent.setup();

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: () =>
        Promise.resolve({ error: 'Unauthorized' }),
    });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Clario Triage/i)).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText(/Describe the issue.../i);
    await user.clear(textarea);
    await user.type(textarea, 'Auth test');

    const submitBtn = screen.getByRole('button', { name: /submit ticket/i });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/Failed to submit/i)).toBeInTheDocument();
    });
  });
});
