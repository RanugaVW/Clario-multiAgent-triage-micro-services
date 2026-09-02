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
import { StatusBadge } from '../../components/ui';
import { supabase } from '../../lib/supabase';
import { WavePhysicsLoader } from '../../components/WavePhysicsLoader';
import ShakeButton from '../../components/ShakeButton';
import { formatDate, formatDateTime, formatElapsed, formatDuration, formatRelative, formatTime } from '../../lib/datetime';
import { fetchJson } from '../../lib/fetchJson';
import RotateButton from '../../components/RotateButton';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8600';

function parseAdminResponse(text: string | null | undefined): React.ReactNode {
  if (!text) return 'No final response was produced.';
  if (text.includes('**[INTERNAL TECHNICAL REPORT]**') && text.includes('**[CUSTOMER RESPONSE]**')) {
    const parts = text.split('**[CUSTOMER RESPONSE]**');
    const techReport = parts[0].replace('**[INTERNAL TECHNICAL REPORT]**', '').trim();
    const custResponse = parts[1].trim();

    return (
      <div className="space-y-4">
        <div className="bg-[#2DD4BF]/10 border border-[#2DD4BF]/20 p-3 rounded-xl">
          <span className="text-xs uppercase tracking-wider text-[#2DD4BF] block mb-1 font-bold">Internal technical details</span>
          <p className="text-[#99f6e4] text-sm">{techReport}</p>
        </div>
        <div className="bg-[#E8A33D]/10 border border-[#E8A33D]/20 p-3 rounded-xl">
          <span className="text-xs uppercase tracking-wider text-[#E8A33D] block mb-1 font-bold">Customer-facing output</span>
          <p className="text-[#fbd999] text-sm">{custResponse}</p>
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
  low_relevance?: boolean | null;
};

type TicketClassification = {
  category: string | null;
  priority: string | null;
  sentiment: string | null;
  confidence: number | null;
  source?: string | null;
};

type Resolution = {
  id: string;
  final_response: string | null;
  escalated: boolean;
  escalation_reasons: string[] | null;
  resolved_at: string;
  total_reflection_count: number | null;
  total_llm_calls?: number | null;
  total_latency_ms?: number | null;
  resolved_by?: string | null;
  ticket_id: string;
};

type Ticket = {
  id: string;
  raw_text: string;
  subject: string | null;
  customer_email: string | null;
  status: string;
  created_at: string;
  updated_at?: string | null;
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
      const json = await fetchJson('/api/tickets');
      setAllTickets(json.data || []);
      // Save to Client Cache
      sessionStorage.setItem('tickets:list:metadata', JSON.stringify({
        timestamp: Date.now(),
        data: json.data || []
      }));
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
        <Loader2 className="w-10 h-10 animate-spin text-[#E8A33D]" />
        <p className="text-[#8A8F98] text-sm">Loading admin workspace...</p>
      </div>
    );
  }

  return (
    <main className="min-h-screen py-8 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <header className="flex justify-between items-center mb-10 animate-fade-in">
        <div className="flex items-center space-x-3">
          <div className="bg-[#2DD4BF]/15 p-2 rounded-xl border border-[#2DD4BF]/25">
            <Settings className="text-[#2DD4BF] w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[#ECECEC]">System administration</h1>
            <p className="text-sm text-[#8A8F98]">Clario Platform — {user?.email}</p>
          </div>
        </div>
        <div className="flex items-center space-x-3">
          <button onClick={() => router.push('/')} className="flex items-center text-sm text-[#8A8F98] hover:text-[#ECECEC] transition-colors px-3 py-2 rounded-lg hover:bg-white/[0.06]">
            <ArrowLeft className="w-4 h-4 mr-1.5" /> Back to triage
          </button>
          <button onClick={handleLogout} className="p-2 hover:bg-white/[0.06] rounded-full transition-colors text-[#8A8F98] hover:text-[#FB7185]" title="Sign Out">
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
        <StatBadge label="Total tickets" value={allTickets.length} color="indigo" />
        <StatBadge label="Auto-resolved" value={resolvedTickets.length} color="emerald" />
        <StatBadge label="Human review" value={humanReviewTickets.length} color="amber" />
        <StatBadge label="AI agents active" value={2} color="sky" />
      </div>

      {/* ── Debug ───────────────────────────────────────────────────────────── */}
      {debugInfo && (
        <div className="mb-6 bg-[#FB7185]/10 border border-[#FB7185]/30 rounded-xl p-4 text-[#FB7185] text-sm">
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
        <section className="glass-panel rounded-[28px] overflow-hidden animate-fade-in" style={{ animationDelay: '0.25s' }}>
          <div className="p-6 border-b border-white/10 flex justify-between items-center">
            <h2 className="text-lg font-semibold text-[#ECECEC] flex items-center">
              <Bot className="w-5 h-5 mr-2 text-[#2DD4BF]" /> AI agents
            </h2>
            <RotateButton onClick={fetchData} isLoading={dataLoading} />
          </div>

          {dataLoading ? (
            <div className="p-16 flex justify-center"><Loader2 className="w-8 h-8 animate-spin text-[#E8A33D]" /></div>
          ) : (
            <div className="divide-y divide-white/10">
              {AI_AGENTS.map((agent) => {
                const agentTickets = getAgentTickets(agent.domain);
                const Icon = agent.icon;
                const colorMap: Record<string, string> = {
                  emerald: 'text-emerald-400 bg-emerald-500/15 border-emerald-500/25',
                  sky: 'text-[#2DD4BF] bg-[#2DD4BF]/15 border-[#2DD4BF]/25',
                };
                return (
                  <div key={agent.id} className="flex flex-col">
                    <div
                      className="p-5 flex items-center justify-between cursor-pointer hover:bg-white/[0.04] transition-colors"
                      onClick={() => setExpandedAgentId(prev => prev === agent.id ? null : agent.id)}
                    >
                      <div className="flex items-center space-x-4">
                        <div className={`w-12 h-12 rounded-2xl border flex items-center justify-center ${colorMap[agent.color]}`}>
                          <Icon className="w-6 h-6" />
                        </div>
                        <div>
                          <p className="font-semibold text-[#ECECEC] text-base">{agent.name}</p>
                          <p className="text-xs text-[#8A8F98] mt-0.5">{agent.description}</p>
                          <p className="text-xs mt-1 flex items-center">
                            <span className={`w-1.5 h-1.5 rounded-full mr-1.5 animate-pulse ${agent.color === 'emerald' ? 'bg-emerald-400' : 'bg-[#2DD4BF]'}`} />
                            <span className={agent.color === 'emerald' ? 'text-emerald-400' : 'text-[#2DD4BF]'}>Active — RAG domain: <strong>{agent.domain}</strong></span>
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-6">
                        <div className="text-right">
                          <p className="text-2xl font-bold text-[#ECECEC]">{agentTickets.length}</p>
                          <p className="text-xs text-[#8A8F98]">Tickets handled</p>
                        </div>
                        {expandedAgentId === agent.id ? <ChevronUp className="w-5 h-5 text-[#8A8F98]" /> : <ChevronDown className="w-5 h-5 text-[#8A8F98]" />}
                      </div>
                    </div>

                    {expandedAgentId === agent.id && (
                      <div className="px-5 pb-5 border-t border-white/10">
                        {agentTickets.length === 0 ? (
                          <p className="text-[#8A8F98] italic text-sm text-center py-8">No tickets handled by this agent yet. Submit a ticket to see it here.</p>
                        ) : (
                          <div className="p-6">
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
          <div className="glass-panel rounded-[28px] p-6 mb-6">
            <h2 className="text-base font-semibold text-[#ECECEC] mb-1 flex items-center">
              <Layers className="w-4 h-4 mr-2 text-[#E8A33D]" /> LangGraph pipeline architecture
            </h2>
            <p className="text-sm text-[#8A8F98]">All nodes run sequentially within the LangGraph state machine. The <code className="bg-white/[0.06] px-1 rounded text-[#E8A33D]">TicketState</code> blackboard is passed between nodes.</p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {PIPELINE_NODES.map((node, i) => {
              const Icon = node.icon;
              return (
                <div key={node.id} className="rounded-2xl backdrop-blur-md bg-white/[0.03] border border-white/[0.08] p-5 relative overflow-hidden">
                  <div className="absolute top-3 right-3 text-white/20 text-xs font-bold">#{i + 1}</div>
                  <div className="bg-[#E8A33D]/15 border border-[#E8A33D]/25 w-10 h-10 rounded-xl flex items-center justify-center mb-3">
                    <Icon className="w-5 h-5 text-[#E8A33D]" />
                  </div>
                  <p className="font-semibold text-[#ECECEC] text-sm mb-1">{node.name}</p>
                  <p className="text-xs text-[#8A8F98] leading-relaxed">{node.description}</p>
                  <div className="mt-3 flex items-center">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5 animate-pulse" />
                    <span className="text-xs text-emerald-400">Active</span>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-6 glass-panel rounded-2xl p-5">
            <h3 className="text-sm font-semibold text-[#ECECEC] mb-3 flex items-center">
              <BarChart2 className="w-4 h-4 mr-2 text-[#2DD4BF]" /> Processing stats
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="rounded-2xl bg-white/[0.03] p-3 text-center">
                <p className="text-xl font-bold text-[#ECECEC]">{allTickets.length}</p>
                <p className="text-xs text-[#8A8F98]">Total processed</p>
              </div>
              <div className="rounded-2xl bg-white/[0.03] p-3 text-center">
                <p className="text-xl font-bold text-emerald-400">{resolvedTickets.length}</p>
                <p className="text-xs text-[#8A8F98]">Auto-resolved</p>
              </div>
              <div className="rounded-2xl bg-white/[0.03] p-3 text-center">
                <p className="text-xl font-bold text-[#FB923C]">{humanReviewTickets.length}</p>
                <p className="text-xs text-[#8A8F98]">Escalated</p>
              </div>
              <div className="rounded-2xl bg-white/[0.03] p-3 text-center">
                <p className="text-xl font-bold text-[#2DD4BF]">
                  {allTickets.length > 0 ? Math.round((resolvedTickets.length / allTickets.length) * 100) : 0}%
                </p>
                <p className="text-xs text-[#8A8F98]">Auto-resolve rate</p>
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
                <RotateButton onClick={fetchData} isLoading={dataLoading} />
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
  const allResolutions = fullData?.resolutions || ticket.resolutions || [];
  const hasResolvedResolution = allResolutions.some(r => !r.escalated);
  const isEscalated = !hasResolvedResolution && (allResolutions.some(r => r.escalated) || ticket.status === 'escalated');
  const resolutionMetadata = allResolutions.find(r => !r.escalated) || allResolutions[0];
  const isResolved = hasResolvedResolution || ticket.status === 'resolved';
  const resolution = resolutionMetadata;
  const updatedAt = fullData?.updated_at || ticket.updated_at || null;
  const retrievedSources = Array.isArray(draft?.retrieved_sources) ? draft.retrieved_sources : [];
  const escalationReasons: string[] = allResolutions
    .flatMap(r => (Array.isArray(r.escalation_reasons) ? r.escalation_reasons : []))
    .map(r => String(r));

  // Ticks only on the client so the "open for" clock stays live without an SSR mismatch.
  const [nowIso, setNowIso] = useState<string | null>(null);
  useEffect(() => {
    if (!expanded) return;
    setNowIso(new Date().toISOString());
    const timer = setInterval(() => setNowIso(new Date().toISOString()), 30000);
    return () => clearInterval(timer);
  }, [expanded]);

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
  let statusColor = '#8A8F98';
  let statusLabel = 'Pending';
  let statusTone: 'neutral' | 'warning' | 'success' = 'neutral';
  if (isEscalated) { statusColor = '#FB923C'; statusLabel = 'Needs review'; statusTone = 'warning'; }
  else if (isResolved) { statusColor = '#34D399'; statusLabel = 'Resolved'; statusTone = 'success'; }

  // Extract snippet
  const textParts = ticket.raw_text.split('[OCR EXTRACTED TEXT FROM ATTACHMENT]');
  const issueSnippet = textParts[0].trim().substring(0, 80) + (textParts[0].length > 80 ? '...' : '');

  // Handle Resolve (for human review)
  const handleResolve = async () => {
    if (!replyText.trim()) return;
    setIsSubmitting(true);
    try {
      const res = await fetch('/api/tickets', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: ticket.id,
          final_response: replyText.trim()
        })
      });
      if (!res.ok) throw new Error("Failed to resolve via API");

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
    <div className="rounded-2xl backdrop-blur-md bg-white/[0.03] border border-white/[0.08] mb-2 transition-all duration-200 hover:border-white/20 overflow-hidden">
      {/* Unexpanded Row (Clickable) */}
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
          {ticket.raw_graph_payload?.processing_time_ms && (
             <span className="text-[11px] text-[#2DD4BF] font-mono w-20 shrink-0 bg-[#2DD4BF]/10 px-1.5 py-0.5 rounded-full text-center truncate">
               {(ticket.raw_graph_payload.processing_time_ms / 1000).toFixed(2)}s
             </span>
          )}
          <span className="text-sm text-[#ECECEC] truncate font-sans">{issueSnippet}</span>
        </div>

        <div className="flex items-center space-x-6 shrink-0 pl-4">
          <StatusBadge label={statusLabel} tone={statusTone} />
          {onDelete && (
            <ShakeButton onDelete={(e) => { e.stopPropagation(); onDelete(ticket.id); }} />
          )}
          {expanded ? <ChevronUp className="w-4 h-4 text-[#8A8F98]" /> : <ChevronDown className="w-4 h-4 text-[#8A8F98]" />}
        </div>
      </div>

      {/* Expanded Grid */}
      {expanded && (
        <div className="border-t border-white/10 p-6 grid grid-cols-1 lg:grid-cols-2 gap-8">

          {/* Metadata strip: everything about the ticket that is not its body */}
          <div className="lg:col-span-2 rounded-2xl border border-white/10 bg-white/[0.03] p-4">
            <span className="text-xs text-[#8A8F98] block mb-3">Ticket details</span>
            <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-x-6 gap-y-4">
              <MetaItem label="Ticket ID" value={ticket.id} mono title={ticket.id} />
              <MetaItem label="Subject" value={ticket.subject || fullData?.subject || 'No subject'} />
              <MetaItem label="Requester" value={ticket.customer_email || fullData?.customer_email || 'Anonymous'} title={ticket.customer_email || undefined} />
              <MetaItem label="Status" value={statusLabel} color={statusColor} />
              <MetaItem label="Submitted" value={formatDateTime(ticket.created_at)} hint={formatRelative(ticket.created_at)} />
              <MetaItem label="Last update" value={formatDateTime(updatedAt)} hint={updatedAt ? formatRelative(updatedAt) : undefined} />
              <MetaItem
                label="Resolved at"
                value={resolution?.resolved_at ? formatDateTime(resolution.resolved_at) : (isEscalated ? 'Awaiting human review' : 'In progress')}
                color={resolution?.resolved_at ? '#34D399' : statusColor}
              />
              <MetaItem
                label={resolution?.resolved_at ? 'Turnaround' : 'Open for'}
                value={resolution?.resolved_at ? formatElapsed(ticket.created_at, resolution.resolved_at) : formatElapsed(ticket.created_at, nowIso)}
              />
              <MetaItem
                label="Pipeline time"
                value={
                  ticket.raw_graph_payload?.processing_time_ms != null
                    ? formatDuration(ticket.raw_graph_payload.processing_time_ms)
                    : (resolution?.total_latency_ms != null ? formatDuration(resolution.total_latency_ms) : '—')
                }
                color="#2DD4BF"
              />
              <MetaItem label="Reflections" value={String(resolution?.total_reflection_count ?? draft?.reflection_attempt ?? 0)} />
              <MetaItem label="LLM calls" value={resolution?.total_llm_calls != null ? String(resolution.total_llm_calls) : '—'} />
              <MetaItem label="Routed domain" value={(draft?.domain || classification?.category || 'unrouted')} mono />
            </div>

            {escalationReasons.length > 0 && (
              <div className="mt-4 pt-3 border-t border-white/10">
                <span className="text-xs text-[#FB923C] block mb-2">Escalation reasons</span>
                <div className="flex flex-wrap gap-2">
                  {escalationReasons.map((reason, i) => (
                    <span key={i} className="text-xs font-mono bg-[#FB923C]/10 border border-[#FB923C]/30 text-[#FB923C] px-2 py-1 rounded-full">
                      {reason}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Left Column: Issue & OCR */}
          <div className="space-y-6">
            <div>
              <span className="text-xs text-[#2DD4BF] block mb-2">Original message</span>
              <p className="text-sm text-[#ECECEC] leading-relaxed font-sans whitespace-pre-wrap">"{textParts[0].trim()}"</p>
            </div>

            {textParts.length > 1 && (
              <div className="border-l border-[#2DD4BF] pl-4 py-1">
                <span className="text-xs text-[#2DD4BF] block mb-2 flex items-center">
                  <ImageIcon className="w-3 h-3 mr-1.5" /> Text extracted from image
                </span>
                <pre className="text-xs text-[#8A8F98] whitespace-pre-wrap font-mono bg-white/[0.03] rounded-xl p-3 border border-white/10">
                  {textParts[1].trim()}
                </pre>
              </div>
            )}

            {/* Signature Element: Telemetry Track */}
            {classification && (
              <div className="mt-6 pt-4 border-t border-white/10">
                <span className="text-xs text-[#8A8F98] block mb-2">Pipeline telemetry</span>
                <div className="flex flex-wrap gap-2">
                  <span className="text-xs font-mono bg-white/[0.03] border border-white/10 px-2 py-1 rounded-full text-[#ECECEC]">Category: {classification.category || 'unknown'}</span>
                  <span className="text-xs font-mono bg-white/[0.03] border border-white/10 px-2 py-1 rounded-full" style={{ color: classification.priority?.toLowerCase() === 'high' ? '#FB923C' : '#8A8F98' }}>Priority: {classification.priority}</span>
                  {classification.sentiment && (
                    <span className="text-xs font-mono bg-white/[0.03] border border-white/10 px-2 py-1 rounded-full" style={{ color: classification.sentiment.toLowerCase() === 'negative' ? '#FB7185' : '#8A8F98' }}>Sentiment: {classification.sentiment}</span>
                  )}
                  {classification.confidence != null && (
                    <span className="text-xs font-mono bg-white/[0.03] border border-white/10 px-2 py-1 rounded-full text-[#2DD4BF]">Confidence: {(classification.confidence * 100).toFixed(0)}%</span>
                  )}
                  {classification.source && (
                    <span className="text-xs font-mono bg-white/[0.03] border border-white/10 px-2 py-1 rounded-full text-[#8A8F98]">Source: {classification.source}</span>
                  )}
                  {draft?.rag_top_score != null && (
                    <span className="text-xs font-mono bg-white/[0.03] border border-white/10 px-2 py-1 rounded-full text-[#8A8F98]">RAG score: {draft.rag_top_score.toFixed(3)}</span>
                  )}
                  {draft?.low_relevance && (
                    <span className="text-xs font-mono bg-[#FB7185]/10 border border-[#FB7185]/30 px-2 py-1 rounded-full text-[#FB7185]">Low relevance</span>
                  )}
                  {retrievedSources.length > 0 && (
                    <span className="text-xs font-mono bg-white/[0.03] border border-white/10 px-2 py-1 rounded-full text-[#8A8F98]">Sources: {retrievedSources.length}</span>
                  )}
                </div>
              </div>
            )}

            {fullData?.raw_graph_payload && (
              <div className="mt-4 rounded-xl border border-white/10 bg-white/[0.03] p-3">
                <span className="text-xs text-[#8A8F98] block mb-2">Raw pipeline payload</span>
                <pre className="text-[10px] text-[#8A8F98] overflow-x-auto font-mono max-h-32">
                  {JSON.stringify(fullData.raw_graph_payload, null, 2)}
                </pre>
              </div>
            )}

            {isLoading && (
              <div className="mt-4 flex items-center text-xs text-[#8A8F98]">
                <Loader2 className="w-3 h-3 animate-spin mr-2 text-[#2DD4BF]" /> Loading full details…
              </div>
            )}
          </div>

          {/* Right Column: AI Processing / Resolution */}
          <div className="space-y-6 flex flex-col h-full">
            <div className="flex-1">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs text-[#34D399]">Resolution</span>
                {draft?.rag_top_score != null && (
                  <span className="text-xs text-[#8A8F98]">RAG score: {draft.rag_top_score.toFixed(3)}</span>
                )}
              </div>

              <div className="rounded-2xl bg-white/[0.03] border border-white/10 p-4 min-h-[150px] font-sans text-sm text-[#ECECEC]">
                 {resolution?.final_response
                    ? parseAdminResponse(resolution.final_response)
                    : (draft?.draft_text
                        ? parseAdminResponse(draft.draft_text)
                        : (isEscalated
                            ? 'Awaiting human review…'
                            : <div className="flex justify-center items-center py-8"><WavePhysicsLoader theme="dark" /></div>
                          )
                      )
                 }
              </div>
            </div>

            {/* Human Review Override Actions */}
            {(role === 'human' || (role === 'all' && isEscalated)) && !isReplying && (
              <button
                onClick={() => setIsReplying(true)}
                className="w-full bg-transparent border border-[#2DD4BF] text-[#2DD4BF] hover:bg-[#2DD4BF] hover:text-[#08090D] transition-colors rounded-2xl py-3 text-sm font-medium">
                Claim this ticket
              </button>
            )}

            {(role === 'human' || (role === 'all' && isEscalated)) && isReplying && (
              <div className="space-y-3">
                <textarea
                  className="w-full bg-white/[0.03] border border-[#FB923C]/50 rounded-2xl text-[#ECECEC] text-sm p-3 font-sans focus:outline-none focus:border-[#FB923C] resize-none"
                  rows={4}
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  disabled={isSubmitting}
                />
                <div className="flex gap-2">
                  <button onClick={() => setIsReplying(false)} className="flex-1 border border-white/10 bg-transparent text-[#8A8F98] hover:text-[#ECECEC] hover:bg-white/[0.06] transition-colors rounded-2xl py-3 text-sm font-medium">Cancel</button>
                  <button onClick={handleResolve} disabled={!replyText.trim() || isSubmitting} className="flex-1 bg-[#FB923C] text-[#08090D] hover:bg-[#fdba74] transition-colors rounded-2xl py-3 text-sm font-semibold disabled:opacity-50">
                    {isSubmitting ? 'Sending…' : 'Send resolution'}
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

/** One label/value pair in the expanded ticket metadata grid. */
function MetaItem({ label, value, hint, color, mono, title }: {
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

function Chip({ label, color, icon }: { label: string; color: string; icon?: React.ReactNode }) {
  const colors: Record<string, string> = {
    indigo: 'bg-[#E8A33D]/15 text-[#E8A33D] border-[#E8A33D]/25',
    sky: 'bg-[#2DD4BF]/15 text-[#2DD4BF] border-[#2DD4BF]/25',
    amber: 'bg-[#FB923C]/15 text-[#FB923C] border-[#FB923C]/25',
    red: 'bg-[#FB7185]/15 text-[#FB7185] border-[#FB7185]/25',
    emerald: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/25',
    slate: 'bg-white/[0.06] text-[#8A8F98] border-white/10',
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
          ? 'bg-[#E8A33D]/20 text-[#E8A33D] border border-[#E8A33D]/40 shadow-[0_0_15px_rgba(232,163,61,0.2)]'
          : 'text-[#8A8F98] hover:text-[#ECECEC] border border-transparent hover:border-white/10 hover:bg-white/[0.04]'
      }`}
    >
      <span className={warn && !active ? 'text-[#FB923C]' : ''}>{icon}</span>
      <span>{label}</span>
    </button>
  );
}

function StatBadge({ label, value, color }: { label: string; value: number; color: string }) {
  const colors: Record<string, string> = {
    indigo: 'from-[#E8A33D]/10 to-[#E8A33D]/5 border-[#E8A33D]/20 text-[#E8A33D]',
    amber: 'from-[#FB923C]/10 to-[#FB923C]/5 border-[#FB923C]/20 text-[#FB923C]',
    emerald: 'from-emerald-500/10 to-emerald-500/5 border-emerald-500/20 text-emerald-300',
    sky: 'from-[#2DD4BF]/10 to-[#2DD4BF]/5 border-[#2DD4BF]/20 text-[#2DD4BF]',
  };
  return (
    <div className={`bg-gradient-to-br ${colors[color]} border rounded-2xl p-4`}>
      <p className="text-3xl font-bold text-[#ECECEC]">{value}</p>
      <p className={`text-xs font-medium mt-1`}>{label}</p>
    </div>
  );
}

function SystemCard({ icon, label, status, uptime, color }: {
  icon: React.ReactNode; label: string; status: string; uptime: string; color: string;
}) {
  const colorMap: Record<string, string> = {
    emerald: 'text-emerald-400 bg-emerald-500/15 border-emerald-500/25',
    amber: 'text-[#FB923C] bg-[#FB923C]/15 border-[#FB923C]/25',
    sky: 'text-[#2DD4BF] bg-[#2DD4BF]/15 border-[#2DD4BF]/25',
  };
  return (
    <div className="rounded-2xl backdrop-blur-md bg-white/[0.03] border border-white/[0.08] p-5">
      <div className="flex justify-between items-start mb-3">
        <div className={`p-2.5 rounded-xl border ${colorMap[color]}`}>{icon}</div>
        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${colorMap[color]}`}>{status}</span>
      </div>
      <h3 className="font-semibold text-[#ECECEC] text-sm">{label}</h3>
      <p className="text-xs text-[#8A8F98] mt-0.5">Uptime: {uptime}</p>
    </div>
  );
}
