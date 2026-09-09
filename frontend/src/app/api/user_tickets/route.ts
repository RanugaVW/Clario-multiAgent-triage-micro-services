import { NextResponse } from 'next/server';
import { createClient as createSupabaseClient } from '@supabase/supabase-js';
<<<<<<< HEAD
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
=======

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || '';

// Building the client with an empty key throws while the module loads, which makes
// Next.js answer with an HTML error page instead of JSON. Build it on first use so a
// missing key comes back as a JSON 500 the caller can actually read.
function createServiceClient() {
  return createSupabaseClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);
>>>>>>> origin/add/voice-to-text-service
}

let supabaseClient: ReturnType<typeof createServiceClient> | null = null;

function getSupabase() {
<<<<<<< HEAD
  if (!process.env.SUPABASE_SERVICE_ROLE_KEY) return null;
=======
  if (!SUPABASE_SERVICE_KEY) return null;
>>>>>>> origin/add/voice-to-text-service
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
<<<<<<< HEAD
  const caller = await requireUser(request);
  if (!caller) return NextResponse.json({ error: 'Authentication required' }, { status: 401 });

=======
>>>>>>> origin/add/voice-to-text-service
  const supabase = getSupabase();
  if (!supabase) return MISSING_KEY_RESPONSE();

  const { searchParams } = new URL(request.url);
  const userId = searchParams.get('userId');

  if (!userId) {
    return NextResponse.json({ error: 'Missing userId' }, { status: 400 });
  }

<<<<<<< HEAD
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
=======
  const { data, error } = await supabase
    .from('tickets')
    .select('*, resolutions(*), ticket_classifications(category, priority, sentiment, confidence)')
>>>>>>> origin/add/voice-to-text-service
    .eq('user_id', userId)
    .order('created_at', { ascending: false });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ data: data || [] });
}
