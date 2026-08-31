import { NextResponse } from 'next/server';
import { createClient as createRedisClient } from 'redis';
import { createClient as createSupabaseClient } from '@supabase/supabase-js';

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || '';
const REDIS_URL = process.env.REDIS_URL || 'redis://localhost:6379';
const CACHE_KEY = 'tickets:list:metadata';
const CACHE_TTL_SECONDS = 60; // 1 minute cache

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

// Helper to get connected Redis client gracefully (avoids crashing if Redis is down)
async function getRedisClient(): Promise<any> {
  // Bypassed Redis for local Windows testing environment
  return null;
}

export async function GET() {
  const supabase = getSupabase();
  if (!supabase) return MISSING_KEY_RESPONSE();

  const redis = await getRedisClient();

  if (redis) {
    try {
      // 1. Check Server Cache (Redis)
      const cached = await redis.get(CACHE_KEY);
      if (cached) {
        await redis.quit();
        return NextResponse.json({ data: JSON.parse(cached), source: 'redis-cache' });
      }
    } catch (e) {
      console.error("Redis get error", e);
    }
  }

  // 2. Cache Miss -> Query Origin (Database)
  const { data: ticketData, error: ticketError } = await supabase
    .from('tickets')
    .select(`
      id, raw_text, subject, customer_email, status, created_at, raw_graph_payload,
      ticket_drafts ( domain ),
      ticket_classifications ( category, priority, sentiment, confidence ),
      resolutions ( id, escalated, resolved_at, ticket_id )
    `)
    .order('created_at', { ascending: false });

  if (ticketError) {
    if (redis) await redis.quit();
    return NextResponse.json({ error: ticketError.message }, { status: 500 });
  }

  // 3. Update Server Cache
  if (redis) {
    try {
      await redis.set(CACHE_KEY, JSON.stringify(ticketData || []), {
        EX: CACHE_TTL_SECONDS
      });
    } catch (e) {
      console.error("Redis set error", e);
    } finally {
      await redis.quit();
    }
  }

  return NextResponse.json({ data: ticketData || [], source: 'database' });
}

export async function DELETE(request: Request) {
  const supabase = getSupabase();
  if (!supabase) return MISSING_KEY_RESPONSE();

  const { searchParams } = new URL(request.url);
  const id = searchParams.get('id');

  if (id) {
    // First, manually cascade deletes for all related tables to avoid Foreign Key constraint violations
    await supabase.from('ticket_drafts').delete().eq('ticket_id', id);
    await supabase.from('ticket_classifications').delete().eq('ticket_id', id);
    await supabase.from('resolutions').delete().eq('ticket_id', id);
    await supabase.from('human_reviews').delete().eq('ticket_id', id);
    
    // Then, delete the parent ticket directly from database
    const { error } = await supabase.from('tickets').delete().eq('id', id);
    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }
  }

  // Invalidate cache
  const redis = await getRedisClient();
  if (redis) {
    try {
      await redis.del(CACHE_KEY);
      await redis.quit();
    } catch (e) {
      console.error("Redis del error", e);
    }
  }
  
  return NextResponse.json({ message: 'Deleted and cache invalidated' });
}

export async function PUT(request: Request) {
  const supabase = getSupabase();
  if (!supabase) return MISSING_KEY_RESPONSE();

  const body = await request.json();
  const { id, final_response } = body;

  if (!id || !final_response) {
    return NextResponse.json({ error: 'Missing id or final_response' }, { status: 400 });
  }

  // First update status
  const { error: updateError } = await supabase.from('tickets').update({ status: 'resolved' }).eq('id', id);
  if (updateError) {
    return NextResponse.json({ error: updateError.message }, { status: 500 });
  }

  // Then insert resolution
  const { error: insertError } = await supabase.from('resolutions').insert({
    ticket_id: id,
    final_response,
    escalated: false,
    resolved_at: new Date().toISOString()
  });
  if (insertError) {
    return NextResponse.json({ error: insertError.message }, { status: 500 });
  }

  // Invalidate cache
  const redis = await getRedisClient();
  if (redis) {
    try {
      await redis.del(CACHE_KEY);
      await redis.quit();
    } catch (e) {
      console.error("Redis del error", e);
    }
  }
  
  return NextResponse.json({ success: true });
}
