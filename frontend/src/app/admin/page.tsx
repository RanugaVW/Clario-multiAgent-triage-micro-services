'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useRouter } from 'next/navigation';
import {
  Activity, Settings, Database, Server, Cpu, LogOut, Loader2,
  ChevronDown, ChevronUp, AlertTriangle, CheckCircle, Mail, Clock,
  BarChart2, MessageSquare, ShieldAlert, Tag, Zap, ArrowLeft, Bot,
  CreditCard, Wrench, Brain, GitBranch, Eye, RotateCcw, ArrowRightLeft,
  Shield, Layers, CheckCircle2,
} from 'lucide-react';
import { supabase } from '../../lib/supabase';

// ─── Types ────────────────────────────────────────────────────────────────────

type TicketDraft = {
  rag_top_score: number | null;
  draft_text: string | null;
  domain: string | null;
  retrieved_sources: any[] | null;
  reflection_attempt: number | null;
};

type TicketClassification = {
  category: string | null;
  priority: string | null;
  sentiment: string | null;
  confidence: number | null;
};

type Resolution = {
  id: string;
  final_response: string | null;
  escalated: boolean;
  escalation_reasons: string[] | null;
  resolved_at: string;
  total_reflection_count: number | null;
  ticket_id: string;
};

type Ticket = {
  id: string;
  raw_text: string;
  subject: string | null;
  customer_email: string | null;
  status: string;
  created_at: string;
  ticket_drafts: TicketDraft[];
  ticket_classifications: TicketClassification[];
  resolutions: Resolution[];
};

// ─── Virtual AI Agent Definitions (from architecture doc) ─────────────────────

const AI_AGENTS = [
  {
    id: 'billing_agent',
    name: 'Billing Agent',
    description: 'Handles billing, payments, refunds, account charges',
    icon: CreditCard,
    domain: 'billing',
    color: 'emerald',
    keywords: ['billing', 'account', 'payment', 'charge', 'refund', 'invoice'],
  },
  {
    id: 'technical_agent',
    name: 'Technical Agent',
    description: 'Handles technical errors, crashes, login, system failures',
    icon: Wrench,
    domain: 'technical',
    color: 'sky',
    keywords: ['technical', 'error', 'crash', 'login', 'bug', 'not working'],
  },
];

const PIPELINE_NODES = [
  { id: 'surrogate_node', name: 'SurrogateShield', description: 'PII anonymization & redaction', icon: Shield },
  { id: 'analyzer_node', name: 'Semantic Distiller', description: 'Extracts key concepts', icon: Brain },
  { id: 'classification_node', name: 'Classifier (Gemini)', description: 'LLM-based category, priority, sentiment', icon: Tag },
  { id: 'routing_node', name: 'Router', description: 'Routes to billing, technical, or both agents', icon: GitBranch },
  { id: 'validation_node', name: 'EGC Validator', description: 'Evidence Graph Consistency + LLM Judge', icon: Eye },
  { id: 'reflection_node', name: 'Reflection Node', description: 'Bounded retry on quality/policy failures', icon: RotateCcw },
  { id: 'escalation_node', name: 'Escalation Node', description: 'Triggers human review for unresolvable tickets', icon: ShieldAlert },
  { id: 'resolve_node', name: 'Resolve Node', description: 'Restores PII from ShadowMap', icon: ArrowRightLeft },
];

// ─── Admin Dashboard ──────────────────────────────────────────────────────────

