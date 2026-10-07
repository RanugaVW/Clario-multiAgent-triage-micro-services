-- ==========================================
-- TICKET CONVERSATION THREAD (customer <-> staff replies)
-- ==========================================
-- One row per chat message posted AFTER a ticket was submitted. The original
-- issue stays in tickets.raw_text (the only text the ML pipeline ever sees) and
-- the first staff/AI answer stays in resolutions.final_response - the UI renders
-- those two as the opening of the thread, so nothing is duplicated here and the
-- orchestrator/sidecar never has to know this table exists.
--
-- Write path: Next.js /api/tickets/[id]/messages (service-role, after
-- requireUser()) - there is deliberately NO insert/update/delete policy, so a
-- browser holding the anon key cannot forge author_id/author_role.
-- Read path: the same API route for the initial load, plus Supabase Realtime
-- for live inserts, which is why the SELECT policies below are needed.
--
-- Run once in the Supabase SQL editor. Safe to re-run.

CREATE TABLE IF NOT EXISTS public.ticket_messages (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- CASCADE: both delete paths (/api/tickets DELETE and the sidecar's
    -- /customer_tickets/{id}) hand-delete known child tables before the
    -- ticket; cascading here means neither has to learn about this one.
    ticket_id     UUID NOT NULL REFERENCES public.tickets(id) ON DELETE CASCADE,
    -- SET NULL: removing an account must not erase the other party's history.
    author_id     UUID REFERENCES public.users(id) ON DELETE SET NULL,
    -- Role snapshotted at send time, so a later role change doesn't flip
    -- which side of the thread an old bubble renders on.
    author_role   VARCHAR(16) NOT NULL CHECK (author_role IN ('user', 'agent', 'admin')),
    body          TEXT NOT NULL CHECK (char_length(btrim(body)) BETWEEN 1 AND 5000),
    -- Client-generated idempotency key for optimistic sends: a retried POST
    -- (flaky network, double-click) hits the unique index instead of
    -- producing a duplicate bubble, and the client matches its pending
    -- bubble to the confirmed row by this value.
    client_msg_id UUID NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ticket_messages_client_msg_unique UNIQUE (ticket_id, client_msg_id)
);

-- Serves "the whole thread for ticket X, oldest first" and "messages after
-- cursor T" with one index range scan; also covers the ticket_id FK.
CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket_created
    ON public.ticket_messages (ticket_id, created_at);

CREATE INDEX IF NOT EXISTS idx_ticket_messages_author
    ON public.ticket_messages (author_id);

ALTER TABLE public.ticket_messages ENABLE ROW LEVEL SECURITY;

-- Belt and braces on top of "no write policy": even if someone later adds a
-- permissive policy by mistake, browser roles still cannot write.
REVOKE INSERT, UPDATE, DELETE ON public.ticket_messages FROM anon, authenticated;

DROP POLICY IF EXISTS "Customers view own ticket messages" ON public.ticket_messages;
CREATE POLICY "Customers view own ticket messages" ON public.ticket_messages
    FOR SELECT TO authenticated USING (
        EXISTS (
            SELECT 1 FROM public.tickets t
            WHERE t.id = ticket_messages.ticket_id
              AND t.user_id = (SELECT auth.uid())
        )
    );

-- Same staff expression as every other staff policy in supabase_schema.sql.
DROP POLICY IF EXISTS "Staff view all ticket messages" ON public.ticket_messages;
CREATE POLICY "Staff view all ticket messages" ON public.ticket_messages
    FOR SELECT TO authenticated USING (
        (SELECT role FROM public.users WHERE id = (SELECT auth.uid())) IN ('admin', 'agent')
    );

-- Realtime only broadcasts tables in this publication, and it evaluates the
-- SELECT policies above per subscriber, so a customer's channel never
-- receives another customer's messages.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_publication_tables
        WHERE pubname = 'supabase_realtime'
          AND schemaname = 'public' AND tablename = 'ticket_messages'
    ) THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE public.ticket_messages;
    END IF;
END $$;
