'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useRouter } from 'next/navigation';
import { Clock, CheckCircle2, AlertTriangle, ArrowRight, Loader2, RefreshCw } from 'lucide-react';
import { AgentShell } from './AgentShell';
import { fetchStaffTickets } from '../../lib/agentApi';
import { reviewQueue, queueStats, ticketHeadline, ticketCategories, type QueueTicket } from '../../lib/agentQueue';
import { formatRelative } from '../../lib/datetime';
import { Badge, type BadgeTone } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { Notice } from '../../components/ui/Notice';
import { cx } from '../../lib/cx';

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
    <div className="flex min-h-dvh items-center justify-center bg-canvas">
      <Loader2 className="h-8 w-8 animate-spin text-brand" aria-hidden="true" />
    </div>
  );

  return (
    <AgentShell>
      <header className="mb-10 flex items-center justify-between">
        <div>
          <h1 className="text-h2 text-fg">Agent dashboard</h1>
          <p className="text-app text-fg-muted">Escalated tickets queue</p>
        </div>
        <Button variant="ghost" size="sm" onClick={refresh} disabled={fetching} aria-label="Refresh queue" title="Refresh" className="h-10 w-10 rounded-pill px-0">
          <RefreshCw className={cx('h-5 w-5', fetching && 'animate-spin')} aria-hidden="true" />
        </Button>
      </header>

      <div className="mb-10 grid grid-cols-1 gap-6 md:grid-cols-3">
        <StatCard icon={<AlertTriangle />} label="Needs review" value={String(stats.needsReview)} toneClass="text-warning" />
        <StatCard
          icon={<Clock />}
          label="Oldest waiting"
          value={stats.oldestWaitingSince ? formatRelative(stats.oldestWaitingSince) : '—'}
          toneClass="text-accent"
        />
        <StatCard icon={<CheckCircle2 />} label="Resolved today" value={String(stats.resolvedToday)} toneClass="text-success" />
      </div>

      <Card flush className="overflow-hidden">
        <div className="flex items-center justify-between border-b border-border p-6">
          <h2 className="text-h3 text-fg">Escalation queue</h2>
        </div>

        {error && (
          <Notice tone="danger" role="alert" className="m-6">
            <div className="flex items-center justify-between gap-4">
              <span>Could not load the queue: {error}</span>
              <Button variant="secondary" size="sm" onClick={refresh}>Try again</Button>
            </div>
          </Notice>
        )}

        {!error && fetching && tickets.length === 0 && (
          <div className="flex justify-center p-12" role="status" aria-label="Loading tickets">
            <Loader2 className="h-6 w-6 animate-spin text-brand" aria-hidden="true" />
          </div>
        )}

        <ul className="divide-y divide-border">
          {queue.map((ticket) => {
            const cls = ticket.ticket_classifications?.[0];
            const priority = cls?.priority ?? 'Unrated';
            const tone: BadgeTone = /^(urgent|critical)$/i.test(priority)
              ? 'danger'
              : /^high$/i.test(priority) ? 'warning' : 'brand';
            const iconTone = tone === 'danger' ? 'text-danger' : tone === 'warning' ? 'text-warning' : 'text-brand';
            return (
              <li key={ticket.id} className="flex flex-wrap items-center justify-between gap-4 p-6 transition-colors focus-within:bg-surface-raised hover:bg-surface-raised">
                <div className="flex min-w-0 items-start gap-4">
                  <div className={cx('rounded-lg border border-border bg-surface p-2', iconTone)}>
                    <AlertTriangle className="h-5 w-5" aria-hidden="true" />
                  </div>
                  <div className="min-w-0">
                    <h3 className="truncate text-body font-semibold text-fg">{ticketHeadline(ticket)}</h3>
                    <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-app text-fg-muted">
                      <span className="font-mono text-caption">{ticket.id.slice(0, 8)}</span>
                      {ticketCategories(ticket).map((c) => (
                        <Badge key={c}>{c}</Badge>
                      ))}
                      <span className="flex items-center"><Clock className="mr-1 h-3 w-3" aria-hidden="true" /> {formatRelative(ticket.created_at)}</span>
                      <Badge tone={tone}>Priority: {priority}</Badge>
                    </div>
                  </div>
                </div>

                <Button
                  variant="secondary"
                  onClick={() => router.push(`/agent/${ticket.id}`)}
                  aria-label={`Review ticket ${ticket.id.slice(0, 8)}`}
                  className="shrink-0"
                >
                  <span>Review</span>
                  <ArrowRight className="h-4 w-4" aria-hidden="true" />
                </Button>
              </li>
            );
          })}
        </ul>

        {!error && !fetching && queue.length === 0 && (
          <div className="p-12 text-center text-fg-muted">
            <CheckCircle2 className="mx-auto mb-3 h-12 w-12 text-success" aria-hidden="true" />
            <p>Queue is empty. Great job!</p>
          </div>
        )}
      </Card>
    </AgentShell>
  );
}

function StatCard({ icon, label, value, toneClass }: { icon: React.ReactNode, label: string, value: string, toneClass: string }) {
  return (
    <Card className="flex items-center gap-4">
      <div className={cx('rounded-lg border border-border bg-surface-raised p-3', toneClass)} aria-hidden="true">{icon}</div>
      <div>
        <p className="text-app font-medium text-fg-muted">{label}</p>
        <p className="text-h2 text-fg">{value}</p>
      </div>
    </Card>
  );
}
