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
      <div className="min-h-screen flex items-center justify-center" role="status" aria-label="Loading ticket">
        <Loader2 className="w-8 h-8 animate-spin text-[#E8A33D]" />
      </div>
    );
  }

  const back = (
    <Link href="/agent" className="inline-flex items-center gap-2 text-sm text-[#8A8F98] hover:text-[#ECECEC] transition-colors">
      <ArrowLeft className="w-4 h-4" /> Back to queue
    </Link>
  );

  if (state === 'error' || state === 'missing' || !ticket) {
    return (
      <AgentShell><div className="max-w-3xl space-y-6">
        {back}
        <div role="alert" className="bg-[#FB7185]/10 border border-[#FB7185]/30 text-[#FB7185] text-sm p-4 rounded-2xl">
          {state === 'missing' ? 'Ticket not found.' : `Could not load the ticket: ${loadError}`}
          {state === 'error' && <button onClick={retry} className="ml-3 underline underline-offset-4">Try again</button>}
        </div>
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
        <h1 className="text-2xl font-bold text-[#ECECEC]">{ticket.subject?.trim() || 'Support ticket'}</h1>
        <p className="text-sm text-[#8A8F98] mt-1">
          <span className="font-mono">{ticket.id}</span> · opened {formatDateTime(ticket.created_at)}
          {ticket.customer_email ? ` · ${ticket.customer_email}` : ''}
        </p>
        <div className="flex flex-wrap gap-2 mt-3">
          {ticketCategories(ticket).map((c) => (
            <span key={c} className="px-2 py-0.5 rounded-full text-xs font-medium bg-white/[0.06] text-[#8A8F98]">{c}</span>
          ))}
          {cls?.priority && <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-[#FB923C]/15 text-[#FB923C]">Priority: {cls.priority}</span>}
          {cls?.sentiment && <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-white/[0.06] text-[#8A8F98]">Sentiment: {cls.sentiment}</span>}
        </div>
      </header>

      <section aria-labelledby="customer-message" className="glass-panel rounded-[28px] p-6">
        <h2 id="customer-message" className="text-sm font-semibold text-[#8A8F98] mb-3">Customer message</h2>
        <p className="whitespace-pre-wrap text-[#ECECEC] text-sm">{customerText}</p>
      </section>

      {sent ? (
        <div role="status" className="bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 p-6 rounded-2xl text-center space-y-4">
          <CheckCircle2 className="w-10 h-10 mx-auto" />
          <p className="font-medium">Response sent. The ticket is now resolved.</p>
          <Link href="/agent" className="underline underline-offset-4">Back to queue</Link>
        </div>
      ) : alreadyResolved ? (
        <div role="status" className="bg-white/[0.04] border border-white/10 text-[#8A8F98] p-6 rounded-2xl text-sm">
          This ticket has already been resolved, so it can no longer be answered here.
        </div>
      ) : (
        <section aria-labelledby="your-response" className="glass-panel rounded-[28px] p-6 space-y-4">
          <h2 id="your-response" className="text-sm font-semibold text-[#8A8F98] flex items-center gap-2">
            Your response
            {hasDraft && <span className="inline-flex items-center gap-1 text-[#E8A33D] font-normal"><Sparkles className="w-3 h-3" /> starts from the AI draft — review before sending</span>}
          </h2>
          <label htmlFor="agent-reply" className="sr-only">Response to the customer</label>
          <textarea
            id="agent-reply"
            value={reply}
            onChange={(e) => setReply(e.target.value)}
            rows={10}
            className="glass-input w-full rounded-2xl px-4 py-3.5 text-sm placeholder-white/40 resize-y"
            placeholder="Write the response the customer will receive…"
          />
          {sendError && (
            <div role="alert" className="bg-[#FB7185]/10 border border-[#FB7185]/30 text-[#FB7185] text-sm p-3 rounded-xl">{sendError}</div>
          )}
          <button
            onClick={handleSend}
            disabled={!reply.trim() || sending}
            className="w-full inline-flex items-center justify-center gap-2 rounded-2xl px-6 py-3.5 font-semibold bg-gradient-to-r from-[#E8A33D] to-[#F4B856] text-[#08090D] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="w-4 h-4" /> {sending ? 'Sending…' : 'Send response & resolve'}
          </button>
        </section>
      )}
    </div></AgentShell>
  );
}
