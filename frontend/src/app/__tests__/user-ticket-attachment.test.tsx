import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const createSignedUrl = vi.fn(() =>
  Promise.resolve({ data: { signedUrl: 'https://signed.example.com/img.png' }, error: null })
);
vi.mock('../../lib/supabase', () => ({
  supabase: { storage: { from: () => ({ createSignedUrl }) } },
}));

import { UserTicketRow } from '../dashboard/page';

const baseTicket = {
  id: 'ticket-1',
  raw_text: 'Cannot log in to my account',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  status: 'resolved',
  subject: null,
  customer_email: null,
  resolutions: [],
  ticket_classifications: [],
  customer_feedback: null,
};

describe('UserTicketRow attachment', () => {
  it('does not fetch a signed URL before the row is expanded', () => {
    render(<UserTicketRow ticket={{ ...baseTicket, image_storage_path: 'ticket-1/original.png' }} onDelete={() => {}} userId="user-1" />);
    expect(createSignedUrl).not.toHaveBeenCalled();
  });

  it('fetches and renders the screenshot only after the row is expanded', async () => {
    render(<UserTicketRow ticket={{ ...baseTicket, image_storage_path: 'ticket-1/original.png' }} onDelete={() => {}} userId="user-1" />);
    fireEvent.click(screen.getByText(/Cannot log in to my account/));
    await waitFor(() => expect(createSignedUrl).toHaveBeenCalledWith('ticket-1/original.png', 3600));
    expect(await screen.findByAltText(/your attached screenshot/i)).toHaveAttribute('src', 'https://signed.example.com/img.png');
  });

  it('renders no attachment section when image_storage_path is null', () => {
    render(<UserTicketRow ticket={{ ...baseTicket, image_storage_path: null }} onDelete={() => {}} userId="user-1" />);
    fireEvent.click(screen.getByText(/Cannot log in to my account/));
    expect(screen.queryByAltText(/your attached screenshot/i)).not.toBeInTheDocument();
  });
});
