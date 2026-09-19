import { describe, it, expect } from 'vitest';
import {
  isAnswered, needsHumanReview, priorityRank, sortReviewQueue, reviewQueue, queueStats,
  ticketHeadline, ticketCategories, draftFor, type QueueTicket,
} from './agentQueue';

const t = (over: Partial<QueueTicket> & { priority?: string }): QueueTicket => {
  const { priority, ...rest } = over;
  return {
    id: 't', raw_text: 'help', status: 'escalated', created_at: '2026-09-19T08:00:00Z',
    ticket_classifications: priority ? [{ priority, category: 'Refunds' }] : [],
    resolutions: [],
    ...rest,
  };
};

describe('needsHumanReview (same rule as the admin queue)', () => {
  it('is true for an escalated ticket with no resolution row', () => {
    expect(needsHumanReview(t({}))).toBe(true);
  });
  it('is true when an escalation marker resolution exists', () => {
    expect(needsHumanReview(t({ status: 'open', resolutions: [{ escalated: true }] }))).toBe(true);
  });
  it('is false once a non-escalated resolution exists, even with an escalation marker', () => {
    const ticket = t({ resolutions: [{ escalated: true }, { escalated: false }] });
    expect(isAnswered(ticket)).toBe(true);
    expect(needsHumanReview(ticket)).toBe(false);
  });
  it('is false for an ordinary in-flight ticket', () => {
    expect(needsHumanReview(t({ status: 'open' }))).toBe(false);
  });
  it('tolerates null relations', () => {
    expect(needsHumanReview(t({ resolutions: null, status: 'escalated' }))).toBe(true);
  });
});

describe('ordering', () => {
  it('ranks Critical/Urgent > High > Medium > Low > unknown, case-insensitively', () => {
    expect(['Critical', 'urgent', 'HIGH', 'medium', 'Low', 'weird', null].map(priorityRank))
      .toEqual([0, 0, 1, 2, 3, 4, 4]);
  });
  it('sorts by priority, then oldest first, without mutating the input', () => {
    const input = [
      t({ id: 'low-old', priority: 'Low', created_at: '2026-09-01T00:00:00Z' }),
      t({ id: 'high-new', priority: 'High', created_at: '2026-09-19T00:00:00Z' }),
      t({ id: 'high-old', priority: 'High', created_at: '2026-09-10T00:00:00Z' }),
      t({ id: 'crit', priority: 'Critical', created_at: '2026-09-18T00:00:00Z' }),
    ];
    const snapshot = input.map((x) => x.id);
    expect(sortReviewQueue(input).map((x) => x.id)).toEqual(['crit', 'high-old', 'high-new', 'low-old']);
    expect(input.map((x) => x.id)).toEqual(snapshot);
  });
  it('reviewQueue filters out answered tickets and sorts the rest', () => {
    const q = reviewQueue([
      t({ id: 'done', resolutions: [{ escalated: false }] }),
      t({ id: 'a', priority: 'Low' }),
      t({ id: 'b', priority: 'Urgent' }),
    ]);
    expect(q.map((x) => x.id)).toEqual(['b', 'a']);
  });
});

describe('queueStats', () => {
  const now = new Date(2026, 8, 19, 15, 0, 0); // local time
  it('counts real rows and reports the longest-waiting ticket', () => {
    const stats = queueStats([
      t({ id: '1', created_at: '2026-09-17T10:00:00Z' }),
      t({ id: '2', created_at: '2026-09-18T10:00:00Z' }),
      t({ id: '3', status: 'open' }),
    ], now);
    expect(stats.needsReview).toBe(2);
    expect(stats.oldestWaitingSince).toBe('2026-09-17T10:00:00.000Z');
  });
  it('is zero / null for an empty queue rather than a made-up figure', () => {
    expect(queueStats([], now)).toEqual({ needsReview: 0, oldestWaitingSince: null, resolvedToday: 0 });
  });
  it('counts only non-escalated resolutions made on the same local day', () => {
    const today = new Date(2026, 8, 19, 9, 0, 0).toISOString();
    const yesterday = new Date(2026, 8, 18, 9, 0, 0).toISOString();
    const stats = queueStats([
      t({ id: 'a', status: 'resolved', resolutions: [{ escalated: false, resolved_at: today }] }),
      t({ id: 'b', status: 'resolved', resolutions: [{ escalated: false, resolved_at: yesterday }] }),
      t({ id: 'c', resolutions: [{ escalated: true, resolved_at: today }] }),
      t({ id: 'd', status: 'resolved', resolutions: [{ escalated: false, resolved_at: 'garbage' }] }),
    ], now);
    expect(stats.resolvedToday).toBe(1);
  });
});

describe('display helpers', () => {
  it('headline prefers the subject, else the text before the OCR block, and truncates', () => {
    expect(ticketHeadline(t({ subject: '  Refund please ' }))).toBe('Refund please');
    expect(ticketHeadline(t({ raw_text: 'Login broken\n[OCR EXTRACTED TEXT FROM ATTACHMENT]\nnoise' }))).toBe('Login broken');
    expect(ticketHeadline(t({ raw_text: 'x'.repeat(200) }), 10)).toBe('xxxxxxxxxx…');
  });
  it('splits multi-category classifications', () => {
    const ticket = t({});
    ticket.ticket_classifications = [{ category: 'Billing & Invoicing, Refunds' }];
    expect(ticketCategories(ticket)).toEqual(['Billing & Invoicing', 'Refunds']);
    expect(ticketCategories(t({}))).toEqual([]);
  });
  it('draftFor returns the first non-empty draft or an empty string', () => {
    const ticket = t({});
    ticket.ticket_drafts = [{ draft_text: '  ' }, { draft_text: ' Hello ' }];
    expect(draftFor(ticket)).toBe('Hello');
    expect(draftFor(t({}))).toBe('');
  });
});
