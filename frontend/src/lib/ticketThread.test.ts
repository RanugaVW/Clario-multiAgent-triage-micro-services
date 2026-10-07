import { describe, it, expect } from 'vitest';
import { mergeMessages, isUuid, type ThreadMessage, type TicketMessage } from './ticketThread';

function row(clientMsgId: string, createdAt: string, overrides: Partial<TicketMessage> = {}): TicketMessage {
  return {
    id: `srv-${clientMsgId}`,
    ticket_id: 't1',
    author_id: 'u1',
    author_role: 'user',
    body: `body ${clientMsgId}`,
    client_msg_id: clientMsgId,
    created_at: createdAt,
    ...overrides,
  };
}

function pending(clientMsgId: string, createdAt: string): ThreadMessage {
  return { ...row(clientMsgId, createdAt), id: clientMsgId, state: 'sending' };
}

describe('mergeMessages', () => {
  it('replaces an optimistic bubble with its confirmed row instead of adding a second one', () => {
    const merged = mergeMessages([pending('c1', '2026-10-01T10:00:00.500Z')], [row('c1', '2026-10-01T10:00:00.000Z')]);

    expect(merged).toHaveLength(1);
    expect(merged[0]).toMatchObject({ id: 'srv-c1', state: 'sent' });
  });

  it('ignores the Realtime echo of a row it already has', () => {
    const once = mergeMessages([], [row('c1', '2026-10-01T10:00:00Z')]);
    const twice = mergeMessages(once, [row('c1', '2026-10-01T10:00:00Z')]);

    expect(twice).toHaveLength(1);
  });

  it('confirms a failed bubble when the server did save it after all', () => {
    const failed: ThreadMessage = { ...pending('c1', '2026-10-01T10:00:00Z'), state: 'failed' };

    expect(mergeMessages([failed], [row('c1', '2026-10-01T10:00:00Z')])[0].state).toBe('sent');
  });

  it('orders the thread oldest first regardless of arrival order', () => {
    const merged = mergeMessages(
      [],
      [row('late', '2026-10-01T10:05:00Z'), row('early', '2026-10-01T10:00:00Z'), row('mid', '2026-10-01T10:02:00Z')]
    );

    expect(merged.map((m) => m.client_msg_id)).toEqual(['early', 'mid', 'late']);
  });

  it('keeps unconfirmed bubbles alongside confirmed ones', () => {
    const merged = mergeMessages([pending('mine', '2026-10-01T10:03:00Z')], [row('theirs', '2026-10-01T10:01:00Z')]);

    expect(merged.map((m) => [m.client_msg_id, m.state])).toEqual([
      ['theirs', 'sent'],
      ['mine', 'sending'],
    ]);
  });
});

describe('isUuid', () => {
  // A literal, not crypto.randomUUID(): vitest.setup.ts stubs that globally.
  it('accepts a v4 UUID and rejects anything else', () => {
    expect(isUuid('9b2f4c1e-3a5d-4e7f-8a1b-2c3d4e5f6a7b')).toBe(true);
    expect(isUuid('not-a-uuid')).toBe(false);
    expect(isUuid(42)).toBe(false);
  });
});
