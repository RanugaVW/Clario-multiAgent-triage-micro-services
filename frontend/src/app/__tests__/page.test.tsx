import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Home from '../page';

// Mock fetch API globally
global.fetch = vi.fn();

describe('Ticket Submission Form (Home)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the form properly', () => {
    render(<Home />);
    
    expect(screen.getByLabelText(/Ticket Reference/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Customer Issue/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Submit to Pipeline/i })).toBeInTheDocument();
  });

  it('submits a ticket successfully and displays results', async () => {
    const mockResponse = {
      state: {
        category: 'Billing',
        priority: 'High',
        sentiment: 'Negative',
        routing_decision: 'billing',
        failure_type: 'none',
        escalation_triggered: false,
      },
      handoff_package: {
        reasoning_summary: 'Resolved automatically.',
      },
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    render(<Home />);
    
    const submitBtn = screen.getByRole('button', { name: /Submit to Pipeline/i });
    
    // Fire submission
    fireEvent.click(submitBtn);
    
    // Expect loading state
    expect(screen.getByText(/Processing.../i)).toBeInTheDocument();
    
    // Wait for the result to render
    await waitFor(() => {
      expect(screen.getByText(/Analysis Complete/i)).toBeInTheDocument();
    });

    // Check specific rendered elements
    expect(screen.getByText('Billing')).toBeInTheDocument();
    expect(screen.getByText('High')).toBeInTheDocument();
    expect(screen.getByText('Negative')).toBeInTheDocument();
    expect(screen.getByText('Resolved automatically.')).toBeInTheDocument();
  });

  it('handles server error gracefully', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: 'API timeout' }),
    });

    render(<Home />);
    const submitBtn = screen.getByRole('button', { name: /Submit to Pipeline/i });
    
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/Processing Error/i)).toBeInTheDocument();
      expect(screen.getByText('API timeout')).toBeInTheDocument();
    });
  });
});
