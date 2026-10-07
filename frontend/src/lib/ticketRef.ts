// Display-only ticket references. tickets.id (UUID) stays the real identifier
// everywhere - URLs, API calls, "Copy ID" - this only changes what people read.

export const TICKET_REF_PREFIX = 'TKT';

type RefSource = { id: string; ticket_number?: number | null };

/**
 * "TKT-0042" from tickets.ticket_number (padded to 4 digits so early
 * references line up; larger numbers just grow).
 *
 * Falls back to the UUID's first block, uppercased, when the number is
 * missing - a cached list from before supabase_ticket_numbers.sql ran, or a
 * just-submitted ticket whose number hasn't been read back yet. The fallback
 * deliberately has no "TKT-" prefix so it can't be mistaken for a real one.
 */
export function formatTicketRef(ticket: RefSource): string {
  if (typeof ticket.ticket_number === 'number' && Number.isFinite(ticket.ticket_number)) {
    return `${TICKET_REF_PREFIX}-${String(ticket.ticket_number).padStart(4, '0')}`;
  }
  return ticket.id.split('-')[0].toUpperCase();
}

/**
 * Reads a ticket number out of whatever someone typed into a search box:
 * "TKT-0042", "tkt 42", "#42" or plain "42" all give 42.
 */
export function parseTicketRef(input: string): number | null {
  const match = input.trim().match(new RegExp(`^(?:${TICKET_REF_PREFIX}[\\s-]*|#)?0*(\\d+)$`, 'i'));
  return match ? Number(match[1]) : null;
}

/** True when a search query names this ticket by reference number or by (part of) its UUID. */
export function matchesTicketQuery(ticket: RefSource, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const number = parseTicketRef(q);
  if (number !== null) {
    if (ticket.ticket_number === number) return true;
    // Bare digits may still be a pasted UUID fragment, but only a long one -
    // "42" must not match every UUID that happens to contain a 4 and a 2.
    return /^\d{8,}$/.test(q) && ticket.id.toLowerCase().includes(q);
  }
  return ticket.id.toLowerCase().includes(q);
}
