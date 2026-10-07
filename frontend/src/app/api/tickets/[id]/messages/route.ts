import { NextResponse } from 'next/server';
import { requireUser, isStaff, type AuthedUser } from '../../../../../lib/apiAuth';
import { createServiceClient, type ServiceClient } from '../../../../../lib/serviceClient';
import { MAX_MESSAGE_LENGTH, isUuid, statusAfterReply } from '../../../../../lib/ticketThread';

// Follow-up conversation on one ticket, between its customer and staff.
// Deliberately never forwarded to the orchestrator/ML sidecar: only the
// original tickets.raw_text goes through the pipeline. Uses the service-role
// client (public.ticket_messages has no write policy at all), so every
// handler verifies the caller and their access to the ticket first.

type RouteContext = { params: Promise<{ id: string }> };

const MESSAGE_COLUMNS = 'id, ticket_id, author_id, author_role, body, client_msg_id, created_at';

const MISSING_KEY_RESPONSE = () =>
  NextResponse.json({ error: 'SUPABASE_SERVICE_ROLE_KEY is not set on the server' }, { status: 500 });

type Access =
  | { error: NextResponse }
  | { error?: undefined; caller: AuthedUser; supabase: ServiceClient; ticket: { id: string; status: string | null } };

async function authorize(request: Request, ticketId: string): Promise<Access> {
  const caller = await requireUser(request);
  if (!caller) return { error: NextResponse.json({ error: 'Authentication required' }, { status: 401 }) };
  if (!isUuid(ticketId)) return { error: NextResponse.json({ error: 'Ticket not found' }, { status: 404 }) };

  const supabase = createServiceClient();
  if (!supabase) return { error: MISSING_KEY_RESPONSE() };

  const { data: ticket, error } = await supabase
    .from('tickets')
    .select('id, user_id, status')
    .eq('id', ticketId)
    .maybeSingle();
  if (error) return { error: NextResponse.json({ error: error.message }, { status: 500 }) };

  // Same answer for "no such ticket" and "someone else's ticket", so the
  // endpoint can't be used to probe which ticket ids exist.
  if (!ticket || (ticket.user_id !== caller.id && !isStaff(caller))) {
    return { error: NextResponse.json({ error: 'Ticket not found' }, { status: 404 }) };
  }
  return { caller, supabase, ticket: { id: ticket.id, status: ticket.status } };
}

export async function GET(request: Request, { params }: RouteContext) {
  const { id } = await params;
  const access = await authorize(request, id);
  if (access.error) return access.error;

  const { data, error } = await access.supabase
    .from('ticket_messages')
    .select(MESSAGE_COLUMNS)
    .eq('ticket_id', id)
    .order('created_at', { ascending: true })
    .order('id', { ascending: true });
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  return NextResponse.json({ data: data ?? [], ticketStatus: access.ticket.status });
}

export async function POST(request: Request, { params }: RouteContext) {
  const { id } = await params;
  const access = await authorize(request, id);
  if (access.error) return access.error;
  const { caller, supabase, ticket } = access;

  let payload: { body?: unknown; clientMsgId?: unknown; markResolved?: unknown };
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ error: 'Request body must be valid JSON' }, { status: 400 });
  }

  const body = typeof payload.body === 'string' ? payload.body.trim() : '';
  if (!body) return NextResponse.json({ error: 'Message cannot be empty' }, { status: 400 });
  if (body.length > MAX_MESSAGE_LENGTH) {
    return NextResponse.json({ error: `Message must be at most ${MAX_MESSAGE_LENGTH} characters` }, { status: 400 });
  }
  if (!isUuid(payload.clientMsgId)) {
    return NextResponse.json({ error: 'clientMsgId must be a UUID' }, { status: 400 });
  }
  const clientMsgId = payload.clientMsgId;
  // Closing a ticket is a staff action; a customer's flag is ignored, not trusted.
  const markResolved = isStaff(caller) && payload.markResolved === true;

  // Author comes from the verified token, never from the request. ignoreDuplicates
  // makes a retried send (same clientMsgId) a no-op instead of a second bubble.
  const { error: insertError } = await supabase.from('ticket_messages').upsert(
    { ticket_id: id, author_id: caller.id, author_role: caller.role, body, client_msg_id: clientMsgId },
    { onConflict: 'ticket_id,client_msg_id', ignoreDuplicates: true }
  );
  if (insertError) return NextResponse.json({ error: insertError.message }, { status: 500 });

  const { data: message, error: readError } = await supabase
    .from('ticket_messages')
    .select(MESSAGE_COLUMNS)
    .eq('ticket_id', id)
    .eq('client_msg_id', clientMsgId)
    .single();
  if (readError || !message) {
    return NextResponse.json({ error: readError?.message ?? 'Failed to read back message' }, { status: 500 });
  }

  // The message is saved before the status moves. If this update fails the
  // client sees an error and retries with the same clientMsgId: the insert is
  // then a no-op and the status update simply runs again.
  let ticketStatus = ticket.status;
  const nextStatus = statusAfterReply(ticket.status, caller.role, markResolved);
  if (nextStatus && nextStatus !== ticket.status) {
    const { error: statusError } = await supabase
      .from('tickets')
      .update({ status: nextStatus, updated_at: new Date().toISOString() })
      .eq('id', id);
    if (statusError) return NextResponse.json({ error: statusError.message }, { status: 500 });
    ticketStatus = nextStatus;
  }

  return NextResponse.json({ data: message, ticketStatus }, { status: 201 });
}
