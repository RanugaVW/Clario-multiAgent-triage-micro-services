'use client';

import { useEffect, useRef } from 'react';
import { Notice } from '../ui/Notice';
import { isStaffRole, type MessageAuthorRole, type ThreadMessage } from '../../lib/ticketThread';
import { useTicketThread } from './useTicketThread';
import { MessageBubble } from './MessageBubble';
import { MessageComposer } from './MessageComposer';

function authorLabel(message: ThreadMessage, viewerIsStaff: boolean, viewerId: string | null): string {
  if (message.author_id && message.author_id === viewerId) return 'You';
  if (!isStaffRole(message.author_role)) return 'Customer';
  // Customers just see "Support"; staff can tell agents and admins apart.
  if (!viewerIsStaff) return 'Support';
  return message.author_role === 'admin' ? 'Admin' : 'Agent';
}

/**
 * The follow-up conversation for one ticket, shown inside its expanded panel
 * below the original message and resolution. Customer and staff views share
 * this component; `viewer.role` decides which side is "mine".
 */
export function TicketThread({
  ticketId,
  viewer,
  canResolve = false,
  onTicketStatusChange,
}: {
  ticketId: string;
  viewer: { id: string | null; role: MessageAuthorRole };
  canResolve?: boolean;
  onTicketStatusChange?: (status: string | null) => void;
}) {
  const { messages, loading, loadError, send, retry } = useTicketThread(ticketId, viewer, onTicketStatusChange);
  const viewerIsStaff = isStaffRole(viewer.role);
  const listRef = useRef<HTMLOListElement>(null);

  // Keep the newest message in view as the thread grows.
  useEffect(() => {
    const list = listRef.current;
    if (list) list.scrollTop = list.scrollHeight;
  }, [messages.length]);

  return (
    <section aria-label="Conversation" className="space-y-3 border-t border-border pt-4">
      <span className="block text-caption text-fg-muted">Conversation</span>

      {loadError && (
        <Notice tone="danger" role="alert" className="p-3">
          <span className="text-caption">{loadError}</span>
        </Notice>
      )}

      {!loading && messages.length === 0 && !loadError && (
        <p className="text-app text-fg-muted">
          {viewerIsStaff
            ? 'No follow-up messages on this ticket yet.'
            : 'Need to add something or ask a follow-up? Message the support team here.'}
        </p>
      )}

      {messages.length > 0 && (
        <ol ref={listRef} role="log" aria-live="polite" className="max-h-96 space-y-3 overflow-y-auto pr-1">
          {messages.map((m) => {
            // Mine = the side I'm on, so a second agent's replies still sit on
            // the staff side for every staff viewer.
            const mine = isStaffRole(m.author_role) === viewerIsStaff;
            return (
              <MessageBubble
                key={m.client_msg_id}
                message={m}
                mine={mine}
                authorLabel={authorLabel(m, viewerIsStaff, viewer.id)}
                onRetry={() => retry(m.client_msg_id)}
              />
            );
          })}
        </ol>
      )}

      <MessageComposer
        onSend={send}
        canResolve={canResolve}
        placeholder={viewerIsStaff ? 'Reply to the customer…' : 'Write a message to support…'}
      />
    </section>
  );
}
