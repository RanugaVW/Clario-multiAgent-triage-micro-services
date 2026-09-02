import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import DashboardPage from '../dashboard/page';
import { useAuth } from '../../contexts/AuthContext';
import { supabase } from '../../lib/supabase';

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
      getSession: vi.fn().mockResolvedValue({ data: { session: { access_token: 'fake-token' } } }),
      signOut: vi.fn(),
    },
    from: vi.fn(),
  },
}));

describe('Dashboard Ticket Submission', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (useAuth as any).mockReturnValue({
      user: { id: 'user-123', email: 'test@example.com' },
      role: 'user',
      loading: false,
      roleLoading: false,
    });
    
    // Mock the initial history fetch
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue([]),
    });
  });

  it('submits raw text ticket successfully via API Gateway', async () => {
    const user = userEvent.setup();
    render(<DashboardPage />);
    
    // Clear the default text and type new text
    const textArea = screen.getByPlaceholderText(/Describe the issue.../i);
    await user.clear(textArea);
    await user.type(textArea, 'My test issue description');
    
    // Mock the fetches
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/tickets')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ id: 'uuid-1234' }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve([]),
      });
    });

    // Submit
    const submitBtn = screen.getByRole('button', { name: /submit ticket/i });
    fireEvent.submit(submitBtn.closest('form')!);
    
    await waitFor(() => {
      // Check fetch was called for api gateway
      const fetchCalls = (global.fetch as any).mock.calls;
      const gatewayCall = fetchCalls.find((call: any[]) => call[0].includes('/api/tickets') && call[1]?.method === 'POST');
      
      expect(gatewayCall).toBeDefined();
      expect(gatewayCall[1].headers['Authorization']).toBe('Bearer fake-token');
      expect(gatewayCall[1].headers['Content-Type']).toBe('application/json');
      
      const payload = JSON.parse(gatewayCall[1].body);
      expect(payload.rawText).toBe('My test issue description');
      
      // Check success modal appears
      expect(screen.getByText('Ticket submitted successfully!')).toBeInTheDocument();
      expect(screen.getByText('uuid-1234')).toBeInTheDocument();
    });
  });

  it('submits ticket with image successfully', async () => {
    const user = userEvent.setup();
    render(<DashboardPage />);
    
    // Clear default text
    const textArea = screen.getByPlaceholderText(/Describe the issue.../i);
    await user.clear(textArea);
    await user.type(textArea, 'Issue with screenshot');
    
    // Create a fake File object
    const file = new File(['hello'], 'hello.png', { type: 'image/png' });
    
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    if (fileInput) {
      await userEvent.upload(fileInput, file);
    }

    // Mock fetch for API Gateway
    global.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/tickets')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ id: 'uuid-5678' }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve([]),
      });
    });

    const submitBtn = screen.getByRole('button', { name: /submit ticket/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      // Check fetch was called for API Gateway
      const fetchCalls = (global.fetch as any).mock.calls;
      const gatewayCall = fetchCalls.find((call: any[]) => call[0].includes('/api/tickets') && call[1]?.method === 'POST');
      
      expect(gatewayCall).toBeDefined();
      
      const body = JSON.parse(gatewayCall[1].body);
      expect(body.imageBase64).toBeDefined();
      expect(body.rawText).toBe('Issue with screenshot');
    });
  });
});
