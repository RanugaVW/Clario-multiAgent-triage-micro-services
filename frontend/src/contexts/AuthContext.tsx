'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { supabase } from '../lib/supabase';
import { User } from '@supabase/supabase-js';

type AuthContextType = {
  user: User | null;
  loading: boolean;      // true = auth session still resolving
  roleLoading: boolean;  // true = DB role query still in-flight
  role: 'user' | 'agent' | 'admin' | null;
};

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  roleLoading: true,
  role: null,
});

const fetchUserRole = async (userId: string): Promise<'user' | 'agent' | 'admin'> => {
  // Use RPC to bypass RLS infinite recursion on the users table.
  // get_my_role() is SECURITY DEFINER (runs as postgres superuser) so it reads
  // the role without triggering any SELECT policy on public.users.
  const { data, error } = await supabase.rpc('get_my_role');

  if (error) {
    console.error('Role fetch error:', error.message);
  }

  if (data && ['user', 'agent', 'admin'].includes(data)) {
    return data as 'user' | 'agent' | 'admin';
  }
  return 'user';
};

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [role, setRole] = useState<'user' | 'agent' | 'admin' | null>(null);
  const [loading, setLoading] = useState(true);
  const [roleLoading, setRoleLoading] = useState(true);

  useEffect(() => {
    // Resolve existing session on mount
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      const currentUser = session?.user ?? null;
      setUser(currentUser);
      setLoading(false);

      if (currentUser) {
        setRoleLoading(true);
        const r = await fetchUserRole(currentUser.id);
        setRole(r);
        setRoleLoading(false);
      } else {
        setRole(null);
        setRoleLoading(false);
      }
    });

    // Listen for future auth state changes (login / logout)
    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (_event, session) => {
      const currentUser = session?.user ?? null;
      setUser(currentUser);
      setLoading(false);

      if (currentUser) {
        setRoleLoading(true);
        const r = await fetchUserRole(currentUser.id);
        setRole(r);
        setRoleLoading(false);
      } else {
        setRole(null);
        setRoleLoading(false);
      }
    });

    return () => subscription.unsubscribe();
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, roleLoading, role }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
