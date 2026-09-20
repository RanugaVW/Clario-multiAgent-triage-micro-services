'use client';

import type { ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { Ticket, ShieldAlert } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { supabase } from '../../lib/supabase';
import { AppShell } from '../../components/AppShell';

/** The agent workspace's frame: the shared shell with the agent navigation. */
export function AgentShell({ children }: { children: ReactNode }) {
  const { user, role } = useAuth();
  const router = useRouter();
  return (
    <AppShell
      brand={{ icon: <Ticket className="h-5 w-5" />, title: 'Agent workspace', subtitle: 'Clario Platform' }}
      nav={[{ key: 'queue', label: 'Escalation queue', icon: <Ticket className="w-4 h-4" />, href: '/agent', active: true }]}
      links={role === 'admin' ? [{ key: 'admin', label: 'Admin panel', icon: <ShieldAlert className="w-4 h-4" />, href: '/admin' }] : []}
      email={user?.email}
      onSignOut={async () => {
        await supabase.auth.signOut();
        router.push('/login');
      }}
    >
      {children}
    </AppShell>
  );
}
