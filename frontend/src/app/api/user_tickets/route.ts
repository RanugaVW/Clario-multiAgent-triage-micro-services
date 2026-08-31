import { NextResponse } from 'next/server';
import { createClient as createSupabaseClient } from '@supabase/supabase-js';

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || '';

// Building the client with an empty key throws while the module loads, which makes
// Next.js answer with an HTML error page instead of JSON. Build it on first use so a
// missing key comes back as a JSON 500 the caller can actually read.
function createServiceClient() {
  return createSupabaseClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);
}

let supabaseClient: ReturnType<typeof createServiceClient> | null = null;

function getSupabase() {
  if (!SUPABASE_SERVICE_KEY) return null;
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
  const supabase = getSupabase();
  if (!supabase) return MISSING_KEY_RESPONSE();

  const { searchParams } = new URL(request.url);
  const userId = searchParams.get('userId');

  if (!userId) {
    return NextResponse.json({ error: 'Missing userId' }, { status: 400 });
  }

  const { data, error } = await supabase
    .from('tickets')
    .select('*, resolutions(*)')
    .eq('user_id', userId)
    .order('created_at', { ascending: false });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ data: data || [] });
}
