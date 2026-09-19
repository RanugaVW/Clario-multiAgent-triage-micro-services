import { createClient as createSupabaseClient } from '@supabase/supabase-js';

// Service-role client (bypasses RLS). Built lazily and null without the key - see the note in app/api/tickets/route.ts.
// Only ever use it AFTER requireUser() has verified who is asking.
export function createServiceClient() {
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!key) return null;
  return createSupabaseClient(process.env.NEXT_PUBLIC_SUPABASE_URL || '', key);
}

export type ServiceClient = NonNullable<ReturnType<typeof createServiceClient>>;
