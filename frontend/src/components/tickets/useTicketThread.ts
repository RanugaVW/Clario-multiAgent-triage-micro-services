'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { supabase } from '../../lib/supabase';
import { fetchJson } from '../../lib/fetchJson';
import { mergeMessages, type MessageAuthorRole, type TicketMessage, type ThreadMessage } from '../../lib/ticketThread';

async function authHeaders(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

type ThreadResponse = { data: TicketMessage[]; ticketStatus: string | null };
type SendResponse = { data: TicketMessage; ticketStatus: string | null };

async function fetchThread(ticketId: string): Promise<ThreadResponse> {
  return fetchJson<ThreadResponse>(`/api/tickets/${ticketId}/messages`, { headers: await authHeaders() });
}

/**
 * State for one ticket's conversation: initial load, live inserts over
 * Supabase Realtime, and optimistic sends.
 *
 * Mount it only while the ticket panel is open - the Realtime channel lives
 * exactly as long as the component, so a long ticket list costs nothing until
 * a row is expanded.
 */
export function useTicketThread(
  ticketId: string,
  author: { id: string | null; role: MessageAuthorRole },
  onTicketStatusChange?: (status: string | null) => void
) {
  const [messages, setMessages] = useState<ThreadMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Kept in a ref so a parent re-rendering with a new callback identity
  // doesn't tear down and rebuild the Realtime channel.
  const statusCallback = useRef(onTicketStatusChange);
  useEffect(() => {
    statusCallback.current = onTicketStatusChange;
  }, [onTicketStatusChange]);

  useEffect(() => {
    // Guards against a response landing after the panel closed.
    let active = true;
    const refresh = () =>
      fetchThread(ticketId).then(
        (res) => {
          if (!active) return;
          setMessages((current) => mergeMessages(current, res.data));
          setLoadError(null);
          setLoading(false);
        },
        (e) => {
          if (!active) return;
          setLoadError(e instanceof Error ? e.message : 'Could not load the conversation');
          setLoading(false);
        }
      );

    refresh();
    const channel = supabase
      .channel(`ticket-messages:${ticketId}`)
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'ticket_messages', filter: `ticket_id=eq.${ticketId}` },
        (payload) => setMessages((current) => mergeMessages(current, [payload.new as TicketMessage]))
      )
      .subscribe((status) => {
        // Anything inserted between the first load and the channel going live
        // would otherwise be missed; merging makes the second fetch harmless.
        if (status === 'SUBSCRIBED') refresh();
      });
    return () => {
      active = false;
      supabase.removeChannel(channel);
    };
  }, [ticketId]);

  const deliver = useCallback(
    async (pending: ThreadMessage) => {
      try {
        const res = await fetchJson<SendResponse>(`/api/tickets/${ticketId}/messages`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
          body: JSON.stringify({ body: pending.body, clientMsgId: pending.client_msg_id, markResolved: pending.markResolved }),
        });
        setMessages((current) => mergeMessages(current, [res.data]));
        statusCallback.current?.(res.ticketStatus);
      } catch {
        // Only downgrade a still-pending bubble: the Realtime echo may already
        // have confirmed it even though the response itself failed.
        setMessages((current) =>
          current.map((m) => (m.client_msg_id === pending.client_msg_id && m.state === 'sending' ? { ...m, state: 'failed' } : m))
        );
      }
    },
    [ticketId]
  );

  const send = useCallback(
    (body: string, options: { markResolved?: boolean } = {}) => {
      const clientMsgId = crypto.randomUUID();
      const pending: ThreadMessage = {
        id: clientMsgId,
        ticket_id: ticketId,
        author_id: author.id,
        author_role: author.role,
        body: body.trim(),
        client_msg_id: clientMsgId,
        created_at: new Date().toISOString(),
        state: 'sending',
        markResolved: options.markResolved,
      };
      setMessages((current) => [...current, pending]);
      return deliver(pending);
    },
    [ticketId, author.id, author.role, deliver]
  );

  /** Resends a failed message with the SAME clientMsgId, so it can never duplicate. */
  const retry = useCallback(
    (clientMsgId: string) => {
      const failed = messages.find((m) => m.client_msg_id === clientMsgId && m.state === 'failed');
      if (!failed) return;
      const pending = { ...failed, state: 'sending' as const };
      setMessages((current) => current.map((m) => (m.client_msg_id === clientMsgId ? pending : m)));
      return deliver(pending);
    },
    [messages, deliver]
  );

  return { messages, loading, loadError, send, retry };
}
