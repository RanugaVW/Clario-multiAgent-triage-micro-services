'use client';

import { useState, useEffect } from 'react';
import { Bot, Send, Ticket, AlertCircle, CheckCircle2, ShieldAlert, Cpu, History, X, Clock, CheckCircle } from 'lucide-react';


type TicketState = {
  category?: string;
  priority?: string;
  sentiment?: string;
  routing_decision?: string;
  failure_type?: string;
  escalation_triggered?: boolean;
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

export default function Home() {
  const [ticketId, setTicketId] = useState('demo-001');
  const [ticketText, setTicketText] = useState('Payment failed but the money was taken from my bank account.');
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<TicketResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pastTickets, setPastTickets] = useState<TicketWithResolution[]>([]);
  const [activeTab, setActiveTab] = useState<'new' | 'history'>('new');

  
  const { user, role, loading, roleLoading } = useAuth();
  const router = useRouter();

  const fetchHistory = async () => {
    if (!user) return;
    try {
      const res = await fetch(`http://127.0.0.1:8600/customer_tickets/${user.id}`);
      if (res.ok) {
        const data = await res.json();
        setPastTickets(data);
      }
    } catch (e) {
      console.error('Failed to fetch history:', e);
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
      let ticketUuid = ticketId;
      
      // 1. Save ticket to Supabase first to get real UUID (acts as gateway)
        if (user) {
          const { data: ticketData, error: ticketError } = await supabase
            .from('tickets')
            .insert({ 
              user_id: user.id, 
              raw_text: ticketText, 
              subject: 'Support Ticket',
              customer_email: user.email,
              customer_name: user.email?.split('@')[0] || 'Unknown'
            })
            .select()
            .single();
            
          if (ticketError) {
            console.error("Supabase insert error:", ticketError);
            setError(ticketError.message || "Failed to save ticket to DB");
          }
            
          if (ticketData && !ticketError) {
            ticketUuid = ticketData.id;
          }
        }
        
        // 2. Call ML Sidecar with the real UUID
        let payload;
        try {
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 120000); // 120s timeout

          let response: Response;
          try {
            response = await fetch('http://localhost:8600/process_ticket', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ ticket_id: ticketUuid, raw_text: ticketText }),
              signal: controller.signal,
            });
          } finally {
            clearTimeout(timeoutId);
          }
          
          payload = await response.json();
          
          if (!response.ok) {
            throw new Error(payload.detail || 'Request failed');
          }
        } catch (fetchErr: any) {
          const isAbort = fetchErr.name === 'AbortError';
          const isNetworkError = fetchErr instanceof TypeError && fetchErr.message.includes('fetch');
          throw new Error(
            isAbort
              ? 'The backend took too long to respond (>120s). The sidecar may be loading a model or processing a heavy request. Please try again in a moment.'
              : isNetworkError
                ? 'Cannot reach the ML sidecar at http://localhost:8600. Make sure the backend is running (uvicorn app.main:app --host 0.0.0.0 --port 8600 --reload) inside the clario-ml-sidecar venv.'
                : fetchErr.message || 'Backend request failed.'
          );
        }

        
        setResult(payload);
        if (user) fetchHistory();
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred while connecting to the sidecar.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <main className="min-h-screen py-12 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto flex flex-col items-center">
      
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
      <div className="w-full grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
        
        {/* Left Column: Form */}
        <section className="glass-panel p-8 rounded-3xl w-full animate-fade-in relative overflow-hidden" style={{ animationDelay: '0.1s' }}>
          {isProcessing && (
            <div className="absolute inset-0 bg-slate-900/80 backdrop-blur-md z-10 flex flex-col items-center justify-center rounded-3xl p-6 text-center">
              <div className="w-12 h-12 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin mb-4"></div>
              <h3 className="text-indigo-300 font-bold text-lg mb-2 animate-pulse">Analyzing with Gemma-3...</h3>
              <p className="text-slate-300 text-sm max-w-xs">
                The very first ticket takes 15-30s to load the model into memory. 
                Subsequent tickets take ~3 seconds to process.
              </p>
            </div>
          )}
          
          <h2 className="text-2xl font-semibold mb-6 flex items-center text-white">
            <Ticket className="w-5 h-5 mr-3 text-indigo-400" />
            New Ticket
          </h2>
          
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="ticket-id" className="block text-sm font-medium text-slate-300 mb-2">
                Ticket Reference
              </label>
              <input
                id="ticket-id"
                required
                value={ticketId}
                onChange={(e) => setTicketId(e.target.value)}
                placeholder="e.g. SUP-1001"
                className="glass-input w-full px-4 py-3 rounded-xl"
              />
            </div>
            
            <div>
              <label htmlFor="ticket-text" className="block text-sm font-medium text-slate-300 mb-2">
                Customer Issue
              </label>
              <textarea
                id="ticket-text"
                required
                value={ticketText}
                onChange={(e) => setTicketText(e.target.value)}
                placeholder="Describe the customer's issue..."
                className="glass-input w-full px-4 py-3 rounded-xl h-40 resize-y"
              />
            </div>

            <button
              type="submit"
              disabled={isProcessing}
              className="w-full bg-gradient-to-r from-indigo-500 to-sky-500 hover:from-indigo-400 hover:to-sky-400 text-white font-semibold py-4 px-6 rounded-xl transition-all duration-300 shadow-[0_0_20px_rgba(99,102,241,0.3)] hover:shadow-[0_0_30px_rgba(99,102,241,0.5)] flex items-center justify-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span>{isProcessing ? 'Processing...' : 'Submit to Pipeline'}</span>
              {!isProcessing && <Send className="w-4 h-4 ml-2" />}
            </button>
          </form>
        </section>

        {/* Right Column: Results */}
        <section className={`w-full transition-all duration-500 ease-in-out ${result || error ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8 pointer-events-none'}`}>
          {error && (
            <div className="glass-panel border-red-500/30 p-6 rounded-3xl bg-red-950/20 mb-6 flex items-start space-x-4">
              <ShieldAlert className="text-red-400 w-6 h-6 flex-shrink-0 mt-1" />
              <div>
                <h3 className="text-red-400 font-semibold text-lg mb-1">Processing Error</h3>
                <p className="text-red-300/80">{error}</p>
              </div>
            </div>
          )}

          {result && (
            <div className="space-y-6 animate-fade-in">
              <div className="glass-panel p-8 rounded-3xl relative overflow-hidden">
                <div className="absolute top-0 right-0 p-8 opacity-5">
                  <Bot className="w-32 h-32" />
                </div>
                
                <h2 className="text-2xl font-semibold mb-8 flex items-center text-white">
                  <CheckCircle2 className="w-5 h-5 mr-3 text-emerald-400" />
                  Analysis Complete
                </h2>
                
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-8">
                  <MetricCard label="Category" value={result.state.category} />
                  <MetricCard label="Priority" value={result.state.priority} />
                  <MetricCard label="Sentiment" value={result.state.sentiment} />
                  <MetricCard label="Route" value={result.state.routing_decision} />
                  <MetricCard label="Failure Type" value={result.state.failure_type} />
                  <MetricCard label="Escalated" value={String(result.state.escalation_triggered)} />
                </div>

                <div className="border-t border-slate-700/50 pt-6">
                  <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-4 flex items-center">
                    <AlertCircle className="w-4 h-4 mr-2" />
                    Agent Reasoning / Final Output
                  </h3>
                  <div className="bg-slate-900/50 rounded-xl p-5 border border-slate-700/50 text-slate-300 leading-relaxed">
                    {result.handoff_package?.reasoning_summary || result.final_response || 'No final response was produced.'}
                  </div>
                </div>
              </div>

              <div className="glass-panel p-6 rounded-3xl">
                <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-4">
                  Raw Graph State Payload
                </h3>
                <pre className="bg-[#0b1120] p-4 rounded-xl text-emerald-400/90 text-xs overflow-x-auto border border-slate-800 font-mono shadow-inner">
                  {JSON.stringify(result, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </section>
      </div>
      )}

      {/* ─── Ticket History Full View ─── */}
      {activeTab === 'history' && (
        <div className="w-full max-w-5xl mx-auto animate-fade-in pb-12">
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
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {pastTickets.map(t => {
                const finalResolution = t.resolutions?.find(r => r.escalated === false) || t.resolutions?.[0];
                const isFullyResolved = t.status === 'resolved';
                const isEscalated = t.status === 'escalated';
                
                return (
                  <div key={t.id} className={`glass-panel p-6 rounded-3xl transition-all duration-300 hover:-translate-y-1 hover:shadow-2xl flex flex-col h-full ${isFullyResolved ? 'border-emerald-500/30 bg-emerald-950/10 shadow-[0_10px_30px_rgba(16,185,129,0.05)]' : isEscalated ? 'border-amber-500/30 bg-amber-950/10 shadow-[0_10px_30px_rgba(245,158,11,0.05)]' : 'border-indigo-500/20'}`}>
                    <div className="flex items-start justify-between mb-5">
                      <div className="flex-1 pr-4">
                        <span className="text-[10px] uppercase tracking-widest text-slate-500 font-bold mb-1.5 block flex items-center">
                          <Ticket className="w-3 h-3 mr-1" /> Your Issue
                        </span>
                        <p className="text-slate-200 font-medium leading-snug line-clamp-2">"{t.raw_text}"</p>
                      </div>
                      <div className="shrink-0">
                        {isFullyResolved ? (
                          <span className="flex items-center text-xs font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-3 py-1.5 rounded-full shadow-[0_0_15px_rgba(52,211,153,0.15)]">
                            <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" /> Resolved
                          </span>
                        ) : isEscalated ? (
                          <span className="flex items-center text-xs font-bold text-amber-400 bg-amber-500/10 border border-amber-500/30 px-3 py-1.5 rounded-full shadow-[0_0_15px_rgba(251,191,36,0.15)] animate-pulse">
                            <Clock className="w-3.5 h-3.5 mr-1.5" /> In Review
                          </span>
                        ) : (
                          <span className="flex items-center text-xs font-bold text-sky-400 bg-sky-500/10 border border-sky-500/30 px-3 py-1.5 rounded-full">
                            <AlertCircle className="w-3.5 h-3.5 mr-1.5" /> Pending
                          </span>
                        )}
                      </div>
                    </div>
                    
                    <div className="flex-grow">
                      {(isFullyResolved && finalResolution?.final_response) ? (
                        <div className="bg-[#0b1120] rounded-2xl p-4 border border-slate-800 relative overflow-hidden mt-2 h-full">
                          <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-emerald-400 to-emerald-600"></div>
                          <span className="text-[10px] uppercase tracking-wider text-slate-500 block mb-2 font-bold flex items-center">
                            <CheckCircle className="w-3 h-3 mr-1" /> Final Response
                          </span>
                          <p className="text-emerald-300 text-sm leading-relaxed">{finalResolution.final_response}</p>
                        </div>
                      ) : (
                        <div className="mt-2 p-4 rounded-2xl border border-slate-800/80 bg-slate-900/40 flex flex-col items-center justify-center text-center h-full min-h-[100px]">
                          <Cpu className="w-6 h-6 text-slate-600 mb-2" />
                          <p className="text-xs text-slate-400 font-medium">A human agent has taken over this ticket and is currently drafting a resolution.</p>
                        </div>
                      )}
                    </div>
                    
                    <div className="mt-5 pt-4 border-t border-slate-800/80 text-[11px] text-slate-500 font-medium flex justify-between items-center uppercase tracking-wider">
                      <span>ID: {t.id.split('-')[0]}</span>
                      <span>{new Date(t.created_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                  </div>
                );
              })}
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

function MetricCard({ label, value }: { label: string; value?: string }) {
  return (
    <div className="bg-slate-900/40 border border-slate-700/50 p-4 rounded-2xl flex flex-col justify-center">
      <span className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-1">{label}</span>
      <span className="text-slate-100 font-semibold truncate capitalize">{value ?? '—'}</span>
    </div>
  );
}
