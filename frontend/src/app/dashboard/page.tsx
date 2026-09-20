'use client';

import { useState, useEffect, useCallback } from 'react';
import { Bot, Send, Ticket, CheckCircle2, ShieldAlert, Cpu, History, Star } from 'lucide-react';

import { formatDate, formatDateTime, formatElapsed, formatRelative, formatTime } from '../../lib/datetime';
import { priorityColor } from '../../lib/classification';
import { StatusBadge } from '../../components/ui';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { FormField } from '../../components/ui/FormField';
import { Textarea, Input } from '../../components/ui/Input';
import { ConfirmDialog, Modal } from '../../components/ui/Modal';
import { Notice } from '../../components/ui/Notice';
import { AppShell, type ShellLink, type ShellNavItem } from '../../components/AppShell';
import { theme } from '../../theme/theme.config';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8600';

function parseCustomerResponse(text: string | null | undefined): string {
  if (!text) return 'No final response was produced.';
  if (text.includes('**[CUSTOMER RESPONSE]**')) {
    return text.split('**[CUSTOMER RESPONSE]**')[1].trim();
  }
  return text;
}

// UR-002: the gateway now returns a descriptive JSON body on failure
// ({"error": "...", "details": "..."} - see FR-005/REL-002), but a plain
// "Failed to submit ticket" swallowed that entirely. Exported for direct
// testing since it's pure request/response -> message logic with no React
// state involved.
export async function describeSubmitFailure(res: Response): Promise<string> {
  let message = res.status >= 500
    ? "The support system is temporarily unavailable. Please try again in a moment."
    : "We couldn't submit your ticket. Please check your details and try again.";
  let reference = '';
  try {
    const body = await res.json();
    if (typeof body?.error === 'string') {
      message = body.details ? `${body.error}: ${body.details}` : body.error;
    }
    // SUP-005: the backend tags every error with a reference that also appears
    // on its log lines - quoting it lets support find the cause without the
    // response ever exposing internals.
    if (typeof body?.reference === 'string' && body.reference) {
      reference = ` (reference: ${body.reference})`;
    }
  } catch {
    // Response wasn't JSON (or had no body) - keep the fallback message.
  }
  return message + reference;
}


type TicketState = {
  category?: string;
  priority?: string;
  sentiment?: string;
  routing_decision?: string;
  failure_type?: string;
  escalation_triggered?: boolean;
  ticket_id?: string;
};

type HandoffPackage = {
  reasoning_summary?: string;
};

type TicketResponse = {
  state: TicketState;
  handoff_package?: HandoffPackage;
  final_response?: string;
  detail?: string;
};

type TicketWithResolution = {
  id: string;
  raw_text: string;
  created_at: string;
  updated_at?: string | null;
  status: string;
  subject?: string | null;
  customer_email?: string | null;
  resolutions: {
    final_response: string;
    resolved_by: string;
    escalated: boolean;
    resolved_at?: string | null;
    total_latency_ms?: number | null;
  }[];
  ticket_classifications?: {
    category: string | null;
    priority: string | null;
    sentiment: string | null;
    confidence: number | null;
  }[];
  // ticket_id carries a UNIQUE constraint, so PostgREST embeds this as a
  // to-one relation (a bare object or null) rather than an array.
  customer_feedback?: { score: number } | null;
  image_storage_path?: string | null;
};

import { useAuth } from '../../contexts/AuthContext';
import { supabase } from '../../lib/supabase';
import { useRouter } from 'next/navigation';
import MorphButton from '../../components/MorphButton';
import ShakeButton from '../../components/ShakeButton';
import RotateButton from '../../components/RotateButton';
import VoiceRecorder from '../../components/VoiceRecorder';
import { fetchJson } from '../../lib/fetchJson';

