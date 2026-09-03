'use client';

import { useState, useEffect } from 'react';
import { Bot, Send, Ticket, AlertCircle, CheckCircle2, ShieldAlert, Cpu, History, X, Clock, CheckCircle, Trash2, Copy, LogOut, Star } from 'lucide-react';

import { formatDate, formatDateTime, formatElapsed, formatRelative, formatTime } from '../../lib/datetime';
import { GlassPanel, GlassButton, GlassTextarea, Modal, StatusBadge } from '../../components/ui';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8600';

function parseCustomerResponse(text: string | null | undefined): string {
  if (!text) return 'No final response was produced.';
  if (text.includes('**[CUSTOMER RESPONSE]**')) {
    return text.split('**[CUSTOMER RESPONSE]**')[1].trim();
  }
  return text;
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
  const [ticketText, setTicketText] = useState('Payment failed but the money was taken from my bank account.');
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<TicketResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pastTickets, setPastTickets] = useState<TicketWithResolution[]>([]);
  const [activeTab, setActiveTab] = useState<'new' | 'history'>('new');
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imageBase64, setImageBase64] = useState<string | null>(null);
  const [successModal, setSuccessModal] = useState<{show: boolean, trackingId: string}>({show: false, trackingId: ''});
  const [dataLoading, setDataLoading] = useState(false);
  const { user, role, loading, roleLoading } = useAuth();
  const router = useRouter();

  const fetchHistory = async () => {
    if (!user) return;
    setDataLoading(true);
    try {
      const json = await fetchJson(`/api/user_tickets?userId=${user.id}`);
      setPastTickets(json.data || []);
    } catch (e) {
      console.error('Failed to fetch history:', e);
    } finally {
      setDataLoading(false);
    }
  };

  const handleDeleteTicket = async (ticketId: string) => {
    if (!confirm("Are you sure you want to delete this ticket? This will immediately stop processing.")) return;
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
        alert("Failed to delete the ticket.");
      }
    } catch (e) {
      console.error('Failed to delete ticket:', e);
      alert("Failed to delete the ticket.");
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
      fetchHistory();
    }
  }, [user, role, loading, roleLoading, router]);

  const handleLogout = async () => {
    await supabase.auth.signOut();
    router.refresh();
  };

  if (loading || roleLoading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-16 h-16 border-4 border-[#E8A33D]/20 border-t-[#E8A33D] rounded-full animate-spin"></div>
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
      const GATEWAY_URL = 'http://localhost:8080';

      if (user) {
        const { data: sessionData } = await supabase.auth.getSession();
        const token = sessionData.session?.access_token;

        // Send request to Spring Boot API Gateway
        const res = await fetch(`${GATEWAY_URL}/api/tickets`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {})
          },
          body: JSON.stringify({
            rawText: ticketText,
            subject: "Support Ticket",
            imageBase64: base64String || undefined
          }),
        });

        if (!res.ok) {
          throw new Error("Failed to submit ticket to API Gateway");
        }

        const data = await res.json();
        ticketUuid = data.id; // Use the UUID generated by the backend database
      } else {
        throw new Error("Must be logged in to submit ticket");
      }

        // Success!
        setSuccessModal({ show: true, trackingId: ticketUuid });
        setTicketText('');
        setImageFile(null);
        setImageBase64(null);
        if (user) fetchHistory();
        setActiveTab('history');

    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred while connecting to the sidecar.');
    } finally {
      setIsProcessing(false);
    }
  };

  const dashboardNavItems: { id: 'new' | 'history'; icon: React.ReactNode; label: string }[] = [
    { id: 'new', icon: <Ticket className="w-4 h-4" />, label: 'New ticket' },
    { id: 'history', icon: <History className="w-4 h-4" />, label: `My tickets${pastTickets.length > 0 ? ` (${pastTickets.length})` : ''}` },
  ];

  return (
    <div className="min-h-screen flex flex-col lg:flex-row">

      {/* Success Modal */}
      <Modal
        open={successModal.show}
        onClose={() => { setSuccessModal({show: false, trackingId: ''}); setActiveTab('history'); if (user) fetchHistory(); }}
      >
        <div className="flex flex-col items-center text-center">
          <div className="w-12 h-12 bg-emerald-500/15 rounded-full flex items-center justify-center mb-4 border border-emerald-500/25">
            <CheckCircle2 className="w-6 h-6 text-emerald-400" />
          </div>
          <h3 className="text-xl font-bold text-[#ECECEC] mb-2">Ticket submitted successfully!</h3>
          <p className="text-[#8A8F98] text-sm mb-6">Your issue has been securely logged and is being routed by our LangGraph orchestration.</p>

          <div className="w-full rounded-2xl bg-white/[0.03] p-4 border border-white/10 flex flex-col items-center">
            <span className="text-xs text-[#8A8F98] font-semibold mb-2">Tracking ID</span>
            <div className="flex items-center space-x-3 w-full justify-center">
              <span className="font-mono text-[#2DD4BF] text-sm">{successModal.trackingId}</span>
              <MorphButton textToCopy={successModal.trackingId} label="Copy ID" />
            </div>
          </div>

          <GlassButton
            variant="primary"
            className="mt-6 w-full"
            onClick={() => { setSuccessModal({show: false, trackingId: ''}); setActiveTab('history'); if (user) fetchHistory(); }}
          >
            View my tickets
          </GlassButton>
        </div>
      </Modal>

      {/* ── Sidebar on desktop, top bar on mobile — one set of nodes, laid out
           responsively, so nothing (nav, user info) is duplicated in the DOM ── */}
      <aside className="flex flex-col lg:w-64 lg:shrink-0 lg:h-screen lg:sticky lg:top-0 border-b lg:border-b-0 lg:border-r border-white/10 bg-white/[0.02] backdrop-blur-xl">
        <div className="p-4 lg:p-6 border-b border-white/10 flex items-center space-x-3">
          <div className="bg-[#E8A33D]/15 p-2 rounded-xl border border-[#E8A33D]/25 shrink-0">
            <Cpu className="text-[#E8A33D] w-5 h-5" />
          </div>
          <div className="min-w-0">
            <h1 className="text-sm font-bold text-transparent bg-clip-text bg-gradient-to-r from-[#E8A33D] via-[#2DD4BF] to-[#E8A33D] leading-tight">Clario Triage</h1>
            <p className="text-xs text-[#8A8F98] truncate hidden lg:block">Support ticket portal</p>
          </div>
        </div>

        <nav className="flex flex-row lg:flex-col gap-1 p-3 lg:p-4 overflow-x-auto lg:overflow-y-auto lg:flex-1">
          {dashboardNavItems.map(item => (
            <DashboardNavItem
              key={item.id}
              active={activeTab === item.id}
              onClick={() => { if (item.id === 'history') fetchHistory(); setActiveTab(item.id); }}
              icon={item.icon}
              label={item.label}
            />
          ))}
        </nav>

        <div className="p-3 lg:p-4 border-t border-white/10 flex flex-row lg:flex-col items-center lg:items-stretch justify-between lg:justify-start gap-3 lg:gap-1">
          <p className="text-xs text-[#8A8F98] truncate lg:pb-2" title={user?.email || undefined}>
            Logged in as <span className="text-[#E8A33D]">{user?.email}</span>
          </p>
          <div className="flex items-center lg:flex-col lg:items-stretch gap-2 lg:gap-1 shrink-0 overflow-x-auto">
            {role === 'admin' && (
              <button onClick={() => router.push('/admin')} className="flex items-center text-sm text-[#E8A33D] hover:text-[#F4B856] transition-colors px-3 lg:px-3.5 py-2 rounded-lg hover:bg-white/[0.06] whitespace-nowrap">
                <ShieldAlert className="w-4 h-4 mr-2" /> Admin panel
              </button>
            )}
            {role === 'agent' && (
              <button onClick={() => router.push('/agent')} className="flex items-center text-sm text-emerald-300 hover:text-emerald-200 transition-colors px-3 lg:px-3.5 py-2 rounded-lg hover:bg-white/[0.06] whitespace-nowrap">
                <Bot className="w-4 h-4 mr-2" /> Agent workspace
              </button>
            )}
            <button onClick={handleLogout} className="flex items-center text-sm text-[#8A8F98] hover:text-[#FB7185] transition-colors px-3 lg:px-3.5 py-2 rounded-lg hover:bg-white/[0.06] whitespace-nowrap">
              <LogOut className="w-4 h-4 mr-2" /> Sign out
            </button>
          </div>
        </div>
      </aside>

      {/* ── Main content ──────────────────────────────────────────────────────── */}
      <main className="flex-1 min-w-0 py-8 lg:py-12 px-4 sm:px-6 lg:px-10 max-w-[1800px] flex flex-col items-center">

        {/* Header section */}
        <div className="text-center mb-12 animate-fade-in w-full">
          <p className="text-[#8A8F98] max-w-2xl mx-auto text-lg font-light">
            Submit a support ticket and watch our LangGraph orchestration securely classify, route, and resolve issues in real-time.
          </p>
        </div>

      {activeTab === 'new' && (
      <div className="w-full max-w-2xl mx-auto items-start">

        {/* Form */}
        <GlassPanel tier={1} className="p-8 w-full animate-fade-in relative overflow-hidden" style={{ animationDelay: '0.1s' }}>

          <h2 className="text-xl font-semibold mb-8 flex items-center text-[#ECECEC] border-b border-white/10 pb-4">
            <Ticket className="w-5 h-5 mr-3 text-[#2DD4BF]" />
            Submit a ticket
          </h2>

          {error && (
            <div className="mb-6 bg-[#FB7185]/10 border border-[#FB7185]/20 text-[#FB7185] px-4 py-3 rounded-xl flex items-start text-sm">
              <AlertCircle className="w-5 h-5 mr-2 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-8">
            <div>
              <label htmlFor="ticket-text" className="block text-sm font-medium text-[#8A8F98] mb-2">
                Describe the issue
              </label>
              <GlassTextarea
                id="ticket-text"
                required
                value={ticketText}
                onChange={(e) => setTicketText(e.target.value)}
                placeholder="Describe the issue, or dictate it with the microphone below..."
                className="h-40"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-[#8A8F98] mb-2">
                Or use voice input
              </label>
              <VoiceRecorder
                value={ticketText}
                onValueChange={setTicketText}
                disabled={isProcessing}
              />
            </div>

            <div>
              <label htmlFor="ticket-image" className="block text-sm font-medium text-[#8A8F98] mb-2">
                Attach a screenshot (optional)
              </label>
              <input
                id="ticket-image"
                type="file"
                accept="image/*"
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    setImageFile(e.target.files[0]);
                  }
                }}
                className="w-full py-3 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border file:border-white/10 file:bg-white/[0.06] file:text-xs file:text-[#ECECEC] hover:file:bg-white/[0.12] transition-all text-[#8A8F98] text-sm"
              />
              {imageFile && (
                <p className="mt-2 text-xs font-mono text-[#2DD4BF]">Attached: {imageFile.name}</p>
              )}
            </div>

            <GlassButton type="submit" variant="primary" disabled={isProcessing} className="w-full">
              <span>{isProcessing ? 'Submitting…' : 'Submit ticket'}</span>
              {!isProcessing && <Send className="w-4 h-4" />}
            </GlassButton>
          </form>
        </GlassPanel>
      </div>
      )}

      {/* ─── Ticket History Full View ─── */}
      {activeTab === 'history' && (
        <div className="w-full max-w-6xl mx-auto animate-fade-in pb-12">
          <div className="flex justify-between items-center mb-6 max-w-6xl mx-auto px-2">
            <h2 className="text-lg font-semibold text-[#ECECEC] flex items-center">
              <History className="w-5 h-5 mr-3 text-[#2DD4BF]" /> Ticket history
            </h2>
            <RotateButton onClick={fetchHistory} isLoading={dataLoading} />
          </div>
          {pastTickets.length === 0 ? (
            <div className="text-center py-24 glass-panel rounded-[28px]">
              <Ticket className="w-16 h-16 mx-auto mb-4 opacity-20 text-[#E8A33D]" />
              <p className="text-[#8A8F98] text-lg">You haven't submitted any tickets yet.</p>
              <button
                onClick={() => setActiveTab('new')}
                className="mt-6 text-[#E8A33D] hover:text-[#F4B856] font-medium underline-offset-4 hover:underline"
              >
                Submit your first ticket
              </button>
            </div>
          ) : (
            <div className="flex flex-col w-full max-w-6xl mx-auto">
              {pastTickets.map(t => (
                <UserTicketRow key={t.id} ticket={t} onDelete={handleDeleteTicket} userId={user?.id || ''} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Footer */}
      <footer className="mt-16 w-full flex justify-center items-center border-t border-white/10 pt-6 text-sm text-[#8A8F98] animate-fade-in" style={{ animationDelay: '0.4s' }}>
        <p>© 2026 Clario Support Systems</p>
      </footer>
      </main>
    </div>
  );
}

/** One nav button in the dashboard's vertical sidebar rail. */
function DashboardNavItem({ active, onClick, icon, label }: {
  active: boolean; onClick: () => void; icon: React.ReactNode; label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-xl text-sm font-medium text-left transition-all duration-200 ${
        active
          ? 'bg-[#E8A33D]/20 text-[#E8A33D] border border-[#E8A33D]/40 shadow-[0_0_15px_rgba(232,163,61,0.15)]'
          : 'text-[#8A8F98] hover:text-[#ECECEC] border border-transparent hover:bg-white/[0.04]'
      }`}
    >
      <span className="shrink-0">{icon}</span>
      <span className="truncate">{label}</span>
    </button>
  );
}

// ─── UserTicketRow ──────────────────────────────────────────────────────────

import { ChevronDown, ChevronUp } from 'lucide-react';
import { WavePhysicsLoader } from '../../components/WavePhysicsLoader';

function UserTicketRow({ ticket, onDelete, userId }: { ticket: TicketWithResolution; onDelete: (id: string) => void; userId: string }) {
  const [expanded, setExpanded] = useState(false);
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
                  color={classification.priority.toLowerCase() === 'high' ? '#FB923C' : undefined}
                />
              )}
              <UserMetaItem label="Handled by" value={handledBy} />
            </div>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs text-[#8A8F98] block">Your message</span>
              <MorphButton textToCopy={ticket.id} label="Copy ID" />
            </div>
            <p className="text-sm text-[#ECECEC] leading-relaxed font-sans whitespace-pre-wrap">"{ticket.raw_text}"</p>
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
              <FeedbackStars ticketId={ticket.id} userId={userId} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function FeedbackStars({ ticketId, userId }: { ticketId: string; userId: string }) {
  const [hovered, setHovered] = useState<number | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleRate = async (score: number) => {
    if (submitted || isSubmitting) return;
    setIsSubmitting(true);
    try {
      const res = await fetch('/api/customer_feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticketId, userId, score }),
      });
      if (res.ok) setSubmitted(true);
    } catch (e) {
      console.error('Failed to submit feedback', e);
    } finally {
      setIsSubmitting(false);
    }
  };

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
            disabled={isSubmitting || submitted}
            className="disabled:opacity-50"
          >
            <Star
              className="w-4 h-4"
              fill={(hovered ?? 0) >= n ? '#E8A33D' : 'none'}
              stroke="#E8A33D"
            />
          </button>
        ))}
      </div>
      {submitted && <p className="text-xs text-[#2DD4BF] mt-1">Thanks for your feedback!</p>}
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
