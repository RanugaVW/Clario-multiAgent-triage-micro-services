'use client';

import { useState, useEffect } from 'react';
import { Bot, Send, Ticket, AlertCircle, CheckCircle2, ShieldAlert, Cpu, History, X, Clock, CheckCircle, Trash2, Copy } from 'lucide-react';

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
  status: string;
  resolutions: { final_response: string; resolved_by: string; escalated: boolean }[];
};

import { useAuth } from '../../contexts/AuthContext';
import { supabase } from '../../lib/supabase';
import { useRouter } from 'next/navigation';
import MorphButton from '../../components/MorphButton';
import ShakeButton from '../../components/ShakeButton';
import RotateButton from '../../components/RotateButton';

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
      const res = await fetch(`/api/user_tickets?userId=${user.id}`);
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || 'Failed to fetch history');
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
        <div className="w-16 h-16 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin"></div>
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

  return (
    <main className="min-h-screen py-12 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto flex flex-col items-center">
      
      {/* Success Modal */}
      {successModal.show && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 shadow-2xl max-w-md w-full mx-4 animate-fade-in relative">
            <button 
              onClick={() => { setSuccessModal({show: false, trackingId: ''}); setActiveTab('history'); if (user) fetchHistory(); }}
              className="absolute top-4 right-4 text-slate-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>
            <div className="flex flex-col items-center text-center">
              <div className="w-12 h-12 bg-emerald-500/20 rounded-full flex items-center justify-center mb-4 border border-emerald-500/30">
                <CheckCircle2 className="w-6 h-6 text-emerald-400" />
              </div>
              <h3 className="text-xl font-bold text-white mb-2">Ticket Submitted Successfully!</h3>
              <p className="text-slate-400 text-sm mb-6">Your issue has been securely logged and is being routed by our LangGraph orchestration.</p>
              
              <div className="w-full bg-slate-950 rounded-xl p-4 border border-slate-800 flex flex-col items-center">
                <span className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-2">Tracking ID</span>
                <div className="flex items-center space-x-3 w-full justify-center">
                  <span className="font-mono text-emerald-400 text-sm">{successModal.trackingId}</span>
                  <MorphButton textToCopy={successModal.trackingId} label="Copy ID" />
                </div>
              </div>

              <button
                onClick={() => { setSuccessModal({show: false, trackingId: ''}); setActiveTab('history'); if (user) fetchHistory(); }}
                className="mt-6 w-full py-3 bg-indigo-500 hover:bg-indigo-400 text-white rounded-xl font-semibold transition-colors"
              >
                View My Tickets
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Header section */}
      <div className="text-center mb-12 animate-fade-in relative w-full">
        {user && (
          <div className="absolute right-0 top-0 flex items-center space-x-4">
            <div className="text-sm text-slate-400">
              Logged in as <span className="text-indigo-400">{user.email}</span>
            </div>
            {role === 'admin' && (
              <button 
                onClick={() => router.push('/admin')}
                className="bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-300 text-xs font-semibold px-4 py-2 rounded-xl transition-colors border border-indigo-500/30 flex items-center"
              >
                <ShieldAlert className="w-3 h-3 mr-2" />
                Admin Panel
              </button>
            )}
            {role === 'agent' && (
              <button 
                onClick={() => router.push('/agent')}
                className="bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 text-xs font-semibold px-4 py-2 rounded-xl transition-colors border border-emerald-500/30"
              >
                Agent Workspace
              </button>
            )}
          </div>
        )}

        {/* Removed absolute My Tickets button, using tabs below */}

        <div className="flex justify-center items-center mb-4 space-x-3">
          <div className="bg-indigo-500/20 p-3 rounded-2xl border border-indigo-500/30">
            <Cpu className="text-indigo-400 w-8 h-8" />
          </div>
          <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-sky-400 to-indigo-400">
            Clario Triage
          </h1>
        </div>
        <p className="text-slate-400 max-w-2xl mx-auto text-lg font-light">
          Submit a support ticket and watch our LangGraph orchestration securely classify, route, and resolve issues in real-time.
        </p>
      </div>
      
      {/* ─── Tabs ─── */}
      {user && (
        <div className="flex justify-center space-x-4 mb-10 animate-fade-in w-full">
          <button
            onClick={() => setActiveTab('new')}
            className={`px-8 py-3 rounded-2xl font-semibold transition-all duration-300 flex items-center justify-center min-w-[180px] ${activeTab === 'new' ? 'bg-gradient-to-r from-indigo-500 to-sky-500 text-white shadow-[0_0_25px_rgba(99,102,241,0.4)] scale-105' : 'bg-slate-800/60 text-slate-400 hover:text-slate-200 hover:bg-slate-700/80'}`}
          >
            <Ticket className="w-5 h-5 mr-2" /> Submit Ticket
          </button>
          <button
            onClick={() => { fetchHistory(); setActiveTab('history'); }}
            className={`px-8 py-3 rounded-2xl font-semibold transition-all duration-300 flex items-center justify-center min-w-[180px] ${activeTab === 'history' ? 'bg-gradient-to-r from-indigo-500 to-sky-500 text-white shadow-[0_0_25px_rgba(99,102,241,0.4)] scale-105' : 'bg-slate-800/60 text-slate-400 hover:text-slate-200 hover:bg-slate-700/80'}`}
          >
            <History className="w-5 h-5 mr-2" /> My Tickets
            {pastTickets.length > 0 && (
              <span className={`ml-2 px-2 py-0.5 rounded-full text-xs font-bold ${activeTab === 'history' ? 'bg-white/20 text-white' : 'bg-indigo-500/30 text-indigo-300 border border-indigo-500/30'}`}>
                {pastTickets.length}
              </span>
            )}
          </button>
        </div>
      )}

      {activeTab === 'new' && (
      <div className="w-full max-w-2xl mx-auto items-start">
        
        {/* Form */}
        <section className="glass-panel p-8 w-full animate-fade-in relative overflow-hidden" style={{ animationDelay: '0.1s' }}>

          <h2 className="text-xl font-mono tracking-widest uppercase mb-8 flex items-center text-white border-b border-[#222222] pb-4">
            <Ticket className="w-5 h-5 mr-3 text-[#00E5FF]" />
            INITIALIZE_TICKET
          </h2>
          
          {error && (
            <div className="mb-6 bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-3 rounded flex items-start text-sm">
              <AlertCircle className="w-5 h-5 mr-2 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}
          
          <form onSubmit={handleSubmit} className="space-y-8">
            <div>
              <label htmlFor="ticket-text" className="block text-[10px] font-mono tracking-widest text-[#888888] uppercase mb-2">
                ISSUE_PAYLOAD
              </label>
              <textarea
                id="ticket-text"
                required
                value={ticketText}
                onChange={(e) => setTicketText(e.target.value)}
                placeholder="Describe the issue..."
                className="glass-input w-full px-0 py-3 text-sm h-40 resize-y"
              />
            </div>
            
            <div>
              <label htmlFor="ticket-image" className="block text-[10px] font-mono tracking-widest text-[#888888] uppercase mb-2">
                ATTACH_TELEMETRY (IMAGE)
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
                className="w-full py-3 file:mr-4 file:py-2 file:px-4 file:border file:border-[#222222] file:bg-[#111111] file:text-[10px] file:font-mono file:tracking-widest file:text-[#ececec] hover:file:bg-[#222222] hover:file:text-white transition-all text-[#888888] text-sm"
              />
              {imageFile && (
                <p className="mt-2 text-[10px] font-mono text-[#00E5FF]">ATTACHED: {imageFile.name}</p>
              )}
            </div>

            <button
              type="submit"
              disabled={isProcessing}
              className="w-full bg-[#111111] hover:bg-[#00E5FF] text-[#00E5FF] hover:text-[#050505] border border-[#00E5FF] font-mono tracking-widest uppercase text-xs py-4 px-6 transition-all duration-300 flex items-center justify-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span>{isProcessing ? 'PROCESSING...' : 'PROCESS_TICKET'}</span>
              {!isProcessing && <Send className="w-4 h-4 ml-2" />}
            </button>
          </form>
        </section>
      </div>
      )}

      {/* ─── Ticket History Full View ─── */}
      {activeTab === 'history' && (
        <div className="w-full max-w-5xl mx-auto animate-fade-in pb-12">
          <div className="flex justify-between items-center mb-6 max-w-4xl mx-auto px-2">
            <h2 className="text-lg font-mono tracking-widest uppercase text-white flex items-center">
              <History className="w-5 h-5 mr-3 text-[#00E5FF]" /> Ticket History
            </h2>
            <RotateButton onClick={fetchHistory} isLoading={dataLoading} />
          </div>
          {pastTickets.length === 0 ? (
            <div className="text-center py-24 bg-slate-900/30 rounded-3xl border border-slate-800/50 glass-panel">
              <Ticket className="w-16 h-16 mx-auto mb-4 opacity-20 text-indigo-400" />
              <p className="text-slate-400 text-lg">You haven't submitted any tickets yet.</p>
              <button 
                onClick={() => setActiveTab('new')}
                className="mt-6 text-indigo-400 hover:text-indigo-300 font-medium underline-offset-4 hover:underline"
              >
                Submit your first ticket
              </button>
            </div>
          ) : (
            <div className="flex flex-col w-full max-w-4xl mx-auto">
              {pastTickets.map(t => (
                <UserTicketRow key={t.id} ticket={t} onDelete={handleDeleteTicket} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Footer */}
      <footer className="mt-16 w-full flex justify-between items-center border-t border-slate-800/50 pt-6 text-sm text-slate-500 animate-fade-in" style={{ animationDelay: '0.4s' }}>
        <p>© 2026 Clario Support Systems</p>
        {user ? (
          <button onClick={handleLogout} className="hover:text-red-400 transition-colors flex items-center">
            Sign Out
          </button>
        ) : (
          <a href="/login" className="hover:text-indigo-400 transition-colors flex items-center">
            <ShieldAlert className="w-4 h-4 mr-1.5" />
            Sign In / Register
          </a>
        )}
      </footer>
    </main>
  );
}

// ─── UserTicketRow ──────────────────────────────────────────────────────────

import { ChevronDown, ChevronUp } from 'lucide-react';
import { WavePhysicsLoader } from '../../components/WavePhysicsLoader';

function UserTicketRow({ ticket, onDelete }: { ticket: TicketWithResolution; onDelete: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const finalResolution = ticket.resolutions?.find(r => r.escalated === false);
  const isFullyResolved = ticket.status === 'resolved' || !!finalResolution;
  const isEscalated = !isFullyResolved && (ticket.status === 'escalated' || ticket.resolutions?.some(r => r.escalated));
  
  let statusColor = '#888888';
  let statusLabel = 'PROCESSING';
  if (isEscalated) { statusColor = '#FFD600'; statusLabel = 'REQUIRES REVIEW'; }
  else if (isFullyResolved) { statusColor = '#00FF66'; statusLabel = 'COMPLETED'; }

  const issueSnippet = ticket.raw_text.substring(0, 80) + (ticket.raw_text.length > 80 ? '...' : '');

  return (
    <div className="border border-[#222222] bg-[#111111] mb-2 transition-all duration-200 hover:border-[#444444]">
      {/* Unexpanded Row */}
      <div 
        className="flex items-center justify-between p-4 cursor-pointer select-none"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center space-x-6 flex-1 min-w-0">
          <div className="flex items-center space-x-3 w-36 shrink-0">
            <span className="w-1.5 h-1.5" style={{ backgroundColor: statusColor }} />
            <span className="text-xs font-mono tracking-widest text-[#888888] truncate">{ticket.id.split('-')[0]}</span>
          </div>
          <span className="text-[10px] text-[#888888] font-mono w-20 shrink-0">{new Date(ticket.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
          <span className="text-sm text-[#ececec] truncate font-sans">{issueSnippet}</span>
        </div>
        
        <div className="flex items-center space-x-6 shrink-0 pl-4">
          <span className="text-[10px] font-mono tracking-widest" style={{ color: statusColor }}>[{statusLabel}]</span>
          <ShakeButton onDelete={(e) => { e.stopPropagation(); onDelete(ticket.id); }} />
          {expanded ? <ChevronUp className="w-4 h-4 text-[#888888]" /> : <ChevronDown className="w-4 h-4 text-[#888888]" />}
        </div>
      </div>

      {/* Expanded Details */}
      {expanded && (
        <div className="border-t border-[#222222] p-6 bg-[#050505] space-y-6">
          <div>
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[10px] font-mono tracking-widest text-[#555555] uppercase block">ORIGINAL_PAYLOAD</span>
              <MorphButton textToCopy={ticket.id} label="Copy ID" />
            </div>
            <p className="text-sm text-[#ececec] leading-relaxed font-sans whitespace-pre-wrap">"{ticket.raw_text}"</p>
          </div>
          
          <div className="border-t border-[#222222] pt-4">
            <span className="text-[10px] font-mono tracking-widest uppercase block mb-2" style={{ color: statusColor }}>SYS_RESOLUTION</span>
            <div className="bg-[#111111] border border-[#222222] p-4 min-h-[100px] font-sans text-sm text-[#ececec]">
              {(isFullyResolved && finalResolution?.final_response) 
                ? parseCustomerResponse(finalResolution.final_response) 
                : (isEscalated 
                    ? 'A human agent has taken over this ticket and is currently drafting a resolution.'
                    : <div className="flex justify-center items-center py-8"><WavePhysicsLoader theme="dark" /></div>
                  )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