export default function Home() {
  const [ticketText, setTicketText] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<TicketResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pastTickets, setPastTickets] = useState<TicketWithResolution[]>([]);
  const [activeTab, setActiveTab] = useState<'new' | 'history'>('new');
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [successModal, setSuccessModal] = useState<{show: boolean, trackingId: string}>({show: false, trackingId: ''});
  const [dataLoading, setDataLoading] = useState(false);
  const [ticketPendingDelete, setTicketPendingDelete] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historySearch, setHistorySearch] = useState('');
  const { user, role, loading, roleLoading } = useAuth();
  const router = useRouter();

  const fetchHistory = useCallback(async () => {
    if (!user) return;
    setDataLoading(true);
    try {
      const { data: sessionData } = await supabase.auth.getSession();
      const token = sessionData.session?.access_token;
      const json = await fetchJson<{ data: TicketWithResolution[] }>(`/api/user_tickets?userId=${user.id}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setPastTickets(json.data || []);
    } catch (e) {
      console.error('Failed to fetch history:', e);
    } finally {
      setDataLoading(false);
    }
  }, [user]);

  // UR-006: the native confirm()/alert() this used to call block the whole
  // page, can't be styled, and aren't reliably announced by screen readers.
  // Clicking delete now only opens the ConfirmDialog rendered further down;
  // the actual delete request runs in confirmTicketDeletion below.
  const handleDeleteTicket = (ticketId: string) => {
    setTicketPendingDelete(ticketId);
  };

  const confirmTicketDeletion = async () => {
    const ticketId = ticketPendingDelete;
    if (!ticketId) return;
    setTicketPendingDelete(null);
    setHistoryError(null);
    try {
      const { data: sessionData } = await supabase.auth.getSession();
      const token = sessionData.session?.access_token;
      const res = await fetch(`${API_URL}/customer_tickets/${ticketId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        fetchHistory(); // refresh UI
        // If the deleted ticket was the currently displayed result, clear it
        if (result && result.state.ticket_id === ticketId) {
          setResult(null);
        }
      } else {
        setHistoryError("Failed to delete the ticket.");
      }
    } catch (e) {
      console.error('Failed to delete ticket:', e);
      setHistoryError("Failed to delete the ticket.");
    }
  };

  useEffect(() => {
    const fullyLoaded = !loading && !roleLoading;
    if (!fullyLoaded) return;
    if (!user) {
      router.push('/login');
    } else if (role === 'admin') {
      router.push('/admin');
    } else {
      // fetchHistory sets state synchronously as its first step; deferring
      // the call to a microtask keeps that update out of this effect's own
      // synchronous execution (avoids a same-tick cascading render).
      queueMicrotask(fetchHistory);
    }
  }, [user, role, loading, roleLoading, router, fetchHistory]);

  const handleLogout = async () => {
    await supabase.auth.signOut();
    router.refresh();
  };

  if (loading || roleLoading || !user) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-canvas">
        <div role="status" aria-label="Loading" className="h-12 w-12 animate-spin rounded-full border-4 border-border border-t-brand" />
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsProcessing(true);
    setError(null);
    setResult(null);

    try {
      let base64String = null;
      if (imageFile) {
        base64String = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onloadend = () => {
            const result = reader.result as string;
            // Remove the data:image/png;base64, prefix
            const base64 = result.split(',')[1];
            resolve(base64);
          };
          reader.onerror = reject;
          reader.readAsDataURL(imageFile);
        });
      }

      let ticketUuid = crypto.randomUUID();
      const GATEWAY_URL = process.env.NEXT_PUBLIC_GATEWAY_URL || 'http://localhost:8080';
      const TRACE_RELAY_URL = process.env.NEXT_PUBLIC_TRACE_RELAY_URL || 'http://localhost:8700';
      const traceEnabled = process.env.NEXT_PUBLIC_TRACE_ENABLED === 'true';
      const correlationId = crypto.randomUUID();

      if (traceEnabled) {
        fetch(`${TRACE_RELAY_URL}/trace/event`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ticket_id: correlationId,
            correlation_id: correlationId,
            service: 'frontend',
            step: 'submit',
            status: 'done',
            detail: {},
          }),
        }).catch(() => {});
      }

      if (user) {
        const { data: sessionData } = await supabase.auth.getSession();
        const token = sessionData.session?.access_token;

        // Send request to Spring Boot API Gateway
        const res = await fetch(`${GATEWAY_URL}/api/v1/tickets`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
            ...(traceEnabled ? { 'X-Trace-Correlation-Id': correlationId } : {})
          },
          body: JSON.stringify({
            rawText: ticketText,
            subject: "Support Ticket",
            imageBase64: base64String || undefined
          }),
        });

        if (!res.ok) {
          // UR-002: surface whatever descriptive message the backend actually
          // sent (e.g. FR-005's validation details, or REL-002's "temporarily
          // unavailable, try again shortly") instead of a generic, unhelpful
          // one-liner that discarded it entirely.
          throw new Error(await describeSubmitFailure(res));
        }

        const data = await res.json();
        ticketUuid = data.id; // Use the UUID generated by the backend database
      } else {
        throw new Error("You need to be logged in to submit a ticket. Please sign in and try again.");
      }

        // Success!
        setSuccessModal({ show: true, trackingId: ticketUuid });
        setTicketText('');
        setImageFile(null);
        if (user) fetchHistory();
        setActiveTab('history');

    } catch (err: unknown) {
      if (err instanceof TypeError) {
        // fetch() itself rejects with a TypeError for network-level failures
        // (DNS, connection refused, offline) - there's no response to read a
        // message from, so give a corrective instruction instead of the raw
        // "Failed to fetch" browser message.
        setError("Couldn't reach the support system. Check your connection and try again.");
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('An unexpected error occurred while submitting your ticket. Please try again.');
      }
    } finally {
      setIsProcessing(false);
    }
  };

  // UR-003: with no search, finding one ticket in a long history meant
  // scrolling through all of them. Matches subject, description, and
  // ticket-ID prefix, mirroring the search already available to admins.
  const historySearchLower = historySearch.trim().toLowerCase();
  const filteredPastTickets = historySearchLower
    ? pastTickets.filter(t =>
        t.raw_text.toLowerCase().includes(historySearchLower) ||
        (t.subject ?? '').toLowerCase().includes(historySearchLower) ||
        t.id.toLowerCase().includes(historySearchLower))
    : pastTickets;

  const dashboardNavItems: { id: 'new' | 'history'; icon: React.ReactNode; label: string }[] = [
    { id: 'new', icon: <Ticket className="w-4 h-4" />, label: 'New ticket' },
    { id: 'history', icon: <History className="w-4 h-4" />, label: `My tickets${pastTickets.length > 0 ? ` (${pastTickets.length})` : ''}` },
  ];

  const navItems: ShellNavItem[] = dashboardNavItems.map((item) => ({
    key: item.id,
    label: item.label,
    icon: item.icon,
    active: activeTab === item.id,
    onClick: () => { if (item.id === 'history') fetchHistory(); setActiveTab(item.id); },
  }));
  const footerLinks: ShellLink[] = [
    ...(role === 'admin' ? [{ key: 'admin', label: 'Admin panel', icon: <ShieldAlert className="w-4 h-4" />, href: '/admin', tone: 'brand' as const }] : []),
    ...(role === 'agent' ? [{ key: 'agent', label: 'Agent workspace', icon: <Bot className="w-4 h-4" />, href: '/agent', tone: 'success' as const }] : []),
  ];

  const closeSuccess = () => {
    setSuccessModal({ show: false, trackingId: '' });
    setActiveTab('history');
    if (user) fetchHistory();
  };

  return (
    <AppShell
      brand={{
        icon: <Cpu className="h-5 w-5" aria-hidden="true" />,
        title: <h1 className="text-fg">{`${theme.brand.name} Triage`}</h1>,
        subtitle: 'Support ticket portal',
      }}
      nav={navItems}
      links={footerLinks}
      email={user?.email}
      onSignOut={handleLogout}
      mainClassName="flex flex-col items-center lg:py-12"
    >
      <Modal open={successModal.show} onClose={closeSuccess} title="Ticket submitted successfully!">
        <div className="flex flex-col">
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-pill border border-success/40 bg-surface text-success">
            <CheckCircle2 className="h-6 w-6" aria-hidden="true" />
          </div>
          <p className="mb-6 text-app text-fg-muted">Your issue has been securely logged and is being routed by our LangGraph orchestration.</p>

          <div className="flex w-full flex-col items-center rounded-lg border border-border bg-surface p-4">
            <span className="mb-2 text-caption font-semibold text-fg-muted">Tracking ID</span>
            <div className="flex w-full flex-wrap items-center justify-center gap-3">
              <span className="break-all font-mono text-mono text-accent">{successModal.trackingId}</span>
              <MorphButton textToCopy={successModal.trackingId} label="Copy ID" />
            </div>
          </div>

          <Button className="mt-6 w-full" onClick={closeSuccess}>
            View my tickets
          </Button>
        </div>
      </Modal>

      <ConfirmDialog
        open={ticketPendingDelete !== null}
        title="Delete this ticket?"
        message="This will immediately stop processing and cannot be undone."
        confirmLabel="Delete ticket"
        onConfirm={confirmTicketDeletion}
        onCancel={() => setTicketPendingDelete(null)}
      />

      <p className="mx-auto mb-10 w-full max-w-2xl text-center text-body-lg text-fg-muted">
        Submit a support ticket and watch our LangGraph orchestration securely classify, route, and resolve issues in real-time.
      </p>

      {activeTab === 'new' && (
        <Card raised className="w-full max-w-2xl p-8">
          <h2 className="mb-8 flex items-center gap-3 border-b border-border pb-4 text-h3 text-fg">
            <Ticket className="h-5 w-5 text-accent" aria-hidden="true" />
            Submit a ticket
          </h2>

          {error && (
            <Notice tone="danger" role="alert" className="mb-6">
              {error}
            </Notice>
          )}

          <form onSubmit={handleSubmit} className="space-y-8">
            <FormField label="Describe the issue">
              {(field) => (
                <Textarea
                  {...field}
                  required
                  value={ticketText}
                  onChange={(e) => setTicketText(e.target.value)}
                  placeholder="Describe the issue, or dictate it with the microphone below..."
                  className="h-40"
                />
              )}
            </FormField>

            <div className="flex flex-col gap-2">
              <p className="text-app font-medium text-fg">Or use voice input</p>
              <VoiceRecorder value={ticketText} onValueChange={setTicketText} disabled={isProcessing} />
            </div>

            <FormField label="Attach a screenshot (optional)">
              {({ id }) => (
                <>
                  <input
                    id={id}
                    type="file"
                    accept="image/*"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        setImageFile(e.target.files[0]);
                      }
                    }}
                    className="w-full rounded-lg border border-border-strong bg-surface p-2 text-app text-fg-muted file:mr-4 file:rounded-md file:border file:border-border-strong file:bg-surface-raised file:px-3 file:py-1.5 file:text-small file:text-fg hover:file:bg-brand-soft"
                  />
                  {imageFile && <p className="font-mono text-caption text-accent">Attached: {imageFile.name}</p>}
                </>
              )}
            </FormField>

            <Button type="submit" size="lg" disabled={isProcessing} className="w-full">
              <span>{isProcessing ? 'Submitting…' : 'Submit ticket'}</span>
              {!isProcessing && <Send className="h-4 w-4" aria-hidden="true" />}
            </Button>
          </form>
        </Card>
      )}

      {activeTab === 'history' && (
        <div className="mx-auto w-full max-w-6xl pb-12">
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
            <h2 className="flex items-center gap-3 text-h3 text-fg">
              <History className="h-5 w-5 text-accent" aria-hidden="true" /> Ticket history
            </h2>
            <div className="flex items-center gap-3">
              {pastTickets.length > 0 && (
                <Input
                  type="text"
                  placeholder="Search your tickets…"
                  value={historySearch}
                  onChange={(e) => setHistorySearch(e.target.value)}
                  aria-label="Search your tickets"
                  className="w-full sm:w-64"
                />
              )}
              <RotateButton onClick={fetchHistory} isLoading={dataLoading} />
            </div>
          </div>
          {historyError && (
            <Notice tone="danger" role="alert" className="mb-6">
              {historyError}
            </Notice>
          )}
          {pastTickets.length === 0 ? (
            <Card className="py-16 text-center">
              <Ticket className="mx-auto mb-4 h-12 w-12 text-fg-subtle" aria-hidden="true" />
              <p className="text-body-lg text-fg-muted">You haven&apos;t submitted any tickets yet.</p>
              <Button variant="secondary" className="mt-6" onClick={() => setActiveTab('new')}>
                Submit your first ticket
              </Button>
            </Card>
          ) : filteredPastTickets.length === 0 ? (
            <Card className="py-16 text-center">
              <p className="text-body-lg text-fg-muted">No tickets match &quot;{historySearch}&quot;.</p>
            </Card>
          ) : (
            <div className="flex w-full flex-col gap-2">
              {filteredPastTickets.map((t) => (
                <UserTicketRow key={t.id} ticket={t} onDelete={handleDeleteTicket} userId={user?.id || ''} />
              ))}
            </div>
          )}
        </div>
      )}

      <footer className="mt-16 w-full border-t border-border pt-6 text-center text-app text-fg-muted">
        <p>{`© ${new Date().getFullYear()} ${theme.brand.name}`}</p>
      </footer>
    </AppShell>
  );
}

