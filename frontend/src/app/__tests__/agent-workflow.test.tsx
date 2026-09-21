import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import AgentDashboard from '../agent/page';
import AgentTicketReview from '../agent/[id]/page';
import { useAuth } from '../../contexts/AuthContext';

const push = vi.fn();
const mockSignOut = vi.hoisted(() => vi.fn());
let routeParams: { id: string } = { id: 'ticket-aaaa-1111' };

vi.mock('../../contexts/AuthContext', () => ({ useAuth: vi.fn() }));
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push }),
  useParams: () => routeParams,
}));
vi.mock('../../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: { access_token: 'agent-token' } } }),
      signOut: mockSignOut,
    },
  },
}));

const ticket = (over: Record<string, unknown>) => ({
  id: 'x', raw_text: 'body', subject: null, status: 'escalated',
  created_at: new Date(Date.now() - 3 * 3600_000).toISOString(),
  ticket_drafts: [], ticket_classifications: [], resolutions: [],
  ...over,
});

const TICKETS = [
  ticket({ id: 'ticket-low-0001', subject: 'Low one', ticket_classifications: [{ category: 'Refunds', priority: 'Low' }] }),
  ticket({
    id: 'ticket-aaaa-1111', subject: 'Charged twice', raw_text: 'I was charged twice\n[OCR EXTRACTED TEXT FROM ATTACHMENT]\nreceipt noise',
    customer_email: 'c@example.com',
    ticket_classifications: [{ category: 'Billing & Invoicing, Refunds', priority: 'Urgent', sentiment: 'Frustrated' }],
    ticket_drafts: [{ domain: 'billing', draft_text: 'Draft: we will refund you.' }],
  }),
  ticket({ id: 'ticket-done-0002', subject: 'Already answered', status: 'resolved', resolutions: [{ escalated: false, resolved_at: new Date().toISOString() }] }),
  ticket({ id: 'ticket-open-0003', subject: 'Still with the AI', status: 'open' }),
];

function mockFetch(handler: (url: string, init?: RequestInit) => { status?: number; body: unknown }) {
  global.fetch = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const { status = 200, body } = handler(String(url), init);
    return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
  }) as unknown as typeof fetch;
}

function asRole(role: string | null) {
  vi.mocked(useAuth).mockReturnValue({
    user: role ? { id: 'agent-1', email: 'a@example.com' } : null, role, loading: false, roleLoading: false,
  } as unknown as ReturnType<typeof useAuth>);
}

describe('Agent dashboard (UR-008 / FR-035)', () => {
  beforeEach(() => { vi.clearAllMocks(); routeParams = { id: 'ticket-aaaa-1111' }; asRole('agent'); });

  it('sits inside the shared navigation shell and signs out to /login', async () => {
    mockFetch(() => ({ body: { data: TICKETS } }));
    const user = userEvent.setup();
    render(<AgentDashboard />);
    await screen.findAllByRole('listitem');

    expect(screen.getByRole('navigation', { name: 'Main' })).toHaveTextContent('Escalation queue');
    expect(screen.getByText('a@example.com')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /sign out/i }));
    await waitFor(() => expect(push).toHaveBeenCalledWith('/login'));
    expect(mockSignOut).toHaveBeenCalled();
  });

  it('lists only real tickets that still need a human, most urgent first, with the token attached', async () => {
    mockFetch(() => ({ body: { data: TICKETS } }));
    render(<AgentDashboard />);

    const items = await screen.findAllByRole('listitem');
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent('Charged twice');
    expect(items[1]).toHaveTextContent('Low one');
    expect(screen.queryByText('Already answered')).not.toBeInTheDocument();
    expect(screen.queryByText('Still with the AI')).not.toBeInTheDocument();
    expect(screen.queryByText('SUP-1002')).not.toBeInTheDocument(); // old fabricated mock rows

    const init = vi.mocked(global.fetch).mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer agent-token');
  });

  it('derives the stat cards from the data rather than fixed numbers', async () => {
    mockFetch(() => ({ body: { data: TICKETS } }));
    render(<AgentDashboard />);
    await screen.findAllByRole('listitem');

    expect(screen.getByText('Needs review').parentElement).toHaveTextContent('2');
    expect(screen.getByText('Resolved today').parentElement).toHaveTextContent('1');
    expect(screen.queryByText('2.4 hrs')).not.toBeInTheDocument();
  });

  it('navigates to the real ticket id when Review is pressed', async () => {
    mockFetch(() => ({ body: { data: TICKETS } }));
    const user = userEvent.setup();
    render(<AgentDashboard />);

    await user.click(await screen.findByRole('button', { name: 'Review ticket ticket-a' }));
    expect(push).toHaveBeenCalledWith('/agent/ticket-aaaa-1111');
  });

  it('shows the empty state when nothing is waiting', async () => {
    mockFetch(() => ({ body: { data: [] } }));
    render(<AgentDashboard />);
    expect(await screen.findByText(/Queue is empty/)).toBeInTheDocument();
  });

  it('shows the server error with a retry instead of an empty queue when loading fails', async () => {
    let calls = 0;
    mockFetch(() => (++calls === 1 ? { status: 403, body: { error: 'Staff access required' } } : { body: { data: TICKETS } }));
    const user = userEvent.setup();
    render(<AgentDashboard />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Staff access required');
    expect(screen.queryByText(/Queue is empty/)).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findAllByRole('listitem')).toHaveLength(2);
  });

  it('sends non-staff visitors to /login and never requests tickets', async () => {
    asRole('user');
    mockFetch(() => ({ body: { data: TICKETS } }));
    render(<AgentDashboard />);

    await waitFor(() => expect(push).toHaveBeenCalledWith('/login'));
    expect(global.fetch).not.toHaveBeenCalled();
  });
});

