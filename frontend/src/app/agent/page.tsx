'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useRouter } from 'next/navigation';
import { Clock, CheckCircle2, AlertTriangle, ArrowRight, Loader2, RefreshCw } from 'lucide-react';
import { AgentShell } from './AgentShell';
import { fetchStaffTickets } from '../../lib/agentApi';
import { reviewQueue, queueStats, ticketHeadline, ticketCategories, type QueueTicket } from '../../lib/agentQueue';
import { formatRelative } from '../../lib/datetime';

export default function AgentDashboard() {
  const { user, role, loading } = useAuth();
  const router = useRouter();
  const [tickets, setTickets] = useState<QueueTicket[]>([]);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isStaffUser = !!user && (role === 'agent' || role === 'admin');

  useEffect(() => {
    if (loading) return;
    if (!isStaffUser) router.push('/login');
  }, [loading, isStaffUser, router]);

  // No synchronous setState here: the effect below calls it on mount, when the
  // initial state (fetching, no error) is already correct.
  const load = useCallback(async () => {
    try {
      setTickets(await fetchStaffTickets());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load tickets');
    } finally {
      setFetching(false);
    }
  }, []);

  useEffect(() => {
    if (isStaffUser) queueMicrotask(load); // keeps load()'s state updates out of the effect's synchronous body (same approach as admin/page.tsx)
  }, [isStaffUser, load]);

  const refresh = () => {
    setFetching(true);
    setError(null);
    load();
  };

  const queue = useMemo(() => reviewQueue(tickets), [tickets]);
  const stats = useMemo(() => queueStats(tickets), [tickets]);

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <Loader2 className="w-8 h-8 animate-spin text-[#E8A33D]" />
    </div>
  );

  return (
    <AgentShell>
      <header className="flex justify-between items-center mb-10 animate-fade-in">
        <div>
          <h1 className="text-2xl font-bold text-[#ECECEC]">Agent dashboard</h1>
          <p className="text-sm text-[#8A8F98]">Escalated tickets queue</p>
        </div>
        <button
          onClick={refresh}
          disabled={fetching}
          className="p-2 hover:bg-white/[0.06] rounded-full transition-colors text-[#8A8F98] hover:text-[#ECECEC] disabled:opacity-50"
          aria-label="Refresh queue"
          title="Refresh"
        >
          <RefreshCw className={`w-5 h-5 ${fetching ? 'animate-spin' : ''}`} />
        </button>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10 animate-fade-in" style={{ animationDelay: '0.1s' }}>
        <StatCard icon={<AlertTriangle />} label="Needs review" value={String(stats.needsReview)} color="text-[#FB923C]" />
        <StatCard
          icon={<Clock />}
          label="Oldest waiting"
          value={stats.oldestWaitingSince ? formatRelative(stats.oldestWaitingSince) : '—'}
          color="text-[#2DD4BF]"
        />
        <StatCard icon={<CheckCircle2 />} label="Resolved today" value={String(stats.resolvedToday)} color="text-emerald-400" />
      </div>

      <section className="glass-panel rounded-[28px] overflow-hidden animate-fade-in" style={{ animationDelay: '0.2s' }}>
        <div className="p-6 border-b border-white/10 flex justify-between items-center">
          <h2 className="text-lg font-semibold text-[#ECECEC]">Escalation queue</h2>
        </div>

        {error && (
          <div role="alert" className="m-6 bg-[#FB7185]/10 border border-[#FB7185]/30 text-[#FB7185] text-sm p-4 rounded-2xl flex items-center justify-between gap-4">
            <span>Could not load the queue: {error}</span>
            <button onClick={refresh} className="underline underline-offset-4">Try again</button>
          </div>
        )}

        {!error && fetching && tickets.length === 0 && (
          <div className="p-12 flex justify-center" role="status" aria-label="Loading tickets">
            <Loader2 className="w-6 h-6 animate-spin text-[#E8A33D]" />
          </div>
        )}

        <ul className="divide-y divide-white/10">
          {queue.map((ticket) => {
            const cls = ticket.ticket_classifications?.[0];
            const priority = cls?.priority ?? 'Unrated';
            const tone = /^(urgent|critical)$/i.test(priority)
              ? 'bg-[#FB7185]/15 text-[#FB7185]'
              : /^high$/i.test(priority) ? 'bg-[#FB923C]/15 text-[#FB923C]' : 'bg-[#E8A33D]/15 text-[#E8A33D]';
            return (
              <li key={ticket.id} className="p-6 hover:bg-white/[0.04] focus-within:bg-white/[0.04] transition-colors flex items-center justify-between gap-4">
                <div className="flex items-start space-x-4 min-w-0">
                  <div className={`p-2 rounded-lg ${tone}`}><AlertTriangle className="w-5 h-5" /></div>
                  <div className="min-w-0">
                    <h3 className="font-semibold text-[#ECECEC] truncate">{ticketHeadline(ticket)}</h3>
                    <div className="flex flex-wrap items-center text-sm text-[#8A8F98] mt-1 gap-x-4 gap-y-1">
                      <span className="font-mono text-xs">{ticket.id.slice(0, 8)}</span>
                      {ticketCategories(ticket).map((c) => (
                        <span key={c} className="px-2 py-0.5 rounded-full text-xs font-medium bg-white/[0.06]">{c}</span>
                      ))}
                      <span className="flex items-center"><Clock className="w-3 h-3 mr-1" /> {formatRelative(ticket.created_at)}</span>
                      <span>Priority: {priority}</span>
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => router.push(`/agent/${ticket.id}`)}
                  aria-label={`Review ticket ${ticket.id.slice(0, 8)}`}
                  className="bg-white/[0.06] hover:bg-[#E8A33D] focus-visible:bg-[#E8A33D] text-[#ECECEC] hover:text-[#08090D] focus-visible:text-[#08090D] p-3 rounded-xl transition-all flex items-center shrink-0"
                >
                  <span className="text-sm font-medium mr-2">Review</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </li>
            );
          })}
        </ul>

        {!error && !fetching && queue.length === 0 && (
          <div className="p-12 text-center text-[#8A8F98]">
            <CheckCircle2 className="w-12 h-12 mx-auto mb-3 text-emerald-500/50" />
            <p>Queue is empty. Great job!</p>
          </div>
        )}
      </section>
    </AgentShell>
  );
}

function StatCard({ icon, label, value, color }: { icon: React.ReactNode, label: string, value: string, color: string }) {
  return (
    <div className="glass-panel rounded-[28px] p-6 flex items-center space-x-4">
      <div className={`p-3 rounded-2xl bg-white/[0.03] border border-white/10 ${color}`}>{icon}</div>
      <div>
        <p className="text-sm font-medium text-[#8A8F98]">{label}</p>
        <p className="text-2xl font-bold text-[#ECECEC]">{value}</p>
      </div>
    </div>
  );
}