// ─── UserTicketRow ──────────────────────────────────────────────────────────

import { ChevronDown, ChevronUp } from 'lucide-react';
import { WavePhysicsLoader } from '../../components/WavePhysicsLoader';

export function UserTicketRow({ ticket, onDelete, userId }: { ticket: TicketWithResolution; onDelete: (id: string) => void; userId: string }) {
  const [expanded, setExpanded] = useState(false);
  const [signedImageUrl, setSignedImageUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!expanded || signedImageUrl || !ticket.image_storage_path) return;
    supabase.storage.from('ticket-attachments').createSignedUrl(ticket.image_storage_path, 3600).then(({ data }) => {
      if (data?.signedUrl) setSignedImageUrl(data.signedUrl);
    });
  }, [expanded, signedImageUrl, ticket.image_storage_path]);

  const finalResolution = ticket.resolutions?.find(r => r.escalated === false);
  const isFullyResolved = ticket.status === 'resolved' || !!finalResolution;
  const isEscalated = !isFullyResolved && (ticket.status === 'escalated' || ticket.resolutions?.some(r => r.escalated));

  let statusColor = '#8A8F98';
  let statusLabel = 'In progress';
  let statusTone: 'neutral' | 'warning' | 'success' = 'neutral';
  if (isEscalated) { statusColor = '#FB923C'; statusLabel = 'Needs review'; statusTone = 'warning'; }
  else if (isFullyResolved) { statusColor = '#34D399'; statusLabel = 'Resolved'; statusTone = 'success'; }

  const issueSnippet = ticket.raw_text.substring(0, 80) + (ticket.raw_text.length > 80 ? '...' : '');
  const classification = ticket.ticket_classifications?.[0];
  const resolvedAt = finalResolution?.resolved_at || ticket.resolutions?.find(r => r.resolved_at)?.resolved_at || null;
  // The pipeline never stamps resolved_by, so an escalation that later closed is the
  // reliable sign a person took the ticket over.
  const wasEscalatedAtSomePoint = !!ticket.resolutions?.some(r => r.escalated);
  const handledBy = isFullyResolved
    ? ((finalResolution?.resolved_by || wasEscalatedAtSomePoint) ? 'Support agent' : 'Clario AI')
    : (isEscalated ? 'Support agent (in progress)' : 'Clario AI (in progress)');

  return (
    <div className="rounded-2xl backdrop-blur-md bg-white/[0.03] border border-white/[0.08] mb-2 transition-all duration-200 hover:border-white/20 overflow-hidden">
      {/* Unexpanded Row */}
      <div
        className="flex items-center justify-between p-4 cursor-pointer select-none"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center space-x-6 flex-1 min-w-0">
          <div className="flex items-center space-x-3 w-36 shrink-0">
            <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: statusColor }} />
            <span className="text-xs font-mono text-[#8A8F98] truncate">{ticket.id.split('-')[0]}</span>
          </div>
          <div className="w-28 shrink-0 leading-tight" title={"Submitted " + formatDateTime(ticket.created_at)}>
            <span className="text-[11px] text-[#ECECEC] font-mono block">{formatDate(ticket.created_at)}</span>
            <span className="text-[11px] text-[#8A8F98] font-mono block">{formatTime(ticket.created_at)} · {formatRelative(ticket.created_at)}</span>
          </div>
          <span className="text-sm text-[#ECECEC] truncate font-sans">{issueSnippet}</span>
        </div>

        <div className="flex items-center space-x-6 shrink-0 pl-4">
          <StatusBadge label={statusLabel} tone={statusTone} />
          <ShakeButton onDelete={(e) => { e.stopPropagation(); onDelete(ticket.id); }} />
          {expanded ? <ChevronUp className="w-4 h-4 text-[#8A8F98]" /> : <ChevronDown className="w-4 h-4 text-[#8A8F98]" />}
        </div>
      </div>

      {/* Expanded Details */}
      {expanded && (
        <div className="border-t border-white/10 p-6 space-y-6">

          {/* Ticket facts, not just the clock time it came in */}
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
            <span className="text-xs text-[#8A8F98] block mb-3">Ticket details</span>
            <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-x-6 gap-y-4">
              <UserMetaItem label="Reference" value={ticket.id.split('-')[0].toUpperCase()} mono title={ticket.id} />
              <UserMetaItem label="Status" value={statusLabel} color={statusColor} />
              <UserMetaItem label="Subject" value={ticket.subject || 'No subject'} />
              <UserMetaItem label="Submitted" value={formatDateTime(ticket.created_at)} hint={formatRelative(ticket.created_at)} />
              <UserMetaItem
                label="Last update"
                value={ticket.updated_at ? formatDateTime(ticket.updated_at) : '—'}
                hint={ticket.updated_at ? formatRelative(ticket.updated_at) : undefined}
              />
              <UserMetaItem
                label={resolvedAt ? 'Resolved' : 'Resolution'}
                value={resolvedAt ? formatDateTime(resolvedAt) : (isEscalated ? 'With a human agent' : 'Being processed')}
                hint={resolvedAt ? 'Took ' + formatElapsed(ticket.created_at, resolvedAt) : undefined}
                color={resolvedAt ? '#34D399' : statusColor}
              />
              {classification?.category && (
                <UserMetaItem label="Category" value={classification.category} mono />
              )}
              {classification?.priority && (
                <UserMetaItem
                  label="Priority"
                  value={classification.priority}
                  mono
                  color={priorityColor(classification.priority)}
                />
              )}
              <UserMetaItem label="Handled by" value={handledBy} />
            </div>
          </div>

          {signedImageUrl && (
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
              <span className="text-xs text-[#8A8F98] block mb-3">Your attached screenshot</span>
              <img src={signedImageUrl} alt="Your attached screenshot" className="max-w-full rounded-lg border border-white/10" />
            </div>
          )}

          <div>
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs text-[#8A8F98] block">Your message</span>
              <MorphButton textToCopy={ticket.id} label="Copy ID" />
            </div>
            <p className="text-sm text-[#ECECEC] leading-relaxed font-sans whitespace-pre-wrap">&quot;{ticket.raw_text}&quot;</p>
          </div>

          <div className="border-t border-white/10 pt-4">
            <span className="text-xs block mb-2" style={{ color: statusColor }}>Resolution</span>
            <div className="rounded-2xl bg-white/[0.03] border border-white/10 p-4 min-h-[100px] font-sans text-sm text-[#ECECEC]">
              {(isFullyResolved && finalResolution?.final_response)
                ? parseCustomerResponse(finalResolution.final_response)
                : (isEscalated
                    ? 'A human agent has taken over this ticket and is currently drafting a resolution.'
                    : <div className="flex justify-center items-center py-8"><WavePhysicsLoader /></div>
                  )}
            </div>
            {isFullyResolved && finalResolution?.final_response && (
              <FeedbackStars ticketId={ticket.id} userId={userId} existingScore={ticket.customer_feedback?.score ?? null} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function FeedbackStars({
  ticketId,
  userId,
  existingScore = null,
}: {
  ticketId: string;
  userId: string;
  existingScore?: number | null;
}) {
  const [hovered, setHovered] = useState<number | null>(null);
  // The actual given rating (from a prior visit, or just submitted) - not
  // just a submitted flag, so the stars can stay colored to show it rather
  // than reverting to blank outlines once the mouse leaves.
  const [score, setScore] = useState<number | null>(existingScore);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleRate = async (n: number) => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      const { data: sessionData } = await supabase.auth.getSession();
      const token = sessionData.session?.access_token;
      const res = await fetch('/api/customer_feedback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ ticketId, userId, score: n }),
      });
      if (res.ok) setScore(n);
    } catch (e) {
      console.error('Failed to submit feedback', e);
    } finally {
      setIsSubmitting(false);
    }
  };

  const displayed = hovered ?? score ?? 0;

  return (
    <div className="mt-3">
      <div className="flex items-center gap-1">
        <span className="text-xs text-[#8A8F98] mr-2">Rate this response</span>
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            aria-label={`Rate ${n} stars`}
            onMouseEnter={() => setHovered(n)}
            onMouseLeave={() => setHovered(null)}
            onClick={() => handleRate(n)}
            disabled={isSubmitting}
            className="disabled:opacity-50"
          >
            <Star
              className="w-4 h-4"
              fill={displayed >= n ? '#E8A33D' : 'none'}
              stroke="#E8A33D"
            />
          </button>
        ))}
      </div>
      {score != null && (
        <p className="text-xs text-[#2DD4BF] mt-1">
          Thanks for your feedback! You rated this {score}/5 - click a star to change it.
        </p>
      )}
    </div>
  );
}

/** One label/value pair in the customer-facing ticket detail grid. */
function UserMetaItem({ label, value, hint, color, mono, title }: {
  label: string; value: string; hint?: string; color?: string; mono?: boolean; title?: string;
}) {
  return (
    <div className="min-w-0">
      <span className="text-xs text-[#8A8F98] block mb-1">{label}</span>
      <span
        className={`text-sm block truncate ${mono ? 'font-mono' : 'font-sans'}`}
        style={{ color: color || '#ECECEC' }}
        title={title || value}
      >
        {value}
      </span>
      {hint && <span className="text-xs text-[#8A8F98] block mt-0.5">{hint}</span>}
    </div>
  );
}
