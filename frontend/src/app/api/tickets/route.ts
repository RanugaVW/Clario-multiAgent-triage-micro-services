import { NextResponse } from 'next/server';
import { createClient as createSupabaseClient } from '@supabase/supabase-js';
import { requireUser, isStaff, type AuthedUser } from '../../../lib/apiAuth';

const CACHE_KEY = 'tickets:list:metadata';
const CACHE_TTL_SECONDS = 60; // 1 minute cache

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

const CUSTOMER_MARKER = '[CUSTOMER RESPONSE]';
const normalizeWs = (text: string) => text.replace(/\s+/g, ' ').trim();

function customerSection(draft: string): string {
  const idx = draft.lastIndexOf(CUSTOMER_MARKER);
  return idx === -1 ? draft : draft.slice(idx + CUSTOMER_MARKER.length);
}

// An agent who sends the AI draft (or just its customer-facing section) as-is
// approved it; anything else is an edit worth learning from.
function isUnchangedDraft(finalResponse: string, originalDraft: string | null): boolean {
  if (!originalDraft) return false;
  const final = normalizeWs(finalResponse);
  return final === normalizeWs(originalDraft) || final === normalizeWs(customerSection(originalDraft));
}

// The subset of the real Redis client's surface this route actually calls -
// kept minimal rather than pulling in the full `redis` package's generic
// client type, since getRedisClient() below never actually constructs one.
interface CacheClient {
  get(key: string): Promise<string | null>;
  set(key: string, value: string, options?: { EX?: number }): Promise<unknown>;
  del(key: string): Promise<unknown>;
  quit(): Promise<unknown>;
}

// Helper to get connected Redis client gracefully (avoids crashing if Redis is down)
async function getRedisClient(): Promise<CacheClient | null> {
  // Bypassed Redis for local Windows testing environment
  return null;
}

type StaffCheck = { error: NextResponse; user?: undefined } | { error?: undefined; user: AuthedUser };

async function authorizeStaff(request: Request): Promise<StaffCheck> {
  const user = await requireUser(request);
  if (!user) return { error: NextResponse.json({ error: 'Authentication required' }, { status: 401 }) };
  if (!isStaff(user)) return { error: NextResponse.json({ error: 'Staff access required' }, { status: 403 }) };
  return { user };
}

async function requireStaff(request: Request): Promise<NextResponse | null> {
  return (await authorizeStaff(request)).error ?? null;
}

export async function GET(request: Request) {
  const authError = await requireStaff(request);
  if (authError) return authError;

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
      id, raw_text, subject, customer_email, status, created_at, updated_at, raw_graph_payload,
      ticket_drafts ( domain, draft_text, rag_top_score, low_relevance, reflection_attempt ),
      ticket_classifications ( category, priority, sentiment, confidence, source ),
      resolutions ( id, escalated, resolved_at, ticket_id, resolved_by, total_reflection_count, total_llm_calls, total_latency_ms )
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
  const authError = await requireStaff(request);
  if (authError) return authError;

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
  const staff = await authorizeStaff(request);
  if (staff.error) return staff.error;

  const supabase = getSupabase();
  if (!supabase) return MISSING_KEY_RESPONSE();

  let body: { id?: unknown; final_response?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Request body must be valid JSON' }, { status: 400 });
  }
  const id = typeof body.id === 'string' ? body.id : '';
  const finalResponse = typeof body.final_response === 'string' ? body.final_response.trim() : '';

  if (!id || !finalResponse) {
    return NextResponse.json({ error: 'Missing id or final_response' }, { status: 400 });
  }

  // FR-035/FR-036: a resolution must be attributable and must not silently
  // overwrite an earlier answer, so look at the ticket before writing anything.
  const { data: ticket, error: lookupError } = await supabase
    .from('tickets')
    .select('id, status, resolutions ( id, escalated ), human_reviews ( id, original_draft, decision )')
    .eq('id', id)
    .maybeSingle();
  if (lookupError) {
    return NextResponse.json({ error: lookupError.message }, { status: 500 });
  }
  if (!ticket) {
    return NextResponse.json({ error: 'Ticket not found' }, { status: 404 });
  }
  const alreadyAnswered =
    ticket.status === 'resolved' ||
    (ticket.resolutions ?? []).some((r: { escalated: boolean }) => r.escalated === false);
  if (alreadyAnswered) {
    return NextResponse.json({ error: 'Ticket is already resolved' }, { status: 409 });
  }

  // Insert the resolution first, then flip the status: if the second write
  // fails we can take the resolution back, whereas the old order could leave a
  // "resolved" ticket with no answer attached to it.
  const { data: inserted, error: insertError } = await supabase
    .from('resolutions')
    .insert({
      ticket_id: id,
      final_response: finalResponse,
      escalated: false,
      resolved_by: staff.user.id,
      resolved_at: new Date().toISOString(),
    })
    .select('id')
    .single();
  if (insertError || !inserted) {
    return NextResponse.json({ error: insertError?.message ?? 'Failed to save resolution' }, { status: 500 });
  }

  const { error: updateError } = await supabase.from('tickets').update({ status: 'resolved' }).eq('id', id);
  if (updateError) {
    await supabase.from('resolutions').delete().eq('id', inserted.id);
    return NextResponse.json({ error: updateError.message }, { status: 500 });
  }

  // Learning signal, best-effort: record what the human actually sent so the
  // agent-edit job can learn from it. Never fails or delays the resolution.
  const pendingReview = (ticket.human_reviews ?? []).find(
    (r: { decision: string | null }) => r.decision === 'pending'
  );
  if (pendingReview) {
    try {
      const { error: reviewError } = await supabase
        .from('human_reviews')
        .update({
          final_draft: finalResponse,
          reviewer_id: staff.user.id,
          reviewed_at: new Date().toISOString(),
          decision: isUnchangedDraft(finalResponse, pendingReview.original_draft) ? 'approved_unchanged' : 'edited',
        })
        .eq('id', pendingReview.id);
      if (reviewError) console.error('human_reviews update failed', reviewError.message);
    } catch (e) {
      console.error('human_reviews update threw', e);
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

  return NextResponse.json({ success: true });
}
