import { NextResponse } from 'next/server';
import { createClient as createSupabaseClient } from '@supabase/supabase-js';
import { requireUser } from '../../../lib/apiAuth';

// Read these lazily (inside functions) rather than as module-level constants. Static
// imports execute before a test file's own top-level statements, so a module-level
// const here would capture env vars before a test's `process.env.X = ...` assignments
// ever ran. Building the client with an empty key also throws while the module loads,
// which makes Next.js answer with an HTML error page instead of JSON - building it on
// first use means a missing key comes back as a JSON 500 the caller can actually read.
function createServiceClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY || '';
  return createSupabaseClient(url, key);
}

let supabaseClient: ReturnType<typeof createServiceClient> | null = null;

function getSupabase() {
  if (!process.env.SUPABASE_SERVICE_ROLE_KEY) return null;
  if (!supabaseClient) {
    supabaseClient = createServiceClient();
  }
  return supabaseClient;
}

const MISSING_KEY_RESPONSE = () =>
  NextResponse.json(
    { error: 'SUPABASE_SERVICE_ROLE_KEY is not set on the server' },
    { status: 500 }
  );

export async function POST(request: Request) {
  const caller = await requireUser(request);
  if (!caller) return NextResponse.json({ error: 'Authentication required' }, { status: 401 });

  const supabase = getSupabase();
  if (!supabase) return MISSING_KEY_RESPONSE();

  const body = await request.json();
  const { ticketId, score, comment } = body as {
    ticketId?: string; score?: number; comment?: string;
  };

  if (!ticketId) {
    return NextResponse.json({ error: 'Missing ticketId' }, { status: 400 });
  }
  if (typeof score !== 'number' || !Number.isInteger(score) || score < 1 || score > 5) {
    return NextResponse.json({ error: 'score must be an integer between 1 and 5' }, { status: 400 });
  }

  // Service role bypasses RLS, so ownership must be checked here - against
  // the VERIFIED caller's id, never a client-supplied userId (a customer
  // can only ever rate their own ticket, no staff-on-behalf-of exception).
  const { data: ticket, error: ticketError } = await supabase
    .from('tickets')
    .select('id')
    .eq('id', ticketId)
    .eq('user_id', caller.id)
    .single();

  if (ticketError || !ticket) {
    return NextResponse.json({ error: 'Ticket not found for this user' }, { status: 403 });
  }

  const { data, error } = await supabase
    .from('customer_feedback')
    .upsert(
      { ticket_id: ticketId, score, comment: comment || null, updated_at: new Date().toISOString() },
      { onConflict: 'ticket_id' }
    );

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ data });
}