describe('Agent queue - token markup and semantics', () => {
  beforeEach(() => { vi.clearAllMocks(); routeParams = { id: 'ticket-aaaa-1111' }; asRole('agent'); });

  it('lists queue tickets in a list and keeps the Review button labelled by ticket id', async () => {
    mockFetch(() => ({ body: { data: TICKETS } }));
    render(<AgentDashboard />);

    const items = await screen.findAllByRole('listitem');
    const list = items[0].closest('ul') as HTMLElement;
    expect(within(list).getAllByRole('listitem')).toHaveLength(2);
    expect(screen.getByRole('button', { name: 'Review ticket ticket-a' })).toBeInTheDocument();
  });

  it('shows the priority as a badge with the tone rule urgent->danger, high->warning, else brand', async () => {
    const withPriority = (id: string, priority: string) =>
      ticket({ id, subject: `Subject ${priority}`, ticket_classifications: [{ category: 'Refunds', priority }] });
    mockFetch(() => ({
      body: { data: [withPriority('ticket-u-0001', 'Urgent'), withPriority('ticket-h-0002', 'High'), withPriority('ticket-l-0003', 'Low')] },
    }));
    render(<AgentDashboard />);
    await screen.findAllByRole('listitem');

    expect(screen.getByText('Priority: Urgent').className).toMatch(/\btext-danger\b/);
    expect(screen.getByText('Priority: High').className).toMatch(/\btext-warning\b/);
    expect(screen.getByText('Priority: Low').className).toMatch(/\btext-brand\b/);
  });

  it('renders the load error as an alert with a working Try again button', async () => {
    let calls = 0;
    mockFetch(() => (++calls === 1 ? { status: 500, body: { error: 'Boom' } } : { body: { data: TICKETS } }));
    const user = userEvent.setup();
    render(<AgentDashboard />);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Could not load the queue:');
    const retry = within(alert).getByRole('button', { name: 'Try again' });
    expect(retry.tagName).toBe('BUTTON');
    await user.click(retry);
    expect(await screen.findAllByRole('listitem')).toHaveLength(2);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});

describe('Agent ticket review page (FR-035 / FR-036)', () => {
  beforeEach(() => { vi.clearAllMocks(); routeParams = { id: 'ticket-aaaa-1111' }; asRole('agent'); });

  it('shows the customer message without the OCR block and pre-fills the AI draft', async () => {
    mockFetch(() => ({ body: { data: TICKETS } }));
    render(<AgentTicketReview />);

    expect(await screen.findByRole('heading', { name: 'Charged twice' })).toBeInTheDocument();
    expect(screen.getByText('I was charged twice')).toBeInTheDocument();
    expect(screen.queryByText(/receipt noise/)).not.toBeInTheDocument();
    expect(screen.getByLabelText('Response to the customer')).toHaveValue('Draft: we will refund you.');
    expect(screen.getByText('Billing & Invoicing')).toBeInTheDocument();
  });

  it('sends the edited response through PUT /api/tickets and confirms', async () => {
    const puts: unknown[] = [];
    mockFetch((_url, init) => {
      if (init?.method === 'PUT') { puts.push(JSON.parse(String(init.body))); return { body: { success: true } }; }
      return { body: { data: TICKETS } };
    });
    const user = userEvent.setup();
    render(<AgentTicketReview />);

    const box = await screen.findByLabelText('Response to the customer');
    await user.clear(box);
    await user.type(box, 'Refund issued.');
    await user.click(screen.getByRole('button', { name: /send response/i }));

    expect(await screen.findByText(/ticket is now resolved/i)).toBeInTheDocument();
    expect(puts).toEqual([{ id: 'ticket-aaaa-1111', final_response: 'Refund issued.' }]);
  });

  it('does not allow sending an empty response', async () => {
    mockFetch(() => ({ body: { data: TICKETS } }));
    const user = userEvent.setup();
    render(<AgentTicketReview />);

    await user.clear(await screen.findByLabelText('Response to the customer'));
    expect(screen.getByRole('button', { name: /send response/i })).toBeDisabled();
  });

  it('surfaces a 409 conflict and keeps the agent’s text so nothing is lost', async () => {
    mockFetch((_url, init) =>
      init?.method === 'PUT' ? { status: 409, body: { error: 'Ticket is already resolved' } } : { body: { data: TICKETS } });
    const user = userEvent.setup();
    render(<AgentTicketReview />);

    await user.click(await screen.findByRole('button', { name: /send response/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Ticket is already resolved');
    expect(screen.getByLabelText('Response to the customer')).toHaveValue('Draft: we will refund you.');
    expect(screen.queryByText(/ticket is now resolved/i)).not.toBeInTheDocument();
  });

  it('blocks answering a ticket that is already resolved', async () => {
    routeParams = { id: 'ticket-done-0002' };
    mockFetch(() => ({ body: { data: TICKETS } }));
    render(<AgentTicketReview />);

    expect(await screen.findByText(/already been resolved/i)).toBeInTheDocument();
    expect(screen.queryByLabelText('Response to the customer')).not.toBeInTheDocument();
  });

  it('reports an unknown ticket id', async () => {
    routeParams = { id: 'nope' };
    mockFetch(() => ({ body: { data: TICKETS } }));
    render(<AgentTicketReview />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Ticket not found');
  });

  it('redirects a non-staff visitor to /login without loading anything', async () => {
    asRole(null);
    mockFetch(() => ({ body: { data: TICKETS } }));
    render(<AgentTicketReview />);
    await waitFor(() => expect(push).toHaveBeenCalledWith('/login'));
    expect(global.fetch).not.toHaveBeenCalled();
  });
});

describe('Agent ticket review page - token markup and semantics', () => {
  beforeEach(() => { vi.clearAllMocks(); routeParams = { id: 'ticket-aaaa-1111' }; asRole('agent'); });

  it('moves keyboard focus to the success notice after sending', async () => {
    mockFetch((_url, init) => (init?.method === 'PUT' ? { body: { success: true } } : { body: { data: TICKETS } }));
    const user = userEvent.setup();
    render(<AgentTicketReview />);

    await user.click(await screen.findByRole('button', { name: /send response/i }));

    const notice = await screen.findByRole('status');
    expect(notice).toHaveTextContent(/ticket is now resolved/i);
    expect(notice).toHaveFocus();
  });

  it('shows the priority and sentiment as badges', async () => {
    mockFetch(() => ({ body: { data: TICKETS } }));
    render(<AgentTicketReview />);

    const priority = await screen.findByText('Priority: Urgent');
    expect(priority.className).toMatch(/\btext-warning\b/);
    expect(screen.getByText('Sentiment: Frustrated')).toBeInTheDocument();
  });

  it('labels the reply textarea and marks the AI draft hint', async () => {
    mockFetch(() => ({ body: { data: TICKETS } }));
    render(<AgentTicketReview />);

    const box = await screen.findByLabelText('Response to the customer');
    expect(box.tagName).toBe('TEXTAREA');
    expect(box).toHaveValue('Draft: we will refund you.');
    expect(screen.getByText(/starts from the AI draft/)).toBeInTheDocument();
  });

  it('renders not-found and load errors as alerts with a way back', async () => {
    routeParams = { id: 'nope' };
    mockFetch(() => ({ body: { data: TICKETS } }));
    const first = render(<AgentTicketReview />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Ticket not found');
    expect(screen.getByRole('link', { name: /Back to queue/ })).toHaveAttribute('href', '/agent');
    first.unmount();

    routeParams = { id: 'ticket-aaaa-1111' };
    mockFetch(() => ({ status: 500, body: { error: 'Boom' } }));
    render(<AgentTicketReview />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load the ticket');
    expect(screen.getByRole('link', { name: /Back to queue/ })).toHaveAttribute('href', '/agent');
  });
});

describe('Agent pages wait for the role before deciding to redirect', () => {
  beforeEach(() => { vi.clearAllMocks(); routeParams = { id: 'ticket-aaaa-1111' }; });

  // The session resolves first and the role a moment later: user set, role still null, roleLoading true.
  const roleInFlight = () => vi.mocked(useAuth).mockReturnValue({
    user: { id: 'agent-1', email: 'a@example.com' }, role: null, loading: false, roleLoading: true,
  } as unknown as ReturnType<typeof useAuth>);

  it.each([['queue', AgentDashboard], ['review', AgentTicketReview]])('does not bounce a signed-in user to /login on the %s page while the role is loading', async (_n, Page) => {
    roleInFlight();
    mockFetch(() => ({ body: { data: TICKETS } }));
    render(<Page />);
    await new Promise((r) => setTimeout(r, 50));
    expect(push).not.toHaveBeenCalled();
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
