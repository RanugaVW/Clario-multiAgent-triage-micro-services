import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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
      getSession: vi.fn().mockResolvedValue({ 
        data: { session: { access_token: 'mock-jwt-token' } } 
      }),
      signOut: vi.fn(),
    },
  },
}));

describe('Spring Boot API Gateway Integration', () => {
  const mockPush = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
<<<<<<< HEAD
    vi.mocked(useRouter).mockReturnValue({ push: mockPush, refresh: vi.fn() } as unknown as ReturnType<typeof useRouter>);
=======
    (useRouter as any).mockReturnValue({ push: mockPush, refresh: vi.fn() });
>>>>>>> origin/add/voice-to-text-service
    
    // Mock the initial history fetch (Next.js API route)
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/customer_tickets')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([]),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ id: 'mock-uuid-1234' }),
      });
    });
  });

  it('routes ticket submissions through the Spring Boot API Gateway instead of Supabase/Sidecar directly', async () => {
<<<<<<< HEAD
    vi.mocked(useAuth).mockReturnValue({
=======
    (useAuth as any).mockReturnValue({
>>>>>>> origin/add/voice-to-text-service
      user: { id: 'user-123', email: 'test@example.com' },
      role: 'user',
      loading: false,
      roleLoading: false,
<<<<<<< HEAD
    } as unknown as ReturnType<typeof useAuth>);
=======
    });
>>>>>>> origin/add/voice-to-text-service

    render(<DashboardPage />);
    
    // Wait for UI to render
<<<<<<< HEAD
    expect(screen.getByText(/New ticket/i)).toBeInTheDocument();

    // Fill out the form
    const issueInput = screen.getByLabelText(/Describe the issue/i);
    fireEvent.change(issueInput, { target: { value: 'My server is down' } });

    // Submit the form
    const submitBtn = screen.getByRole('button', { name: /submit ticket/i });
=======
    expect(screen.getByText(/Submit Ticket/i)).toBeInTheDocument();

    // Fill out the form
    const issueInput = screen.getByLabelText(/ISSUE_PAYLOAD/i);
    fireEvent.change(issueInput, { target: { value: 'My server is down' } });

    // Submit the form
    const submitBtn = screen.getByRole('button', { name: /PROCESS_TICKET/i });
>>>>>>> origin/add/voice-to-text-service
    fireEvent.click(submitBtn);

    // Verify the API Gateway is called correctly
    await waitFor(() => {
<<<<<<< HEAD
      const fetchCalls = vi.mocked(global.fetch).mock.calls;
      const gatewayCall = fetchCalls.find(
        (call) => String(call[0]).includes('/api/tickets') && (call[1] as RequestInit | undefined)?.method === 'POST'
      );

      expect(gatewayCall).toBeDefined();
      const init = gatewayCall![1] as RequestInit;

      // Verify the JWT is passed securely
      expect(init.headers).toHaveProperty('Authorization', 'Bearer mock-jwt-token');
      expect(init.headers).toHaveProperty('Content-Type', 'application/json');

      // Verify the payload shape exactly matches the Spring Boot CreateTicketRequest DTO
      const payload = JSON.parse(init.body as string);
=======
      const fetchCalls = (global.fetch as any).mock.calls;
      const gatewayCall = fetchCalls.find((call: any[]) => call[0].includes('/api/tickets') && call[1]?.method === 'POST');
      
      expect(gatewayCall).toBeDefined();
      
      // Verify the JWT is passed securely
      expect(gatewayCall[1].headers).toHaveProperty('Authorization', 'Bearer mock-jwt-token');
      expect(gatewayCall[1].headers).toHaveProperty('Content-Type', 'application/json');
      
      // Verify the payload shape exactly matches the Spring Boot CreateTicketRequest DTO
      const payload = JSON.parse(gatewayCall[1].body);
>>>>>>> origin/add/voice-to-text-service
      expect(payload).toEqual({
        rawText: 'My server is down',
        subject: 'Support Ticket'
      });
    });
  });
});
