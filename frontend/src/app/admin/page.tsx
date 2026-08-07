'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useRouter } from 'next/navigation';
import {
  Activity, Settings, Database, Server, Cpu, LogOut, Loader2,
  ChevronDown, ChevronUp, AlertTriangle, CheckCircle, Mail, Clock,
  BarChart2, MessageSquare, ShieldAlert, Tag, Zap, ArrowLeft, Bot,
  CreditCard, Wrench, Brain, GitBranch, Eye, RotateCcw, ArrowRightLeft,
  Shield, Layers, CheckCircle2, Trash2, Image as ImageIcon,
} from 'lucide-react';
import { supabase } from '../../lib/supabase';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8600';

function parseAdminResponse(text: string | null | undefined): React.ReactNode {
  if (!text) return 'No final response was produced.';
  if (text.includes('**[INTERNAL TECHNICAL REPORT]**') && text.includes('**[CUSTOMER RESPONSE]**')) {
    const parts = text.split('**[CUSTOMER RESPONSE]**');
    const techReport = parts[0].replace('**[INTERNAL TECHNICAL REPORT]**', '').trim();
    const custResponse = parts[1].trim();
    
    return (
      <div className="space-y-4">
        <div className="bg-indigo-950/30 border border-indigo-500/20 p-3 rounded-xl">
          <span className="text-[10px] uppercase tracking-wider text-indigo-400 block mb-1 font-bold">Internal Technical Details</span>
          <p className="text-indigo-200 text-sm">{techReport}</p>
        </div>
        <div className="bg-emerald-950/30 border border-emerald-500/20 p-3 rounded-xl">
          <span className="text-[10px] uppercase tracking-wider text-emerald-400 block mb-1 font-bold">Customer Facing Output</span>
          <p className="text-emerald-200 text-sm">{custResponse}</p>
        </div>
      </div>
    );
  }
  return <p>{text}</p>;
}

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
  raw_graph_payload?: any;
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
  const [activeTab, setActiveTab] = useState<'agents' | 'pipeline' | 'human_review' | 'resolved' | 'all_tickets'>('agents');
  const [dataLoading, setDataLoading] = useState(false);
  const [debugInfo, setDebugInfo] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');

  const isFullyLoaded = !loading && !roleLoading;

  useEffect(() => {
    if (!isFullyLoaded) return;
    if (!user || role !== 'admin') {
      router.push('/login');
      return;
    }
    fetchData();
  }, [isFullyLoaded, user, role]);

  const handleDeleteTicket = async (ticketId: string) => {
    if (!confirm("Are you sure you want to permanently delete this ticket from the system?")) return;
    try {
      // Bypass gateway/sidecar and delete directly via our Next.js API
      const res = await fetch(`/api/tickets?id=${ticketId}`, { 
        method: 'DELETE'
      });
      
      if (res.ok) {
        sessionStorage.removeItem('tickets:list:metadata');
        fetchData();
      } else {
        alert("Failed to delete ticket.");
      }
    } catch (e) {
      console.error(e);
      alert("Error deleting ticket.");
    }
  };

  const fetchData = useCallback(async () => {
    setDataLoading(true);
    setDebugInfo('');
    try {
      // 1. Client-Side Cache Check
      const clientCacheStr = sessionStorage.getItem('tickets:list:metadata');
      if (clientCacheStr) {
        try {
          const parsedCache = JSON.parse(clientCacheStr);
          if (parsedCache.timestamp && (Date.now() - parsedCache.timestamp < 30000)) {
            setAllTickets(parsedCache.data || []);
            setDataLoading(false);
            return;
          }
        } catch (e) {}
      }

      // 2. Fetch from Next.js API (which checks Redis)
      const res = await fetch('/api/tickets');
      const json = await res.json();

      if (!res.ok) {
        setDebugInfo(`Ticket fetch error: ${json.error}`);
      } else {
        setAllTickets(json.data || []);
        // Save to Client Cache
        sessionStorage.setItem('tickets:list:metadata', JSON.stringify({
          timestamp: Date.now(),
          data: json.data || []
        }));
      }
    } catch (e: any) {
       setDebugInfo(`Fetch error: ${e.message}`);
    } finally {
      setDataLoading(false);
    }
  }, []);

  // Group tickets by agent domain based on ticket_drafts domain
  const getAgentTickets = (agentDomain: string) => {
    return allTickets.filter(t => {
      return t.ticket_drafts?.some(d => d.domain === agentDomain);
    }).filter(t => {
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

  const humanReviewTickets = allTickets.filter(t => {
    const isResolved = t.resolutions?.some(r => !r.escalated);
    if (isResolved) return false;
    return t.resolutions?.some(r => r.escalated) || (!t.resolutions?.length && t.status === 'escalated');
  });

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
        <TabBtn active={activeTab === 'resolved'} onClick={() => setActiveTab('resolved')} icon={<CheckCircle2 className="w-4 h-4" />} label={`Resolved (${resolvedTickets.length})`} />
        <TabBtn active={activeTab === 'all_tickets'} onClick={() => setActiveTab('all_tickets')} icon={<MessageSquare className="w-4 h-4" />} label={`All Tickets (${allTickets.length})`} />
      </div>

      {/* ── AI Agents Tab ───────────────────────────────────────────────────── */}
      {activeTab === 'agents' && (
        <section className="glass-panel rounded-3xl overflow-hidden animate-fade-in" style={{ animationDelay: '0.25s' }}>
          <div className="p-6 border-b border-slate-700/50 bg-slate-900/50 flex justify-between items-center">
            <h2 className="text-lg font-mono tracking-widest uppercase text-white flex items-center">
              <Bot className="w-5 h-5 mr-2 text-[#00E5FF]" /> AI Agents
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
                          <div className="p-6 bg-slate-900/40">
                          <div className="flex flex-col">
                              {agentTickets.map(t => (
                                <TicketRow key={t.id} ticket={t} role="agent" onDelete={handleDeleteTicket} />
                              ))}
                            </div>
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
            <HumanReviewTabs humanReviewTickets={humanReviewTickets} onDelete={handleDeleteTicket} />
          )}
        </section>
      )}

      {/* ── Resolved Tab ────────────────────────────────────────────────────── */}
      {activeTab === 'resolved' && (
        <section className="animate-fade-in" style={{ animationDelay: '0.25s' }}>
          {resolvedTickets.length === 0 ? (
            <div className="glass-panel rounded-3xl p-16 text-center">
              <CheckCircle2 className="w-14 h-14 text-emerald-500/50 mx-auto mb-4" />
              <p className="text-slate-300 font-semibold text-lg">No resolved tickets yet</p>
              <p className="text-slate-500 text-sm mt-1">Tickets will appear here once they are resolved.</p>
            </div>
          ) : (
            <div className="flex flex-col">
              {resolvedTickets.map(ticket => (
                <TicketRow key={ticket.id} ticket={ticket} role="all" onDelete={handleDeleteTicket} />
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
              <div className="flex items-center space-x-3">
                <input
                  type="text"
                  placeholder="Search by Ticket UUID..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="bg-slate-800/50 border border-slate-700 text-slate-200 text-xs px-3 py-1.5 rounded-lg w-64 focus:outline-none focus:border-indigo-500 transition-colors"
                />
                <button onClick={fetchData} disabled={dataLoading} className="text-xs text-slate-400 hover:text-white transition-colors flex items-center">
                  {dataLoading ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Activity className="w-3 h-3 mr-1" />}
                  Refresh
                </button>
              </div>
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
              <div className="flex flex-col">
                {allTickets
                  .filter(ticket => !searchQuery || ticket.id.toLowerCase().includes(searchQuery.toLowerCase()))
                  .map(ticket => (
                    <TicketRow key={ticket.id} ticket={ticket} role="all" onDelete={handleDeleteTicket} />
                ))}
              </div>
            )}
          </div>
        </section>
      )}
    </main>
  );
}

// ─── HumanReviewTabs ────────────────────────────────────────────────────────────

function HumanReviewTabs({ humanReviewTickets, onDelete }: { humanReviewTickets: Ticket[], onDelete?: (id: string) => void }) {
  const [activeSubTab, setActiveSubTab] = useState<'billing' | 'technical' | 'other'>('other');

  const billingTickets = humanReviewTickets.filter(t => ['billing', 'account', 'Billing', 'Account'].includes(t.ticket_classifications?.[0]?.category || ''));
  const technicalTickets = humanReviewTickets.filter(t => ['technical', 'Technical'].includes(t.ticket_classifications?.[0]?.category || ''));
  const otherTickets = humanReviewTickets.filter(t => !['billing', 'account', 'Billing', 'Account', 'technical', 'Technical'].includes(t.ticket_classifications?.[0]?.category || ''));

  let activeTickets = otherTickets;
  if (activeSubTab === 'billing') activeTickets = billingTickets;
  if (activeSubTab === 'technical') activeTickets = technicalTickets;

  return (
    <div className="flex flex-col space-y-4">
      <div className="flex space-x-2 border-b border-[#222222] pb-4">
        <button
          onClick={() => setActiveSubTab('billing')}
          className={`px-4 py-2 text-sm font-mono tracking-widest uppercase transition-colors ${activeSubTab === 'billing' ? 'text-[#00E5FF] border-b-2 border-[#00E5FF]' : 'text-[#888888] hover:text-[#ececec]'}`}
        >
          Billing ({billingTickets.length})
        </button>
        <button
          onClick={() => setActiveSubTab('technical')}
          className={`px-4 py-2 text-sm font-mono tracking-widest uppercase transition-colors ${activeSubTab === 'technical' ? 'text-[#FF3366] border-b-2 border-[#FF3366]' : 'text-[#888888] hover:text-[#ececec]'}`}
        >
          Technical ({technicalTickets.length})
        </button>
        <button
          onClick={() => setActiveSubTab('other')}
          className={`px-4 py-2 text-sm font-mono tracking-widest uppercase transition-colors ${activeSubTab === 'other' ? 'text-[#FFD600] border-b-2 border-[#FFD600]' : 'text-[#888888] hover:text-[#ececec]'}`}
        >
          Other / Uncategorized ({otherTickets.length})
        </button>
      </div>

      <div className="flex flex-col">
        {activeTickets.length === 0 ? (
          <div className="p-8 text-center border border-[#222222] bg-[#111111] text-[#888888] font-mono text-sm">
            NO TICKETS IN THIS CATEGORY.
          </div>
        ) : (
          activeTickets.map(ticket => (
            <TicketRow key={ticket.id} ticket={ticket} role="human" onDelete={onDelete} />
          ))
        )}
      </div>
    </div>
  );
}

// ─── TicketRow (Unified Admin View) ──────────────────────────────────────────────────────────

export function TicketRow({ ticket, role, onDelete }: { ticket: Ticket; role: 'agent' | 'human' | 'all', onDelete?: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const [fullData, setFullData] = useState<Ticket | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const draft = fullData?.ticket_drafts?.[0] || ticket.ticket_drafts?.[0];
  const classification = fullData?.ticket_classifications?.[0] || ticket.ticket_classifications?.[0];
  const isEscalated = ticket.resolutions?.some(r => r.escalated) || ticket.status === 'escalated';
  const resolutionMetadata = ticket.resolutions?.find(r => !r.escalated) || ticket.resolutions?.[0];
  const isResolved = !isEscalated && resolutionMetadata;
  const resolution = fullData?.resolutions?.find(r => !r.escalated) || resolutionMetadata;
  
  const [isReplying, setIsReplying] = useState(false);
  const [replyText, setReplyText] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (expanded && !fullData && !isLoading) {
      setIsLoading(true);
      supabase.from('tickets').select(`
        *,
        ticket_drafts (*),
        ticket_classifications (*),
        resolutions (*)
      `).eq('id', ticket.id).single().then(({ data }) => {
        setFullData(data as any);
        setIsLoading(false);
        const fetchedDraft = data?.ticket_drafts?.[0];
        const fetchedRes = data?.resolutions?.find((r: any) => !r.escalated);
        setReplyText(fetchedDraft?.draft_text || fetchedRes?.final_response || "");
      });
    }
  }, [expanded, fullData, isLoading, ticket.id]);

  // Status mapping
  let statusColor = '#888888';
  let statusLabel = 'PENDING';
  if (isEscalated) { statusColor = '#FFD600'; statusLabel = 'REQUIRES REVIEW'; }
  else if (isResolved) { statusColor = '#00FF66'; statusLabel = 'COMPLETED'; }

  // Extract snippet
  const textParts = ticket.raw_text.split('[OCR EXTRACTED TEXT FROM ATTACHMENT]');
  const issueSnippet = textParts[0].trim().substring(0, 80) + (textParts[0].length > 80 ? '...' : '');

  // Handle Resolve (for human review)
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
      
      try {
        await fetch(`${API_URL}/embed_resolved_ticket`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ticket_id: ticket.id,
            ticket_text: ticket.raw_text,
            final_response: replyText.trim(),
            domain: ticket.ticket_classifications?.[0]?.category || 'General'
          })
        });
      } catch (embedError) {}
      
      try {
        await fetch('/api/tickets', { method: 'DELETE' });
        sessionStorage.removeItem('tickets:list:metadata');
      } catch (e) {}
      
      window.location.reload();
    } catch (e) {
      console.error("Failed to resolve", e);
      setIsSubmitting(false);
    }
  };

  return (
    <div className="border border-[#222222] bg-[#111111] mb-2 transition-all duration-200 hover:border-[#444444]">
      {/* Unexpanded Row (Clickable) */}
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
          {ticket.raw_graph_payload?.processing_time_ms && (
             <span className="text-[10px] text-[#00E5FF] font-mono w-20 shrink-0 bg-[#00E5FF]/10 px-1.5 py-0.5 rounded text-center truncate">
               {(ticket.raw_graph_payload.processing_time_ms / 1000).toFixed(2)}s
             </span>
          )}
          <span className="text-sm text-[#ececec] truncate font-sans">{issueSnippet}</span>
        </div>
        
        <div className="flex items-center space-x-6 shrink-0 pl-4">
          <span className="text-[10px] font-mono tracking-widest" style={{ color: statusColor }}>[{statusLabel}]</span>
          {onDelete && (
            <button onClick={(e) => { e.stopPropagation(); onDelete(ticket.id); }} className="text-[#555555] hover:text-[#FF3366] transition-colors flex items-center h-full">
              <Trash2 className="w-4 h-4" />
            </button>
          )}
          {expanded ? <ChevronUp className="w-4 h-4 text-[#888888]" /> : <ChevronDown className="w-4 h-4 text-[#888888]" />}
        </div>
      </div>

      {/* Expanded Grid */}
      {expanded && (
        <div className="border-t border-[#222222] p-6 bg-[#050505] grid grid-cols-1 lg:grid-cols-2 gap-8">
          
          {/* Left Column: Issue & OCR */}
          <div className="space-y-6">
            <div>
              <span className="text-[10px] font-mono tracking-widest text-[#00E5FF] uppercase block mb-2">RAW_INPUT</span>
              <p className="text-sm text-[#ececec] leading-relaxed font-sans whitespace-pre-wrap">"{textParts[0].trim()}"</p>
            </div>
            
            {textParts.length > 1 && (
              <div className="border-l border-[#00E5FF] pl-4 py-1">
                <span className="text-[10px] font-mono tracking-widest text-[#00E5FF] uppercase block mb-2 flex items-center">
                  <ImageIcon className="w-3 h-3 mr-1.5" /> OCR_EXTRACTION
                </span>
                <pre className="text-xs text-[#888888] whitespace-pre-wrap font-mono bg-[#111111] p-3 border border-[#222222]">
                  {textParts[1].trim()}
                </pre>
              </div>
            )}
            
            {ticket.customer_email && (
              <span className="text-[10px] text-[#888888] font-mono block">USER: {ticket.customer_email}</span>
            )}
            
            {/* Signature Element: Telemetry Track */}
            {classification && (
              <div className="mt-6 pt-4 border-t border-[#222222]">
                <span className="text-[10px] font-mono tracking-widest text-[#888888] block mb-2">PIPELINE_TELEMETRY</span>
                <div className="flex flex-wrap gap-2">
                  <span className="text-[10px] font-mono bg-[#111111] border border-[#222222] px-2 py-1 text-[#ececec]">CAT: {classification.category?.toUpperCase() || 'UNKNOWN'}</span>
                  <span className="text-[10px] font-mono bg-[#111111] border border-[#222222] px-2 py-1" style={{ color: classification.priority?.toLowerCase() === 'high' ? '#FFD600' : '#888888' }}>PRI: {classification.priority?.toUpperCase()}</span>
                  {classification.confidence && (
                    <span className="text-[10px] font-mono bg-[#111111] border border-[#222222] px-2 py-1 text-[#00E5FF]">CONF: {(classification.confidence * 100).toFixed(0)}%</span>
                  )}
                </div>
              </div>
            )}
            
            {fullData?.raw_graph_payload && (
              <div className="mt-4 border border-[#222222] bg-[#111111] p-3">
                <span className="text-[10px] font-mono tracking-widest text-[#555555] uppercase block mb-2">GRAPH_PAYLOAD</span>
                <pre className="text-[10px] text-[#555555] overflow-x-auto font-mono max-h-32">
                  {JSON.stringify(fullData.raw_graph_payload, null, 2)}
                </pre>
              </div>
            )}
            
            {isLoading && (
              <div className="mt-4 flex items-center text-[10px] font-mono text-[#888888]">
                <Loader2 className="w-3 h-3 animate-spin mr-2 text-[#00E5FF]" /> FETCHING_FULL_PAYLOAD...
              </div>
            )}
          </div>
          
          {/* Right Column: AI Processing / Resolution */}
          <div className="space-y-6 flex flex-col h-full">
            <div className="flex-1">
              <div className="flex justify-between items-center mb-2">
                <span className="text-[10px] font-mono tracking-widest text-[#00FF66] uppercase">SYS_RESOLUTION</span>
                {draft?.rag_top_score != null && (
                  <span className="text-[10px] font-mono tracking-widest text-[#888888]">RAG_SCORE: {draft.rag_top_score.toFixed(3)}</span>
                )}
              </div>
              
              <div className="bg-[#111111] border border-[#222222] p-4 min-h-[150px] font-sans text-sm text-[#ececec]">
                 {resolution?.final_response ? parseAdminResponse(resolution.final_response) : (draft?.draft_text ? parseAdminResponse(draft.draft_text) : 'AWAITING PROCESS...')}
              </div>
            </div>
            
            {/* Human Review Override Actions */}
            {(role === 'human' || (role === 'all' && isEscalated)) && !isReplying && (
              <button 
                onClick={() => setIsReplying(true)}
                className="w-full bg-transparent border border-[#00E5FF] text-[#00E5FF] hover:bg-[#00E5FF] hover:text-[#050505] transition-colors py-3 text-xs font-mono tracking-widest uppercase">
                CLAIM_TICKET_FOR_REVIEW
              </button>
            )}
            
            {(role === 'human' || (role === 'all' && isEscalated)) && isReplying && (
              <div className="space-y-3">
                <textarea
                  className="w-full bg-[#111111] border border-[#FFD600] text-[#ececec] text-sm p-3 font-sans focus:outline-none resize-none"
                  rows={4}
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  disabled={isSubmitting}
                />
                <div className="flex gap-2">
                  <button onClick={() => setIsReplying(false)} className="flex-1 border border-[#222222] bg-transparent text-[#888888] hover:text-[#ececec] hover:bg-[#222222] transition-colors py-3 text-[10px] font-mono tracking-widest">ABORT</button>
                  <button onClick={handleResolve} disabled={!replyText.trim() || isSubmitting} className="flex-1 bg-[#FFD600] text-[#050505] hover:bg-yellow-400 transition-colors py-3 text-[10px] font-mono tracking-widest font-bold">
                    {isSubmitting ? 'COMMITTING...' : 'COMMIT_RESOLUTION'}
                  </button>
                </div>
              </div>
            )}
            
          </div>
        </div>
      )}
    </div>
  );
}

// ─── HumanReviewCard ──────────────────────────────────────────────────────────

// HumanReviewCard has been deprecated and merged into TicketRow.

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
