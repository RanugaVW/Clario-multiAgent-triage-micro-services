import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { FeedbackStars } from '../dashboard/page';

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: vi.fn(() => ({
    user: { id: 'user-123', email: 'test@example.com' },
    role: 'user',
    loading: false,
    roleLoading: false,
  })),
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
      getSession: vi.fn().mockResolvedValue({ data: { session: { access_token: 'fake-token' } } }),
      signOut: vi.fn(),
    },
    from: vi.fn(),
  },
}));

describe('FeedbackStars', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({ data: [{ score: 4 }] }) })
    ));
  });

  it('submits the clicked score to the feedback API', async () => {
    render(<FeedbackStars ticketId="t1" userId="u1" />);

    fireEvent.click(screen.getByLabelText('Rate 4 stars'));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/customer_feedback',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ ticketId: 't1', userId: 'u1', score: 4 }),
        })
      );
    });
  });

  it('shows a thank-you message after a successful submit', async () => {
    render(<FeedbackStars ticketId="t1" userId="u1" />);

    fireEvent.click(screen.getByLabelText('Rate 4 stars'));

    await waitFor(() => {
      expect(screen.getByText(/thanks for your feedback/i)).toBeInTheDocument();
    });
  });

  it('does not submit again after a successful rating', async () => {
    render(<FeedbackStars ticketId="t1" userId="u1" />);

    fireEvent.click(screen.getByLabelText('Rate 4 stars'));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByLabelText('Rate 5 stars'));
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