export default function AdminDashboard() {
  const { user, role, loading, roleLoading } = useAuth();
  const router = useRouter();

  const [allTickets, setAllTickets] = useState<Ticket[]>([]);
  const [expandedAgentId, setExpandedAgentId] = useState<string | null>('billing_agent');
  const [activeTab, setActiveTab] = useState<'agents' | 'pipeline' | 'human_review' | 'all_tickets'>('agents');
  const [dataLoading, setDataLoading] = useState(false);
  const [debugInfo, setDebugInfo] = useState<string>('');

  const isFullyLoaded = !loading && !roleLoading;

  useEffect(() => {
    if (!isFullyLoaded) return;
    if (!user || role !== 'admin') {
      router.push('/login');
      return;
    }
    fetchData();
  }, [isFullyLoaded, user, role]);

  const fetchData = useCallback(async () => {
    setDataLoading(true);
    setDebugInfo('');
    try {
      const { data: ticketData, error: ticketError } = await supabase
        .from('tickets')
        .select(`
          id, raw_text, subject, customer_email, status, created_at,
          ticket_drafts ( rag_top_score, draft_text, domain, retrieved_sources, reflection_attempt ),
          ticket_classifications ( category, priority, sentiment, confidence ),
          resolutions ( id, final_response, escalated, escalation_reasons, resolved_at, total_reflection_count, ticket_id )
        `)
        .order('created_at', { ascending: false });

      if (ticketError) {
        setDebugInfo(`Ticket fetch error: ${ticketError.message}`);
      } else {
        setAllTickets((ticketData as any) || []);
      }
    } finally {
      setDataLoading(false);
    }
  }, []);

  // Group tickets by agent domain based on ticket_drafts domain
  const getAgentTickets = (agentDomain: string) => {
    return allTickets.filter(t =>
      t.ticket_drafts?.some(d => d.domain === agentDomain) ||
      t.resolutions?.some(r => !r.escalated && r.final_response)
    ).filter(t => {
      const cls = t.ticket_classifications?.[0];
      const draft = t.ticket_drafts?.find(d => d.domain === agentDomain);
      if (draft) return true;
      // Fallback: match by classification category
      if (agentDomain === 'billing') return ['billing', 'account', 'Billing', 'Account'].includes(cls?.category || '');
      if (agentDomain === 'technical') return ['technical', 'Technical'].includes(cls?.category || '');
      return false;
    });
  };

  const resolvedTickets = allTickets.filter(t =>
    t.resolutions?.length > 0 && t.resolutions.some(r => !r.escalated)
  );
  const humanReviewTickets = allTickets.filter(t =>
    t.resolutions?.some(r => r.escalated) ||
    (!t.resolutions?.length && t.status === 'escalated')
  );

  const handleLogout = async () => {
    await supabase.auth.signOut();
    router.push('/login');
  };

  if (!isFullyLoaded) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center space-y-4">
        <Loader2 className="w-10 h-10 animate-spin text-indigo-500" />
        <p className="text-slate-400 text-sm">Loading admin workspace...</p>
      </div>
    );
  }

  return (
    <main className="min-h-screen py-8 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <header className="flex justify-between items-center mb-10 animate-fade-in">
        <div className="flex items-center space-x-3">
          <div className="bg-sky-500/20 p-2 rounded-xl border border-sky-500/30">
            <Settings className="text-sky-400 w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">System Administration</h1>
            <p className="text-sm text-slate-400">Clario Platform — {user?.email}</p>
          </div>
        </div>
        <div className="flex items-center space-x-3">
          <button onClick={() => router.push('/')} className="flex items-center text-sm text-slate-400 hover:text-white transition-colors px-3 py-2 rounded-lg hover:bg-slate-800">
            <ArrowLeft className="w-4 h-4 mr-1.5" /> Back to Triage
          </button>
          <button onClick={handleLogout} className="p-2 hover:bg-slate-800 rounded-full transition-colors text-slate-400 hover:text-red-400" title="Sign Out">
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </header>

      {/* ── System Status ───────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8 animate-fade-in" style={{ animationDelay: '0.1s' }}>
        <SystemCard icon={<Server />} label="Spring Boot Gateway" status="Healthy" uptime="99.9%" color="emerald" />
        <SystemCard icon={<Cpu />} label="ML Sidecar (FastAPI)" status="Healthy" uptime="99.8%" color="emerald" />
        <SystemCard icon={<Database />} label="PostgreSQL (Supabase)" status="Healthy" uptime="99.9%" color="emerald" />
        <SystemCard icon={<Database />} label="ChromaDB (50 docs)" status="Active" uptime="98.5%" color="sky" />
      </div>

      {/* ── Stats Bar ───────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8 animate-fade-in" style={{ animationDelay: '0.15s' }}>
        <StatBadge label="Total Tickets" value={allTickets.length} color="indigo" />
        <StatBadge label="Auto-Resolved" value={resolvedTickets.length} color="emerald" />
        <StatBadge label="Human Review" value={humanReviewTickets.length} color="amber" />
        <StatBadge label="AI Agents Active" value={2} color="sky" />
      </div>

      {/* ── Debug ───────────────────────────────────────────────────────────── */}
      {debugInfo && (
        <div className="mb-6 bg-red-950/30 border border-red-500/30 rounded-xl p-4 text-red-400 text-sm">
          <strong>Debug:</strong> {debugInfo}
        </div>
      )}

      {/* ── Tabs ────────────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-2 mb-6 animate-fade-in" style={{ animationDelay: '0.2s' }}>
        <TabBtn active={activeTab === 'agents'} onClick={() => setActiveTab('agents')} icon={<Bot className="w-4 h-4" />} label={`AI Agents (${AI_AGENTS.length})`} />
        <TabBtn active={activeTab === 'pipeline'} onClick={() => setActiveTab('pipeline')} icon={<Layers className="w-4 h-4" />} label="Pipeline Nodes" />
        <TabBtn active={activeTab === 'human_review'} onClick={() => setActiveTab('human_review')} icon={<AlertTriangle className="w-4 h-4" />} label={`Human Review Queue (${humanReviewTickets.length})`} warn={humanReviewTickets.length > 0} />
        <TabBtn active={activeTab === 'all_tickets'} onClick={() => setActiveTab('all_tickets')} icon={<MessageSquare className="w-4 h-4" />} label={`All Tickets (${allTickets.length})`} />
      </div>

      {/* ── AI Agents Tab ───────────────────────────────────────────────────── */}
      {activeTab === 'agents' && (
        <section className="glass-panel rounded-3xl overflow-hidden animate-fade-in" style={{ animationDelay: '0.25s' }}>
          <div className="p-6 border-b border-slate-700/50 bg-slate-900/50 flex justify-between items-center">
            <h2 className="text-lg font-semibold text-white flex items-center">
              <Bot className="w-5 h-5 mr-2 text-indigo-400" /> RAG AI Agents &amp; Resolved Tickets
            </h2>
            <button onClick={fetchData} disabled={dataLoading} className="text-xs text-slate-400 hover:text-white transition-colors flex items-center">
              {dataLoading ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Activity className="w-3 h-3 mr-1" />}
              Refresh
            </button>
          </div>

          {dataLoading ? (
            <div className="p-16 flex justify-center"><Loader2 className="w-8 h-8 animate-spin text-indigo-500" /></div>
          ) : (
            <div className="divide-y divide-slate-700/30">
              {AI_AGENTS.map((agent) => {
                const agentTickets = getAgentTickets(agent.domain);
                const Icon = agent.icon;
                const colorMap: Record<string, string> = {
                  emerald: 'text-emerald-400 bg-emerald-500/15 border-emerald-500/25',
                  sky: 'text-sky-400 bg-sky-500/15 border-sky-500/25',
                };
                return (
                  <div key={agent.id} className="flex flex-col">
                    <div
                      className="p-5 flex items-center justify-between cursor-pointer hover:bg-slate-800/40 transition-colors"
                      onClick={() => setExpandedAgentId(prev => prev === agent.id ? null : agent.id)}
                    >
                      <div className="flex items-center space-x-4">
                        <div className={`w-12 h-12 rounded-2xl border flex items-center justify-center ${colorMap[agent.color]}`}>
                          <Icon className="w-6 h-6" />
                        </div>
                        <div>
                          <p className="font-semibold text-slate-100 text-base">{agent.name}</p>
                          <p className="text-xs text-slate-500 mt-0.5">{agent.description}</p>
                          <p className="text-xs mt-1 flex items-center">
                            <span className={`w-1.5 h-1.5 rounded-full mr-1.5 animate-pulse ${agent.color === 'emerald' ? 'bg-emerald-400' : 'bg-sky-400'}`} />
                            <span className={agent.color === 'emerald' ? 'text-emerald-400' : 'text-sky-400'}>Active — RAG domain: <strong>{agent.domain}</strong></span>
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-6">
                        <div className="text-right">
                          <p className="text-2xl font-bold text-white">{agentTickets.length}</p>
                          <p className="text-xs text-slate-500">Tickets handled</p>
                        </div>
                        {expandedAgentId === agent.id ? <ChevronUp className="w-5 h-5 text-slate-500" /> : <ChevronDown className="w-5 h-5 text-slate-500" />}
                      </div>
                    </div>

                    {expandedAgentId === agent.id && (
                      <div className="px-5 pb-5 bg-slate-900/20 border-t border-slate-800/50">
                        {agentTickets.length === 0 ? (
                          <p className="text-slate-500 italic text-sm text-center py-8">No tickets handled by this agent yet. Submit a ticket to see it here.</p>
                        ) : (
                          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 pt-4">
                            {agentTickets.map(ticket => (
                              <AgentTicketCard key={ticket.id} ticket={ticket} domain={agent.domain} />
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}

      {/* ── Pipeline Nodes Tab ──────────────────────────────────────────────── */}
      {activeTab === 'pipeline' && (
        <section className="animate-fade-in" style={{ animationDelay: '0.25s' }}>
          <div className="glass-panel rounded-3xl p-6 mb-6">
            <h2 className="text-base font-semibold text-white mb-1 flex items-center">
              <Layers className="w-4 h-4 mr-2 text-indigo-400" /> LangGraph Pipeline Architecture
            </h2>
            <p className="text-sm text-slate-500">All nodes run sequentially within the LangGraph state machine. The <code className="bg-slate-800 px-1 rounded text-indigo-300">TicketState</code> blackboard is passed between nodes.</p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {PIPELINE_NODES.map((node, i) => {
              const Icon = node.icon;
              return (
                <div key={node.id} className="glass-panel rounded-2xl p-5 relative overflow-hidden">
                  <div className="absolute top-3 right-3 text-slate-700 text-xs font-bold">#{i + 1}</div>
                  <div className="bg-indigo-500/15 border border-indigo-500/25 w-10 h-10 rounded-xl flex items-center justify-center mb-3">
                    <Icon className="w-5 h-5 text-indigo-400" />
                  </div>
                  <p className="font-semibold text-slate-200 text-sm mb-1">{node.name}</p>
                  <p className="text-xs text-slate-500 leading-relaxed">{node.description}</p>
                  <div className="mt-3 flex items-center">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5 animate-pulse" />
                    <span className="text-xs text-emerald-400">Active</span>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-6 glass-panel rounded-2xl p-5">
            <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center">
              <BarChart2 className="w-4 h-4 mr-2 text-sky-400" /> Processing Stats
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="bg-slate-900/50 rounded-xl p-3 text-center">
                <p className="text-xl font-bold text-white">{allTickets.length}</p>
                <p className="text-xs text-slate-500">Total processed</p>
              </div>
              <div className="bg-slate-900/50 rounded-xl p-3 text-center">
                <p className="text-xl font-bold text-emerald-400">{resolvedTickets.length}</p>
                <p className="text-xs text-slate-500">Auto-resolved</p>
              </div>
              <div className="bg-slate-900/50 rounded-xl p-3 text-center">
                <p className="text-xl font-bold text-amber-400">{humanReviewTickets.length}</p>
                <p className="text-xs text-slate-500">Escalated</p>
              </div>
              <div className="bg-slate-900/50 rounded-xl p-3 text-center">
                <p className="text-xl font-bold text-sky-400">
                  {allTickets.length > 0 ? Math.round((resolvedTickets.length / allTickets.length) * 100) : 0}%
                </p>
                <p className="text-xs text-slate-500">Auto-resolve rate</p>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* ── Human Review Tab ────────────────────────────────────────────────── */}
      {activeTab === 'human_review' && (
        <section className="animate-fade-in" style={{ animationDelay: '0.25s' }}>
          {humanReviewTickets.length === 0 ? (
            <div className="glass-panel rounded-3xl p-16 text-center">
              <CheckCircle className="w-14 h-14 text-emerald-500/50 mx-auto mb-4" />
              <p className="text-slate-300 font-semibold text-lg">All caught up!</p>
              <p className="text-slate-500 text-sm mt-1">No tickets need human review right now.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {humanReviewTickets.map(ticket => (
                <HumanReviewCard key={ticket.id} ticket={ticket} />
              ))}
            </div>
          )}
        </section>
      )}
      {/* ── All Tickets Tab ──────────────────────────────────────────────────── */}
      {activeTab === 'all_tickets' && (
        <section className="animate-fade-in" style={{ animationDelay: '0.25s' }}>
          <div className="glass-panel rounded-3xl overflow-hidden">
            <div className="p-6 border-b border-slate-700/50 bg-slate-900/50 flex justify-between items-center">
              <h2 className="text-lg font-semibold text-white flex items-center">
                <MessageSquare className="w-5 h-5 mr-2 text-indigo-400" /> All Tickets & Responses
              </h2>
              <button onClick={fetchData} disabled={dataLoading} className="text-xs text-slate-400 hover:text-white transition-colors flex items-center">
                {dataLoading ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Activity className="w-3 h-3 mr-1" />}
                Refresh
              </button>
            </div>

            {dataLoading ? (
              <div className="p-16 flex justify-center"><Loader2 className="w-8 h-8 animate-spin text-indigo-500" /></div>
            ) : allTickets.length === 0 ? (
              <div className="p-16 text-center">
                <MessageSquare className="w-12 h-12 text-slate-700 mx-auto mb-4" />
                <p className="text-slate-400 font-medium">No tickets yet</p>
                <p className="text-slate-600 text-sm mt-1">Submit a ticket from the Triage page to see it here.</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-800/60">
                {allTickets.map((ticket, idx) => {
                  const cls = ticket.ticket_classifications?.[0];
                  const resolution = ticket.resolutions?.find(r => !r.escalated) || ticket.resolutions?.[0];
                  const isEscalated = ticket.resolutions?.some(r => r.escalated) || ticket.status === 'escalated';
                  const isResolved = !isEscalated && resolution?.final_response;
                  return (
                    <div key={ticket.id} className="p-5 hover:bg-slate-800/20 transition-colors">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          {/* Row 1: email + timestamp */}
                          <div className="flex items-center gap-3 mb-2">
                            <span className="text-xs text-slate-500">#{idx + 1}</span>
                            {ticket.customer_email && (
                              <span className="text-xs text-sky-400 flex items-center">
                                <Mail className="w-3 h-3 mr-1" />{ticket.customer_email}
                              </span>
                            )}
                            <span className="text-xs text-slate-600 flex items-center">
                              <Clock className="w-3 h-3 mr-1" />{new Date(ticket.created_at).toLocaleString()}
                            </span>
                          </div>

                          {/* Row 2: raw text */}
                          <p className="text-sm text-slate-200 leading-relaxed mb-3 italic">"{ticket.raw_text}"</p>

                          {/* Row 3: classification chips */}
                          {cls && (
                            <div className="flex flex-wrap gap-1.5 mb-3">
                              {cls.category && <Chip label={cls.category} color="indigo" icon={<Tag className="w-3 h-3" />} />}
                              {cls.priority && <Chip label={cls.priority} color={cls.priority?.toLowerCase() === 'high' || cls.priority?.toLowerCase() === 'urgent' ? 'red' : 'amber'} icon={<Zap className="w-3 h-3" />} />}
                              {cls.sentiment && <Chip label={cls.sentiment} color="sky" />}
                              {cls.confidence != null && (
                                <Chip label={`${(cls.confidence * 100).toFixed(0)}% conf`} color="slate" icon={<BarChart2 className="w-3 h-3" />} />
                              )}
                            </div>
                          )}

                          {/* Row 4: final response */}
                          <div className={`rounded-xl p-3 border ${
                            isEscalated
                              ? 'bg-red-950/20 border-red-500/20'
                              : isResolved
                                ? 'bg-emerald-950/20 border-emerald-500/20'
                                : 'bg-slate-900/40 border-slate-700/30'
                          }`}>
                            <span className={`text-xs font-semibold uppercase tracking-wider block mb-1 ${
                              isEscalated ? 'text-red-400' : isResolved ? 'text-emerald-400' : 'text-slate-500'
                            }`}>
                              {isEscalated ? 'Escalated — Human Review Required' : isResolved ? 'AI Final Response' : 'Pending Resolution'}
                            </span>
                            <p className={`text-xs leading-relaxed ${
                              isEscalated ? 'text-red-300/80' : isResolved ? 'text-emerald-300' : 'text-slate-500 italic'
                            }`}>
                              {resolution?.final_response || (isEscalated ? 'Escalated to human review.' : 'Not yet processed.')}
                            </p>
                          </div>
                        </div>

                        {/* Status badge */}
                        <div className="shrink-0">
                          {isEscalated ? (
                            <span className="flex items-center text-xs font-semibold text-red-400 bg-red-500/15 border border-red-500/30 px-2.5 py-1 rounded-full">
                              <ShieldAlert className="w-3 h-3 mr-1" /> Escalated
                            </span>
                          ) : isResolved ? (
                            <span className="flex items-center text-xs font-semibold text-emerald-400 bg-emerald-500/15 border border-emerald-500/30 px-2.5 py-1 rounded-full">
                              <CheckCircle className="w-3 h-3 mr-1" /> Resolved
                            </span>
                          ) : (
                            <span className="flex items-center text-xs font-semibold text-amber-400 bg-amber-500/15 border border-amber-500/30 px-2.5 py-1 rounded-full">
                              <Clock className="w-3 h-3 mr-1" /> Pending
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </section>
      )}
    </main>
  );
}

// ─── AgentTicketCard ──────────────────────────────────────────────────────────

function AgentTicketCard({ ticket, domain }: { ticket: Ticket; domain: string }) {
  const draft = ticket.ticket_drafts?.find(d => d.domain === domain) || ticket.ticket_drafts?.[0];
  const classification = ticket.ticket_classifications?.[0];
  const resolution = ticket.resolutions?.find(r => !r.escalated) || ticket.resolutions?.[0];

  return (
    <div className="bg-slate-900/60 rounded-2xl border border-slate-700/40 overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-slate-800/60">
        <div className="flex justify-between items-start mb-2">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Customer Issue</span>
          {resolution?.escalated && (
            <span className="bg-red-500/20 text-red-400 text-xs px-2 py-0.5 rounded-full border border-red-500/30 flex items-center">
              <ShieldAlert className="w-3 h-3 mr-1" /> Escalated
            </span>
          )}
        </div>
        <p className="text-slate-200 text-sm leading-relaxed">"{ticket.raw_text}"</p>
        {ticket.customer_email && (
          <p className="text-xs text-sky-400 mt-2 flex items-center">
            <Mail className="w-3 h-3 mr-1" /> {ticket.customer_email}
          </p>
        )}
        <p className="text-xs text-slate-600 mt-1 flex items-center">
          <Clock className="w-3 h-3 mr-1" /> {new Date(ticket.created_at).toLocaleString()}
        </p>
      </div>

      {/* Classification */}
      {classification && (
        <div className="px-4 py-3 border-b border-slate-800/60 flex flex-wrap gap-2">
          {classification.category && <Chip label={classification.category} color="indigo" icon={<Tag className="w-3 h-3" />} />}
          {classification.priority && <Chip label={classification.priority} color={classification.priority?.toLowerCase() === 'high' || classification.priority?.toLowerCase() === 'urgent' ? 'red' : 'amber'} icon={<Zap className="w-3 h-3" />} />}
          {classification.sentiment && <Chip label={classification.sentiment} color="sky" />}
          {classification.confidence != null && (
            <Chip label={`${(classification.confidence * 100).toFixed(0)}% confidence`} color="slate" icon={<BarChart2 className="w-3 h-3" />} />
          )}
        </div>
      )}

      {/* RAG Output */}
      <div className="px-4 py-3 border-b border-slate-800/60">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-amber-500 uppercase tracking-wider">RAG Retrieval</span>
          {draft?.rag_top_score != null ? (
            <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${
              draft.rag_top_score >= 0.5 ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30'
              : draft.rag_top_score >= 0.3 ? 'text-amber-400 bg-amber-500/10 border-amber-500/30'
              : 'text-red-400 bg-red-500/10 border-red-500/30'
            }`}>
              Score: {draft.rag_top_score.toFixed(3)}
            </span>
          ) : (
            <span className="text-xs text-slate-600">No score</span>
          )}
        </div>
        <p className="text-slate-400 text-xs leading-relaxed">
          {draft?.draft_text?.substring(0, 200) || 'No RAG draft generated.'}
          {(draft?.draft_text?.length || 0) > 200 ? '...' : ''}
        </p>
        {draft?.reflection_attempt != null && draft.reflection_attempt > 0 && (
          <p className="text-xs text-amber-500/70 mt-1 flex items-center">
            <RotateCcw className="w-3 h-3 mr-1" /> {draft.reflection_attempt} reflection attempt(s)
          </p>
        )}
      </div>

      {/* Final Response */}
      <div className="px-4 py-3">
        <span className="text-xs font-semibold text-emerald-500 uppercase tracking-wider flex items-center mb-2">
          <MessageSquare className="w-3 h-3 mr-1" /> Final Response
        </span>
        <p className="text-emerald-300 text-sm leading-relaxed">
          {resolution?.final_response || 'Pending resolution...'}
        </p>
      </div>
    </div>
  );
}

// ─── HumanReviewCard ──────────────────────────────────────────────────────────

function HumanReviewCard({ ticket }: { ticket: Ticket }) {
  const draft = ticket.ticket_drafts?.[0];
  const classification = ticket.ticket_classifications?.[0];
  const resolution = ticket.resolutions?.find(r => r.escalated);
  const escalationReasons = resolution?.escalation_reasons || [];
  
  const [isReplying, setIsReplying] = useState(false);
  const [replyText, setReplyText] = useState(draft?.draft_text || resolution?.final_response || "");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleResolve = async () => {
    if (!replyText.trim()) return;
    setIsSubmitting(true);
    try {
      await supabase.from('tickets').update({ status: 'resolved' }).eq('id', ticket.id);
      await supabase.from('resolutions').insert({
        ticket_id: ticket.id,
        final_response: replyText.trim(),
        escalated: false,
        resolved_at: new Date().toISOString()
      });
      
      // Embed to precedent memory
      try {
        await fetch('http://localhost:8600/embed_resolved_ticket', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ticket_id: ticket.id,
            ticket_text: ticket.raw_text,
            final_response: replyText.trim(),
            domain: ticket.ticket_classifications?.[0]?.category || 'General'
          })
        });
      } catch (embedError) {
        console.error("Failed to embed precedent memory", embedError);
      }
      
      window.location.reload();
    } catch (e) {
      console.error("Failed to resolve", e);
      setIsSubmitting(false);
    }
  };

  return (
    <div className="glass-panel rounded-2xl overflow-hidden border border-amber-500/20">
      <div className="p-4 border-b border-slate-700/50 flex justify-between items-start">
        <div>
          <span className="bg-red-500/20 text-red-400 text-xs font-semibold px-2.5 py-1 rounded-full border border-red-500/30 flex items-center w-fit">
            <AlertTriangle className="w-3 h-3 mr-1.5" /> Escalated to Human Review
          </span>
          {escalationReasons.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {escalationReasons.map(r => (
                <span key={r} className="text-xs bg-red-900/30 text-red-400 px-2 py-0.5 rounded border border-red-800/40">{r.replace(/_/g, ' ')}</span>
              ))}
            </div>
          )}
        </div>
        <span className="text-xs text-slate-500 whitespace-nowrap ml-2">{new Date(ticket.created_at).toLocaleDateString()}</span>
      </div>

      <div className="p-4 space-y-3">
        <div>
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Customer Issue</p>
          <p className="text-slate-200 text-sm leading-relaxed">"{ticket.raw_text}"</p>
          {ticket.customer_email && (
            <p className="text-xs text-sky-400 mt-1.5 flex items-center">
              <Mail className="w-3 h-3 mr-1" /> {ticket.customer_email}
            </p>
          )}
        </div>

        {classification && (
          <div className="flex flex-wrap gap-1.5">
            {classification.category && <Chip label={classification.category} color="indigo" icon={<Tag className="w-3 h-3" />} />}
            {classification.priority && <Chip label={classification.priority} color="amber" icon={<Zap className="w-3 h-3" />} />}
            {classification.sentiment && <Chip label={classification.sentiment} color="sky" />}
          </div>
        )}

        <div className="bg-[#0b1120] rounded-xl p-3 border border-slate-800">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-amber-500 uppercase tracking-wider">Best RAG Draft</span>
            {draft?.rag_top_score != null ? (
              <span className="text-xs font-bold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/30">
                Score: {draft.rag_top_score.toFixed(3)}
              </span>
            ) : <span className="text-xs text-slate-600">No score</span>}
          </div>
          <p className="text-slate-400 text-xs leading-relaxed">
            {resolution?.final_response || draft?.draft_text || 'No draft was generated.'}
          </p>
        </div>

        {!isReplying ? (
          <button 
            onClick={() => setIsReplying(true)}
            className="w-full bg-gradient-to-r from-indigo-500 to-sky-500 hover:from-indigo-400 hover:to-sky-400 text-white text-sm font-semibold py-2.5 rounded-xl transition-all duration-300">
            Take Over Review
          </button>
        ) : (
          <div className="mt-4 space-y-3">
            <textarea
              className="w-full bg-[#0b1120] text-slate-200 text-sm rounded-xl border border-slate-700 p-3 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none resize-none"
              rows={4}
              placeholder="Draft your response to the customer..."
              value={replyText}
              onChange={(e) => setReplyText(e.target.value)}
              disabled={isSubmitting}
            />
            <div className="flex gap-2">
              <button
                onClick={() => setIsReplying(false)}
                disabled={isSubmitting}
                className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-semibold py-2.5 rounded-xl transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleResolve}
                disabled={isSubmitting || !replyText.trim()}
                className="flex-1 bg-gradient-to-r from-emerald-500 to-emerald-400 hover:from-emerald-400 hover:to-emerald-300 text-white text-sm font-semibold py-2.5 rounded-xl transition-all disabled:opacity-50"
              >
                {isSubmitting ? <Loader2 className="w-4 h-4 mx-auto animate-spin" /> : 'Send & Resolve'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Helper Components ────────────────────────────────────────────────────────

function Chip({ label, color, icon }: { label: string; color: string; icon?: React.ReactNode }) {
  const colors: Record<string, string> = {
    indigo: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/25',
    sky: 'bg-sky-500/15 text-sky-300 border-sky-500/25',
    amber: 'bg-amber-500/15 text-amber-300 border-amber-500/25',
    red: 'bg-red-500/15 text-red-300 border-red-500/25',
    emerald: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/25',
    slate: 'bg-slate-700/50 text-slate-400 border-slate-600/30',
  };
  return (
    <span className={`inline-flex items-center text-xs px-2 py-0.5 rounded-full border font-medium capitalize ${colors[color] || colors.slate}`}>
      {icon && <span className="mr-1">{icon}</span>}
      {label}
    </span>
  );
}

function TabBtn({ active, onClick, icon, label, warn }: {
  active: boolean; onClick: () => void; icon: React.ReactNode; label: string; warn?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center space-x-2 px-5 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
        active
          ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 shadow-[0_0_15px_rgba(99,102,241,0.2)]'
          : 'text-slate-400 hover:text-white border border-transparent hover:border-slate-700/50 hover:bg-slate-800/50'
      }`}
    >
      <span className={warn && !active ? 'text-amber-400' : ''}>{icon}</span>
      <span>{label}</span>
    </button>
  );
}

function StatBadge({ label, value, color }: { label: string; value: number; color: string }) {
  const colors: Record<string, string> = {
    indigo: 'from-indigo-500/10 to-indigo-500/5 border-indigo-500/20 text-indigo-300',
    amber: 'from-amber-500/10 to-amber-500/5 border-amber-500/20 text-amber-300',
    emerald: 'from-emerald-500/10 to-emerald-500/5 border-emerald-500/20 text-emerald-300',
    sky: 'from-sky-500/10 to-sky-500/5 border-sky-500/20 text-sky-300',
  };
  return (
    <div className={`bg-gradient-to-br ${colors[color]} border rounded-2xl p-4`}>
      <p className="text-3xl font-bold text-white">{value}</p>
      <p className={`text-xs font-medium mt-1`}>{label}</p>
    </div>
  );
}

function SystemCard({ icon, label, status, uptime, color }: {
  icon: React.ReactNode; label: string; status: string; uptime: string; color: string;
}) {
  const colorMap: Record<string, string> = {
    emerald: 'text-emerald-400 bg-emerald-500/15 border-emerald-500/25',
    amber: 'text-amber-400 bg-amber-500/15 border-amber-500/25',
    sky: 'text-sky-400 bg-sky-500/15 border-sky-500/25',
  };
  return (
    <div className="glass-panel p-5 rounded-2xl">
      <div className="flex justify-between items-start mb-3">
        <div className={`p-2.5 rounded-xl border ${colorMap[color]}`}>{icon}</div>
        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${colorMap[color]}`}>{status}</span>
      </div>
      <h3 className="font-semibold text-slate-200 text-sm">{label}</h3>
      <p className="text-xs text-slate-500 mt-0.5">Uptime: {uptime}</p>
    </div>
  );
}
