import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ user: { id: 'admin-1' } }),
}));
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

const createSignedUrl = vi.fn(() =>
  Promise.resolve({ data: { signedUrl: 'https://signed.example.com/img.png' }, error: null })
);
const fromTable = vi.fn(() => ({
  select: () => ({ eq: () => ({ single: () => Promise.resolve({ data: null }) }) }),
}));

vi.mock('../../lib/supabase', () => ({
  supabase: {
    from: (...args: unknown[]) => fromTable(...args),
    storage: { from: () => ({ createSignedUrl }) },
  },
}));

import { TicketRow, type Ticket } from '../admin/page';

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
  resolutions: [],
  response_evaluations: [],
  customer_feedback: null,
};

describe('TicketRow attachment', () => {
  it('does not fetch a signed URL before the row is expanded', () => {
    render(<TicketRow ticket={{ ...baseTicket, image_storage_path: 'ticket-1/original.png' } as unknown as Ticket} role="all" />);
    expect(createSignedUrl).not.toHaveBeenCalled();
  });

  it('fetches and renders the screenshot only after the row is expanded', async () => {
    render(<TicketRow ticket={{ ...baseTicket, image_storage_path: 'ticket-1/original.png' } as unknown as Ticket} role="all" />);
    fireEvent.click(screen.getByText('Cannot log in'));
    await waitFor(() => expect(createSignedUrl).toHaveBeenCalledWith('ticket-1/original.png', 3600));
    expect(await screen.findByAltText(/attached screenshot/i)).toHaveAttribute('src', 'https://signed.example.com/img.png');
  });

  it('renders no attachment section when image_storage_path is null', () => {
    render(<TicketRow ticket={{ ...baseTicket, image_storage_path: null } as unknown as Ticket} role="all" />);
    fireEvent.click(screen.getByText('Cannot log in'));
    expect(screen.queryByAltText(/attached screenshot/i)).not.toBeInTheDocument();
  });
});
