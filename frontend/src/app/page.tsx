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
  resolutions: { final_response: string; resolved_by: string }[];
};

import { useAuth } from '../contexts/AuthContext';
import { supabase } from '../lib/supabase';
import { useRouter } from 'next/navigation';

export default function Home() {
  const [ticketId, setTicketId] = useState('demo-001');
  const [ticketText, setTicketText] = useState('Payment failed but the money was taken from my bank account.');
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<TicketResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pastTickets, setPastTickets] = useState<TicketWithResolution[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  
  const { user, role, loading, roleLoading } = useAuth();
  const router = useRouter();

  const fetchHistory = async () => {
    if (!user) return;
    const { data } = await supabase
      .from('tickets')
      .select('*, resolutions(*)')
      .eq('user_id', user.id)
      .order('created_at', { ascending: false });
    if (data) setPastTickets(data);
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
          const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout

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
              ? 'The backend took too long to respond (>30s). The sidecar may be loading a model or processing a heavy request. Please try again in a moment.'
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

        {/* My Tickets button — top-left of header */}
        {user && (
          <div className="absolute left-0 top-0">
            <button
              id="my-tickets-btn"
              onClick={() => { fetchHistory(); setShowHistory(true); }}
              className="flex items-center space-x-2 bg-slate-800/60 hover:bg-slate-700/60 border border-slate-700/50 hover:border-indigo-500/40 text-slate-300 hover:text-white text-sm font-medium px-4 py-2 rounded-xl transition-all duration-200"
            >
              <History className="w-4 h-4 text-indigo-400" />
              <span>My Tickets</span>
              {pastTickets.length > 0 && (
                <span className="bg-indigo-500/30 text-indigo-300 text-xs px-1.5 py-0.5 rounded-full border border-indigo-500/40 ml-1">
                  {pastTickets.length}
                </span>
              )}
            </button>
          </div>
        )}

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

      <div className="w-full grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
        
        {/* Left Column: Form */}
        <section className="glass-panel p-8 rounded-3xl w-full animate-fade-in relative overflow-hidden" style={{ animationDelay: '0.1s' }}>
          {isProcessing && (
            <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm z-10 flex flex-col items-center justify-center rounded-3xl">
              <div className="w-16 h-16 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin mb-4"></div>
              <p className="text-indigo-300 font-medium animate-pulse">Orchestrating ticket...</p>
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

      {/* ─── Slide-in Ticket History Drawer ─── */}
      {showHistory && (
        <div className="fixed inset-0 z-50 flex justify-end">
          {/* backdrop */}
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setShowHistory(false)}
          />
          {/* panel */}
          <aside className="relative z-10 w-full max-w-md bg-[#0d1526] border-l border-slate-700/50 h-full flex flex-col shadow-2xl animate-fade-in">
            <div className="flex items-center justify-between px-6 py-5 border-b border-slate-700/50">
              <div className="flex items-center space-x-3">
                <History className="w-5 h-5 text-indigo-400" />
                <h2 className="text-lg font-semibold text-white">My Tickets</h2>
                <span className="text-xs bg-slate-700/60 text-slate-400 px-2 py-0.5 rounded-full">{pastTickets.length} total</span>
              </div>
              <button
                onClick={() => setShowHistory(false)}
                className="p-2 rounded-lg hover:bg-slate-700/50 text-slate-400 hover:text-white transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
              {pastTickets.length === 0 ? (
                <div className="text-center py-16 text-slate-500">
                  <Ticket className="w-10 h-10 mx-auto mb-3 opacity-30" />
                  <p>No tickets submitted yet.</p>
                </div>
              ) : (
                pastTickets.map(t => {
                  const resolved = t.resolutions && t.resolutions.length > 0;
                  return (
                    <div
                      key={t.id}
                      className={`rounded-2xl border p-4 ${
                        resolved
                          ? 'bg-slate-900/60 border-slate-700/40'
                          : 'bg-slate-900/30 border-slate-800/40'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2 mb-3">
                        <p className="text-sm text-slate-200 leading-relaxed italic flex-1">"{t.raw_text}"</p>
                        {resolved ? (
                          <span className="flex items-center shrink-0 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded-full">
                            <CheckCircle className="w-3 h-3 mr-1" /> Resolved
                          </span>
                        ) : (
                          <span className="flex items-center shrink-0 text-xs text-amber-400 bg-amber-500/10 border border-amber-500/30 px-2 py-0.5 rounded-full">
                            <Clock className="w-3 h-3 mr-1" /> Pending
                          </span>
                        )}
                      </div>
                      {resolved ? (
                        <div className="bg-[#0b1120] rounded-xl p-3 border border-slate-800">
                          <span className="text-xs uppercase tracking-wider text-slate-500 block mb-1">AI Response</span>
                          <p className="text-emerald-300 text-xs leading-relaxed">{t.resolutions[0].final_response}</p>
                        </div>
                      ) : (
                        <p className="text-xs text-slate-500 italic">Awaiting agent review…</p>
                      )}
                      <p className="text-xs text-slate-600 mt-2">{new Date(t.created_at).toLocaleString()}</p>
                    </div>
                  );
                })
              )}
            </div>
          </aside>
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
