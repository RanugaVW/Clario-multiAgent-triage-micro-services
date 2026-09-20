-- ============================================================================
-- CLARIO DATABASE PERFORMANCE - PROPOSED INDEXES + SLOW-QUERY MONITORING (PER-004)
-- ============================================================================
-- STATUS: APPLIED by the project owner on 2026-09-20 (reported; verify with the queries in NFR Testing/PER-004-Database-Performance/REPORT.md).
-- Every statement is idempotent (IF NOT EXISTS) and can be run more than once.
--
-- WHY: PostgreSQL does not index the referencing side of a foreign key. Every
-- "SELECT ... FROM tickets, ticket_classifications(...), resolutions(...)" the
-- app issues (frontend /api/tickets, /api/reports, user history) joins child
-- tables on ticket_id, and every "DELETE FROM tickets" cascades through them
-- by ticket_id. Without these indexes each join/cascade is a sequential scan of
-- the child table, which is fine at a few hundred rows and is the classic cause
-- of the multi-second query spikes seen under load once the tables grow.
--
-- LOCKING NOTE: plain CREATE INDEX blocks writes to the table while it builds.
-- On the current small tables that is milliseconds. If a table has grown large,
-- run each statement separately with CREATE INDEX CONCURRENTLY (cannot run
-- inside a transaction block / multi-statement editor run).
--
-- ROLLBACK: DROP INDEX IF EXISTS public.<index_name>;   (nothing else changes)
-- ============================================================================

-- --- foreign-key join / cascade paths (child.ticket_id) ---------------------
CREATE INDEX IF NOT EXISTS idx_ticket_classifications_ticket ON public.ticket_classifications (ticket_id);
CREATE INDEX IF NOT EXISTS idx_ticket_drafts_ticket          ON public.ticket_drafts (ticket_id);
CREATE INDEX IF NOT EXISTS idx_ticket_validations_ticket     ON public.ticket_validations (ticket_id);
CREATE INDEX IF NOT EXISTS idx_human_reviews_ticket          ON public.human_reviews (ticket_id);
CREATE INDEX IF NOT EXISTS idx_resolutions_ticket            ON public.resolutions (ticket_id);
CREATE INDEX IF NOT EXISTS idx_ticket_logs_ticket            ON public.ticket_logs (ticket_id);

-- --- ownership lookups ("my tickets": WHERE user_id = ? ORDER BY created_at DESC) ---
CREATE INDEX IF NOT EXISTS idx_tickets_user_created          ON public.tickets (user_id, created_at DESC);

-- --- staff list / reports (ORDER BY created_at, date-range filters) ---------
CREATE INDEX IF NOT EXISTS idx_tickets_created               ON public.tickets (created_at DESC);

-- --- FK columns pointing at users (ON DELETE SET NULL scans the child on user delete) ---
CREATE INDEX IF NOT EXISTS idx_human_reviews_reviewer        ON public.human_reviews (reviewer_id);
CREATE INDEX IF NOT EXISTS idx_resolutions_resolved_by       ON public.resolutions (resolved_by);

-- --- optional, only if the status filter is used on large volumes -----------
-- Partial index: the human-review queue is a small, hot slice of the table.
CREATE INDEX IF NOT EXISTS idx_tickets_escalated             ON public.tickets (created_at) WHERE status = 'escalated';

-- ============================================================================
-- SLOW-QUERY MONITORING ("long-running queries shall be monitored")
-- ============================================================================
-- Supabase ships the pg_stat_statements extension (schema: extensions). This view
-- lists statements whose average time exceeds the 500 ms acceptance threshold in
-- PER-004, worst first. It is readable only by the service role / postgres, never by
-- the anon or authenticated (customer) roles, because query text can include data.
CREATE EXTENSION IF NOT EXISTS pg_stat_statements WITH SCHEMA extensions;

CREATE OR REPLACE VIEW public.slow_queries
WITH (security_invoker = true) AS
SELECT
    queryid,
    calls,
    round(mean_exec_time::numeric, 1)  AS mean_ms,
    round(max_exec_time::numeric, 1)   AS max_ms,
    round(total_exec_time::numeric, 0) AS total_ms,
    rows,
    left(query, 300)                   AS query
FROM extensions.pg_stat_statements
WHERE mean_exec_time > 500
  AND query NOT ILIKE '%pg_stat_statements%'
ORDER BY mean_exec_time DESC;

REVOKE ALL ON public.slow_queries FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.slow_queries TO service_role;

-- Usage:   SELECT * FROM public.slow_queries LIMIT 20;
-- Note: the view runs with the caller's privileges (security_invoker). In the SQL Editor (postgres) it shows everything.
-- Via the service_role, other roles' statements may show as "<insufficient privilege>" unless you also run:
--   GRANT pg_read_all_stats TO service_role;      -- optional; decide deliberately, query text can contain data
-- Reset after a tuning change:   SELECT extensions.pg_stat_statements_reset();
--
-- VERIFY an index is used (should show "Index Scan"/"Bitmap Index Scan", not "Seq Scan" on big tables):
--   EXPLAIN (ANALYZE, BUFFERS)
--   SELECT t.id, c.category, r.escalated
--   FROM tickets t
--   LEFT JOIN ticket_classifications c ON c.ticket_id = t.id
--   LEFT JOIN resolutions r ON r.ticket_id = t.id
--   WHERE t.user_id = '<some user uuid>' ORDER BY t.created_at DESC;
-- (On a tiny table Postgres may still choose a Seq Scan because it is genuinely cheaper - that is correct.)
