'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Loader2, Send, CheckCircle2, Sparkles } from 'lucide-react';
import { useAuth } from '../../../contexts/AuthContext';
import { AgentShell } from '../AgentShell';
import { fetchStaffTickets, submitResolution } from '../../../lib/agentApi';
import { draftFor, isAnswered, ticketCategories, type QueueTicket } from '../../../lib/agentQueue';
import { formatDateTime } from '../../../lib/datetime';
import { Badge } from '../../../components/ui/Badge';
import { Button } from '../../../components/ui/Button';
import { Card } from '../../../components/ui/Card';
import { Notice } from '../../../components/ui/Notice';
import { Textarea } from '../../../components/ui/Input';
import { AUTH_LINK } from '../../../components/auth/AuthLayout';

type LoadState = 'loading' | 'ready' | 'missing' | 'error';

export default function AgentTicketReview() {
  const { user, role, loading } = useAuth();
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const ticketId = params?.id;

  const [state, setState] = useState<LoadState>('loading');
  const [ticket, setTicket] = useState<QueueTicket | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reply, setReply] = useState('');
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  const isStaffUser = !!user && (role === 'agent' || role === 'admin');

  useEffect(() => {
    if (loading) return;
    if (!isStaffUser) router.push('/login');
  }, [loading, isStaffUser, router]);

  // No synchronous setState here: the effect below calls it on mount, when the
  // initial state ('loading', no error) is already correct.
  const load = useCallback(async () => {
    try {
      const found = (await fetchStaffTickets()).find((t) => t.id === ticketId) ?? null;
      setTicket(found);
      setReply(found ? draftFor(found) : '');
      setState(found ? 'ready' : 'missing');
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : 'Could not load the ticket');
      setState('error');
    }
  }, [ticketId]);

  useEffect(() => {
    if (isStaffUser && ticketId) queueMicrotask(load); // same approach as admin/page.tsx
  }, [isStaffUser, ticketId, load]);

  const retry = () => {
    setState('loading');
    setLoadError(null);
    load();
  };

  const handleSend = async () => {
    if (!ticket || !reply.trim() || sending) return;
    setSending(true);
    setSendError(null);
    try {
      await submitResolution(ticket.id, reply.trim());
      setSent(true);
    } catch (e) {
      setSendError(e instanceof Error ? e.message : 'Could not send the response');
    } finally {
      setSending(false);
    }
  };

  if (loading || state === 'loading') {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-canvas" role="status" aria-label="Loading ticket">
        <Loader2 className="h-8 w-8 animate-spin text-brand" aria-hidden="true" />
      </div>
    );
  }

  const back = (
    <Link href="/agent" className="inline-flex items-center gap-2 rounded-md text-app text-fg-muted transition-colors hover:text-fg">
      <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back to queue
    </Link>
  );

  if (state === 'error' || state === 'missing' || !ticket) {
    return (
      <AgentShell><div className="max-w-3xl space-y-6">
        {back}
        <Notice tone="danger" role="alert">
          {state === 'missing' ? 'Ticket not found.' : `Could not load the ticket: ${loadError}`}
          {state === 'error' && <Button variant="secondary" size="sm" onClick={retry} className="ml-3">Try again</Button>}
        </Notice>
      </div></AgentShell>
    );
  }

  const cls = ticket.ticket_classifications?.[0];
  const alreadyResolved = isAnswered(ticket);
  const customerText = ticket.raw_text.split('[OCR EXTRACTED TEXT FROM ATTACHMENT]')[0].trim();
  const hasDraft = !!draftFor(ticket);

  return (
    <AgentShell><div className="max-w-3xl space-y-6">
      {back}

      <header>
        <h1 className="text-h2 text-fg">{ticket.subject?.trim() || 'Support ticket'}</h1>
        <p className="mt-1 text-app text-fg-muted">
          <span className="font-mono">{ticket.id}</span> · opened {formatDateTime(ticket.created_at)}
          {ticket.customer_email ? ` · ${ticket.customer_email}` : ''}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {ticketCategories(ticket).map((c) => (
            <Badge key={c}>{c}</Badge>
          ))}
          {cls?.priority && <Badge tone="warning">Priority: {cls.priority}</Badge>}
          {cls?.sentiment && <Badge>Sentiment: {cls.sentiment}</Badge>}
        </div>
      </header>

      <Card aria-labelledby="customer-message" role="region">
        <h2 id="customer-message" className="mb-3 text-app font-semibold text-fg-muted">Customer message</h2>
        <p className="whitespace-pre-wrap text-app text-fg">{customerText}</p>
      </Card>

      {sent ? (
        <Notice tone="success" role="status" focusOnMount className="space-y-4 p-6 text-center">
          <CheckCircle2 className="mx-auto h-10 w-10" aria-hidden="true" />
          <p className="font-medium">Response sent. The ticket is now resolved.</p>
          <Link href="/agent" className={AUTH_LINK}>Back to queue</Link>
        </Notice>
      ) : alreadyResolved ? (
        <Notice tone="info" role="status">
          This ticket has already been resolved, so it can no longer be answered here.
        </Notice>
      ) : (
        <Card aria-labelledby="your-response" role="region" className="space-y-4">
          <h2 id="your-response" className="flex items-center gap-2 text-app font-semibold text-fg-muted">
            Your response
            {hasDraft && <span className="inline-flex items-center gap-1 font-normal text-brand"><Sparkles className="h-3 w-3" aria-hidden="true" /> starts from the AI draft — review before sending</span>}
          </h2>
          <label htmlFor="agent-reply" className="sr-only">Response to the customer</label>
          <Textarea
            id="agent-reply"
            value={reply}
            onChange={(e) => setReply(e.target.value)}
            rows={10}
            placeholder="Write the response the customer will receive…"
          />
          {sendError && <Notice tone="danger" role="alert">{sendError}</Notice>}
          <Button size="lg" onClick={handleSend} disabled={!reply.trim() || sending} className="w-full">
            <Send className="h-4 w-4" aria-hidden="true" /> {sending ? 'Sending…' : 'Send response & resolve'}
          </Button>
        </Card>
      )}
    </div></AgentShell>
  );
}
