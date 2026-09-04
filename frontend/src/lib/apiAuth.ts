import { createClient as createSupabaseClient } from '@supabase/supabase-js';

export type AuthedUser = {
  id: string;
  email: string | null;
  role: 'user' | 'agent' | 'admin';
};

/**
 * Verifies the caller's Supabase access token and resolves their role.
 *
 * Every /api/* route in this app that talks to Supabase with the
 * SERVICE_ROLE key (which bypasses Row Level Security entirely) must call
 * this first - the service-role key has no concept of "who is asking" on
 * its own, so without this check any route using it is reachable by
 * anyone who can send it an HTTP request, authenticated or not.
 *
 * Returns null for a missing/invalid/expired token - callers should
 * respond 401. A valid token with the wrong role is the caller's job to
 * reject (403), not this function's - it only answers "who is this".
 */
export async function requireUser(request: Request): Promise<AuthedUser | null> {
  const authHeader = request.headers.get('authorization') ?? request.headers.get('Authorization');
  const token = authHeader?.match(/^Bearer\s+(.+)$/i)?.[1];
  if (!token) return null;

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';
  if (!url || !anonKey) return null;

  // Built with the anon key (never service-role) plus this specific
  // caller's token as the global auth header, so both auth.getUser() and
  // the get_my_role() RPC below run as this user, under RLS - the same
  // client shape AuthContext.tsx's own fetchUserRole() relies on.
  const supabase = createSupabaseClient(url, anonKey, {
    global: { headers: { Authorization: `Bearer ${token}` } },
  });

  const { data: userData, error: userError } = await supabase.auth.getUser(token);
  if (userError || !userData.user) return null;

  // get_my_role() is SECURITY DEFINER (runs as postgres superuser) so it
  // reads the role without triggering public.users' own SELECT policy -
  // identical rationale to AuthContext.tsx's fetchUserRole().
  const { data: roleData } = await supabase.rpc('get_my_role');
  const role: AuthedUser['role'] = ['user', 'agent', 'admin'].includes(roleData) ? roleData : 'user';

  return { id: userData.user.id, email: userData.user.email ?? null, role };
}

export function isStaff(user: AuthedUser | null): boolean {
  return user?.role === 'admin' || user?.role === 'agent';
}
