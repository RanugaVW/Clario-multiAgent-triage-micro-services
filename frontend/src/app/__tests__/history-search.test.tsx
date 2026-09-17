import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import DashboardPage from '../dashboard/page';
import { useAuth } from '../../contexts/AuthContext';

// UR-003: the customer's ticket history had no way to find one ticket among
// many except scrolling - this covers the new client-side search added to
// close that gap (mirrors the search already available to admins).

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: vi.fn(() => ({ push: vi.fn(), refresh: vi.fn() })),
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

const mockTicketHistoryResponse = (tickets: unknown[]) => ({
  ok: true,
  headers: { get: (name: string) => (name === 'content-type' ? 'application/json' : null) },
  json: vi.fn().mockResolvedValue({ data: tickets }),
});

const tickets = [
  { id: 'ticket-aaa111', raw_text: 'My printer will not connect to wifi', created_at: new Date().toISOString(), status: 'resolved', resolutions: [] },
  { id: 'ticket-bbb222', raw_text: 'Invoice number 4021 looks wrong', created_at: new Date().toISOString(), status: 'received', resolutions: [] },
  { id: 'ticket-ccc333', raw_text: 'Cannot reset my password', created_at: new Date().toISOString(), status: 'escalated', resolutions: [] },
];

describe('Ticket history search (UR-003)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAuth).mockReturnValue({
      user: { id: 'user-123', email: 'test@clario.com' },
      role: 'user',
      loading: false,
      roleLoading: false,
    } as unknown as ReturnType<typeof useAuth>);

    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/user_tickets')) {
        return Promise.resolve(mockTicketHistoryResponse(tickets));
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
  });

  it('filters the ticket list as the user types, and shows all tickets when cleared', async () => {
    const user = userEvent.setup();
    render(<DashboardPage />);

    await user.click(await screen.findByRole('button', { name: /My Tickets/i }));

    await waitFor(() => {
      expect(screen.getByText(/printer will not connect/i)).toBeInTheDocument();
      expect(screen.getByText(/Invoice number 4021/i)).toBeInTheDocument();
      expect(screen.getByText(/Cannot reset my password/i)).toBeInTheDocument();
    });

    const searchBox = screen.getByLabelText('Search your tickets');
    await user.type(searchBox, 'invoice');

    await waitFor(() => {
      expect(screen.getByText(/Invoice number 4021/i)).toBeInTheDocument();
      expect(screen.queryByText(/printer will not connect/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/Cannot reset my password/i)).not.toBeInTheDocument();
    });

    await user.clear(searchBox);

    await waitFor(() => {
      expect(screen.getByText(/printer will not connect/i)).toBeInTheDocument();
      expect(screen.getByText(/Invoice number 4021/i)).toBeInTheDocument();
      expect(screen.getByText(/Cannot reset my password/i)).toBeInTheDocument();
    });
  });

  it('shows a no-results message for a query that matches nothing, without claiming there is no history at all', async () => {
    const user = userEvent.setup();
    render(<DashboardPage />);

    await user.click(await screen.findByRole('button', { name: /My Tickets/i }));
    await waitFor(() => expect(screen.getByText(/printer will not connect/i)).toBeInTheDocument());

    const searchBox = screen.getByLabelText('Search your tickets');
    await user.type(searchBox, 'zzz-nothing-matches-zzz');

    await waitFor(() => {
      expect(screen.getByText(/No tickets match/i)).toBeInTheDocument();
    });
    // Must not fall back to the "you haven't submitted any tickets yet" empty state.
    expect(screen.queryByText(/haven.t submitted any tickets yet/i)).not.toBeInTheDocument();
  });
});
