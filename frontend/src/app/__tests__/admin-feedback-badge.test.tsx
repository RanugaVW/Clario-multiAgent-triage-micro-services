import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ user: { id: 'admin-1' } }),
}));
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));
vi.mock('../../lib/supabase', () => ({
  supabase: { from: vi.fn(() => ({ select: () => ({ eq: () => ({ single: () => Promise.resolve({ data: null }) }) }) })) },
}));

import { TicketRow } from '../admin/page';

const baseTicket = {
  id: 'ticket-1',
  raw_text: 'Cannot log in',
  subject: null,
  customer_email: 'x@example.com',
  status: 'resolved',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  ticket_drafts: [],
  ticket_classifications: [],
  resolutions: [{ id: 'r1', final_response: 'Try resetting your password.', escalated: false, escalation_reasons: null, resolved_at: new Date().toISOString(), total_reflection_count: 0, ticket_id: 'ticket-1' }],
  response_evaluations: [],
};

describe('TicketRow customer rating badge', () => {
  it('shows the customer rating when feedback exists', () => {
    render(<TicketRow ticket={{ ...baseTicket, customer_feedback: [{ score: 5 }] } as any} role="all" />);
    // The badge lives in TicketRow's expanded detail panel (pre-existing
    // behavior, unrelated to this task), so expand the row first.
    fireEvent.click(screen.getByText('Cannot log in'));
    expect(screen.getByText(/Customer rating: 5\/5/i)).toBeInTheDocument();
  });

  it('renders no rating badge when there is no feedback yet', () => {
    render(<TicketRow ticket={{ ...baseTicket, customer_feedback: [] } as any} role="all" />);
    fireEvent.click(screen.getByText('Cannot log in'));
    expect(screen.queryByText(/Customer rating/i)).not.toBeInTheDocument();
  });
});
