'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useRouter } from 'next/navigation';
import { Ticket, Clock, CheckCircle2, AlertTriangle, ArrowRight, LogOut, Loader2 } from 'lucide-react';
import { supabase } from '../../lib/supabase';

// Mock data for prototype
const MOCK_TICKETS = [
  { id: 'SUP-1002', status: 'escalated', priority: 'High', category: 'Billing', time: '10 mins ago' },
  { id: 'SUP-1005', status: 'escalated', priority: 'Urgent', category: 'Technical', time: '1 hr ago' },
  { id: 'SUP-1009', status: 'escalated', priority: 'Medium', category: 'Billing', time: '2 hrs ago' },
];

export default function AgentDashboard() {
  const { user, role, loading } = useAuth();
  const router = useRouter();
<<<<<<< HEAD
  const [tickets] = useState(MOCK_TICKETS);
=======
  const [tickets, setTickets] = useState(MOCK_TICKETS);
>>>>>>> origin/add/voice-to-text-service

  useEffect(() => {
    if (!loading && !user && !role) {
      // router.push('/login');
    }
  }, [user, role, loading, router]);

  const handleLogout = async () => {
    await supabase.auth.signOut();
    router.push('/login');
  };

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
<<<<<<< HEAD
      <Loader2 className="w-8 h-8 animate-spin text-[#E8A33D]" />
=======
      <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
>>>>>>> origin/add/voice-to-text-service
    </div>
  );

  return (
    <main className="min-h-screen py-8 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
      {/* Header */}
      <header className="flex justify-between items-center mb-10 animate-fade-in">
        <div className="flex items-center space-x-3">
<<<<<<< HEAD
          <div className="bg-[#E8A33D]/15 p-2 rounded-xl border border-[#E8A33D]/25">
            <Ticket className="text-[#E8A33D] w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[#ECECEC]">Agent dashboard</h1>
            <p className="text-sm text-[#8A8F98]">Escalated tickets queue</p>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          <span className="text-sm font-medium text-[#8A8F98]">
            Agent workspace
          </span>
          <button
            onClick={handleLogout}
            className="p-2 hover:bg-white/[0.06] rounded-full transition-colors text-[#8A8F98] hover:text-[#ECECEC]"
=======
          <div className="bg-indigo-500/20 p-2 rounded-xl border border-indigo-500/30">
            <Ticket className="text-indigo-400 w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Agent Dashboard</h1>
            <p className="text-sm text-slate-400">Escalated Tickets Queue</p>
          </div>
        </div>
        
        <div className="flex items-center space-x-4">
          <span className="text-sm font-medium text-slate-300">
            Agent Workspace
          </span>
          <button 
            onClick={handleLogout}
            className="p-2 hover:bg-slate-800 rounded-full transition-colors text-slate-400 hover:text-white"
>>>>>>> origin/add/voice-to-text-service
            title="Sign Out"
          >
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </header>

      {/* Stats row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10 animate-fade-in" style={{ animationDelay: '0.1s' }}>
<<<<<<< HEAD
        <StatCard icon={<AlertTriangle />} label="Needs review" value={tickets.length.toString()} color="text-[#FB923C]" />
        <StatCard icon={<Clock />} label="Avg resolution" value="2.4 hrs" color="text-[#2DD4BF]" />
        <StatCard icon={<CheckCircle2 />} label="Resolved today" value="14" color="text-emerald-400" />
      </div>

      {/* Ticket List */}
      <section className="glass-panel rounded-[28px] overflow-hidden animate-fade-in" style={{ animationDelay: '0.2s' }}>
        <div className="p-6 border-b border-white/10 flex justify-between items-center">
          <h2 className="text-lg font-semibold text-[#ECECEC]">Escalation queue</h2>
        </div>

        <div className="divide-y divide-white/10">
          {tickets.map((ticket) => (
            <div key={ticket.id} className="p-6 hover:bg-white/[0.04] transition-colors flex items-center justify-between group">
              <div className="flex items-start space-x-4">
                <div className={`p-2 rounded-lg ${ticket.priority === 'Urgent' ? 'bg-[#FB7185]/15 text-[#FB7185]' : ticket.priority === 'High' ? 'bg-[#FB923C]/15 text-[#FB923C]' : 'bg-[#E8A33D]/15 text-[#E8A33D]'}`}>
                  <AlertTriangle className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-[#ECECEC] flex items-center">
                    {ticket.id}
                    <span className="ml-3 px-2 py-0.5 rounded-full text-xs font-medium bg-white/[0.06] text-[#8A8F98]">
                      {ticket.category}
                    </span>
                  </h3>
                  <div className="flex items-center text-sm text-[#8A8F98] mt-1 space-x-4">
=======
        <StatCard icon={<AlertTriangle />} label="Needs Review" value={tickets.length.toString()} color="text-amber-400" />
        <StatCard icon={<Clock />} label="Avg Resolution" value="2.4 hrs" color="text-sky-400" />
        <StatCard icon={<CheckCircle2 />} label="Resolved Today" value="14" color="text-emerald-400" />
      </div>

      {/* Ticket List */}
      <section className="glass-panel rounded-3xl overflow-hidden animate-fade-in" style={{ animationDelay: '0.2s' }}>
        <div className="p-6 border-b border-slate-700/50 flex justify-between items-center bg-slate-900/50">
          <h2 className="text-lg font-semibold text-white">Escalation Queue</h2>
        </div>
        
        <div className="divide-y divide-slate-700/50">
          {tickets.map((ticket) => (
            <div key={ticket.id} className="p-6 hover:bg-slate-800/40 transition-colors flex items-center justify-between group">
              <div className="flex items-start space-x-4">
                <div className={`p-2 rounded-lg ${ticket.priority === 'Urgent' ? 'bg-red-500/20 text-red-400' : ticket.priority === 'High' ? 'bg-amber-500/20 text-amber-400' : 'bg-indigo-500/20 text-indigo-400'}`}>
                  <AlertTriangle className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-100 flex items-center">
                    {ticket.id}
                    <span className="ml-3 px-2 py-0.5 rounded-full text-xs font-medium bg-slate-800 text-slate-300">
                      {ticket.category}
                    </span>
                  </h3>
                  <div className="flex items-center text-sm text-slate-400 mt-1 space-x-4">
>>>>>>> origin/add/voice-to-text-service
                    <span className="flex items-center"><Clock className="w-3 h-3 mr-1" /> {ticket.time}</span>
                    <span className="flex items-center">Priority: {ticket.priority}</span>
                  </div>
                </div>
              </div>
<<<<<<< HEAD

              <button
                onClick={() => router.push(`/agent/${ticket.id}`)}
                className="bg-white/[0.06] hover:bg-[#E8A33D] text-[#ECECEC] hover:text-[#08090D] p-3 rounded-xl transition-all opacity-0 group-hover:opacity-100 transform translate-x-2 group-hover:translate-x-0 flex items-center"
=======
              
              <button 
                onClick={() => router.push(`/agent/${ticket.id}`)}
                className="bg-slate-800 hover:bg-indigo-600 text-white p-3 rounded-xl transition-all opacity-0 group-hover:opacity-100 transform translate-x-2 group-hover:translate-x-0 flex items-center"
>>>>>>> origin/add/voice-to-text-service
              >
                <span className="text-sm font-medium mr-2">Review</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          ))}
<<<<<<< HEAD

          {tickets.length === 0 && (
            <div className="p-12 text-center text-[#8A8F98]">
=======
          
          {tickets.length === 0 && (
            <div className="p-12 text-center text-slate-400">
>>>>>>> origin/add/voice-to-text-service
              <CheckCircle2 className="w-12 h-12 mx-auto mb-3 text-emerald-500/50" />
              <p>Queue is empty. Great job!</p>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}

function StatCard({ icon, label, value, color }: { icon: React.ReactNode, label: string, value: string, color: string }) {
  return (
<<<<<<< HEAD
    <div className="glass-panel rounded-[28px] p-6 flex items-center space-x-4">
      <div className={`p-3 rounded-2xl bg-white/[0.03] border border-white/10 ${color}`}>
        {icon}
      </div>
      <div>
        <p className="text-sm font-medium text-[#8A8F98]">{label}</p>
        <p className="text-2xl font-bold text-[#ECECEC]">{value}</p>
=======
    <div className="glass-panel p-6 rounded-3xl flex items-center space-x-4">
      <div className={`p-3 rounded-2xl bg-slate-800/50 border border-slate-700/50 ${color}`}>
        {icon}
      </div>
      <div>
        <p className="text-sm font-medium text-slate-400">{label}</p>
        <p className="text-2xl font-bold text-white">{value}</p>
>>>>>>> origin/add/voice-to-text-service
      </div>
    </div>
  );
}
