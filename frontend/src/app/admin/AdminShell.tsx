'use client';

import type { ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, BarChart3, LayoutDashboard, Settings, Users } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { supabase } from '../../lib/supabase';
import { AppShell, type ShellNavItem } from '../../components/AppShell';

export type AdminSection = 'console' | 'reports' | 'users';

/**
 * The frame shared by every admin page. The console passes its in-page tabs as `consoleTabs`; the other pages get a
 * single "Console" link back. Reports and Users are always one click away.
 */
export function AdminShell({
  active,
  consoleTabs,
  children,
}: {
  active: AdminSection;
  consoleTabs?: ShellNavItem[];
  children: ReactNode;
}) {
  const { user } = useAuth();
  const router = useRouter();
  const consoleNav: ShellNavItem[] = consoleTabs ?? [
    { key: 'console', label: 'Console', icon: <LayoutDashboard className="w-4 h-4" />, href: '/admin' },
  ];
  return (
    <AppShell
      brand={{ icon: <Settings className="h-5 w-5" />, title: 'System administration', subtitle: 'Clario Platform' }}
      nav={[
        ...consoleNav,
        { key: 'reports', label: 'Reports', icon: <BarChart3 className="w-4 h-4" />, href: '/admin/reports', active: active === 'reports' },
        { key: 'users', label: 'Users', icon: <Users className="w-4 h-4" />, href: '/admin/users', active: active === 'users' },
      ]}
      links={[{ key: 'triage', label: 'Back to triage', icon: <ArrowLeft className="w-4 h-4" />, href: '/' }]}
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
