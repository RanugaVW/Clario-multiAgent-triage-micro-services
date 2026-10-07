// Shared by the /api/tickets/[id]/messages route (server) and the ticket thread
// UI (browser), so it must stay free of any client-only or server-only imports.

export type MessageAuthorRole = 'user' | 'agent' | 'admin';

/** A row of public.ticket_messages, exactly as the API returns it. */
export interface TicketMessage {
  id: string;
  ticket_id: string;
  author_id: string | null;
  author_role: MessageAuthorRole;
  body: string;
  client_msg_id: string;
  created_at: string;
}

/**
 * A message as the thread renders it. `sending`/`failed` rows exist only in the
 * browser (optimistic sends) and carry what a retry needs to resend them.
 */
export type ThreadMessage = TicketMessage & {
  state: 'sent' | 'sending' | 'failed';
  markResolved?: boolean;
};

export const MAX_MESSAGE_LENGTH = 5000;

/** tickets.status for a ticket a customer has replied to after it was resolved. */
export const REOPENED_STATUS = 'reopened';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isUuid(value: unknown): value is string {
  return typeof value === 'string' && UUID_RE.test(value);
}

export function isStaffRole(role: string | null | undefined): boolean {
  return role === 'agent' || role === 'admin';
}

/**
 * Folds confirmed rows (from the API or a Realtime insert) into the thread.
 *
 * client_msg_id is the identity, not id: an optimistic bubble has no server id
 * yet, and the same confirmed row typically arrives twice - once as the POST
 * response and once as its own Realtime echo. A confirmed row always replaces
 * a pending/failed one with the same client_msg_id.
 */
export function mergeMessages(current: ThreadMessage[], incoming: TicketMessage[]): ThreadMessage[] {
  const byClientId = new Map(current.map((m) => [m.client_msg_id, m]));
  for (const row of incoming) {
    byClientId.set(row.client_msg_id, { ...row, state: 'sent' });
  }
  return [...byClientId.values()].sort(
    (a, b) => a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id)
  );
}

/**
 * Decides the ticket's status after a reply is saved. Returns the new
 * tickets.status, or null to leave it as it is.
 *
 * `currentStatus` is tickets.status before the reply ('received', 'processing',
 * 'escalated', 'resolved', 'reopened', ...). `markResolved` is true only when a
 * staff member pressed "Send & resolve" - the route already forces it to false
 * for customers.
 *
 * Remember the UI shows a ticket as resolved whenever it has a non-escalated
 * resolution row UNLESS its status is 'reopened', so 'reopened' is the only
 * status that can pull an already-answered ticket back into the review queue.
 */
export function statusAfterReply(
  currentStatus: string | null,
  authorRole: MessageAuthorRole,
  markResolved: boolean
): string | null {
  // TODO(human)
  return null;
}
