// Pure helpers behind the agent workspace (UR-008 / FR-035 / FR-036): which
// tickets a human still has to answer, in what order, and the figures shown
// above the queue. Kept free of React and fetch so the rules are unit-testable
// and the agent page cannot drift from the admin page's definition of "needs review".
import { splitCategories } from './classification';

export type QueueResolution = {
  id?: string;
  escalated: boolean;
  resolved_at?: string | null;
};

export type QueueTicket = {
  id: string;
  raw_text: string;
  subject?: string | null;
  customer_email?: string | null;
  status: string;
  created_at: string;
  ticket_drafts?: { draft_text?: string | null; domain?: string | null }[] | null;
  ticket_classifications?: {
    category?: string | null;
    priority?: string | null;
    sentiment?: string | null;
  }[] | null;
  resolutions?: QueueResolution[] | null;
};

/** A ticket already has a human/final answer attached. */
export function isAnswered(ticket: QueueTicket): boolean {
  return (ticket.resolutions ?? []).some((r) => !r.escalated);
}

/**
 * Same rule the admin console uses for its human-review queue: not yet answered,
 * and either carrying an escalation marker or escalated with no resolution row.
 */
export function needsHumanReview(ticket: QueueTicket): boolean {
  if (isAnswered(ticket)) return false;
  const resolutions = ticket.resolutions ?? [];
  return resolutions.some((r) => r.escalated) || (resolutions.length === 0 && ticket.status === 'escalated');
}

const PRIORITY_RANK: Record<string, number> = { critical: 0, urgent: 0, high: 1, medium: 2, low: 3 };
const UNKNOWN_RANK = 4;

export function priorityRank(priority: string | null | undefined): number {
  return PRIORITY_RANK[(priority ?? '').trim().toLowerCase()] ?? UNKNOWN_RANK;
}

/** Most urgent first; within a priority the longest-waiting ticket comes first. Does not mutate. */
export function sortReviewQueue(tickets: QueueTicket[]): QueueTicket[] {
  return [...tickets].sort((a, b) => {
    const byPriority =
      priorityRank(a.ticket_classifications?.[0]?.priority) - priorityRank(b.ticket_classifications?.[0]?.priority);
    if (byPriority !== 0) return byPriority;
    return Date.parse(a.created_at) - Date.parse(b.created_at);
  });
}

export function reviewQueue(tickets: QueueTicket[]): QueueTicket[] {
  return sortReviewQueue(tickets.filter(needsHumanReview));
}

export type QueueStats = {
  needsReview: number;
  oldestWaitingSince: string | null;
  resolvedToday: number;
};

function sameLocalDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

/** Figures derived from real rows - nothing here is a constant. `now` is injectable for tests. */
export function queueStats(tickets: QueueTicket[], now: Date = new Date()): QueueStats {
  const queue = tickets.filter(needsHumanReview);
  const waiting = queue.map((t) => Date.parse(t.created_at)).filter((ms) => !Number.isNaN(ms));

  const resolvedToday = tickets.filter((t) =>
    (t.resolutions ?? []).some((r) => {
      if (r.escalated || !r.resolved_at) return false;
      const when = new Date(r.resolved_at);
      return !Number.isNaN(when.getTime()) && sameLocalDay(when, now);
    })
  ).length;

  return {
    needsReview: queue.length,
    oldestWaitingSince: waiting.length ? new Date(Math.min(...waiting)).toISOString() : null,
    resolvedToday,
  };
}

/** First line of the ticket, ignoring any OCR block appended by the attachment pipeline. */
export function ticketHeadline(ticket: QueueTicket, max = 90): string {
  const subject = ticket.subject?.trim();
  const body = ticket.raw_text.split('[OCR EXTRACTED TEXT FROM ATTACHMENT]')[0].trim();
  const text = subject || body;
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

export function ticketCategories(ticket: QueueTicket): string[] {
  return splitCategories(ticket.ticket_classifications?.[0]?.category);
}

/** The AI draft a reviewer starts from (empty string when the pipeline produced none). */
export function draftFor(ticket: QueueTicket): string {
  return (ticket.ticket_drafts ?? []).find((d) => d.draft_text?.trim())?.draft_text?.trim() ?? '';
}
