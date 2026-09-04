import { NextResponse } from 'next/server';
import { createClient as createSupabaseClient } from '@supabase/supabase-js';
import { requireUser, isStaff } from '../../../lib/apiAuth';

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

export async function GET(request: Request) {
  const caller = await requireUser(request);
  if (!caller) return NextResponse.json({ error: 'Authentication required' }, { status: 401 });

  const supabase = getSupabase();
  if (!supabase) return MISSING_KEY_RESPONSE();

  const { searchParams } = new URL(request.url);
  const userId = searchParams.get('userId');

  if (!userId) {
    return NextResponse.json({ error: 'Missing userId' }, { status: 400 });
  }

  // A customer may only ever fetch their own history; staff (who already
  // have their own admin-console path via /api/tickets) are allowed to
  // pass an arbitrary userId here too, matching the same staff-can-view-all
  // boundary the tickets RLS policy grants them everywhere else.
  if (userId !== caller.id && !isStaff(caller)) {
    return NextResponse.json({ error: 'Cannot view another user\'s tickets' }, { status: 403 });
  }

  const { data, error } = await supabase
    .from('tickets')
    .select('*, resolutions(*), ticket_classifications(category, priority, sentiment, confidence), customer_feedback(score)')
    .eq('user_id', userId)
    .order('created_at', { ascending: false });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ data: data || [] });
}
