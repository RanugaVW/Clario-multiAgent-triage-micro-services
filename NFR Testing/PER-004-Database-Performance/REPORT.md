# PER-004 — Database Performance

**Status before:** 🔴 Not implemented — no custom indexes on any core table; no monitoring of slow queries.
**Status after:** 🟡→✅ **Applied by you on 2026-09-20 (reported by the user; I could not verify it — no database access from here).** Verify with the queries in the *Post-apply verification* section below; the ≤ 500 ms criterion is still unmeasured.

Requirements: *queries optimized using appropriate indexing* · *frequently accessed data retrieved efficiently* · *long-running queries monitored* · Acceptance: *standard queries ≤ 500 ms*.

## The finding
PostgreSQL does **not** index the referencing side of a foreign key. The app joins `tickets` to `ticket_classifications`, `ticket_drafts`, `resolutions`, `ticket_validations`
(staff list, reports, user history) and cascades deletes through them all by `ticket_id`. With no index each is a sequential scan of the child table — harmless now, and the usual
reason a query "spikes to a minute under load" as data grows (the spike observed in an earlier concurrent-load test).

## What is in `supabase_performance_indexes.sql` (repo root, next to the other `supabase_*.sql`)
- **11 indexes** (10 plus the optional partial one), all `CREATE INDEX IF NOT EXISTS` (idempotent): `ticket_id` on `ticket_classifications`, `ticket_drafts`, `ticket_validations`, `human_reviews`, `resolutions`, `ticket_logs`;
  `tickets(user_id, created_at DESC)` for "my tickets"; `tickets(created_at DESC)` for staff lists and date-range reports; `human_reviews(reviewer_id)`, `resolutions(resolved_by)` (FK to users);
  a small partial index for the `escalated` review queue.
- **Slow-query monitoring:** `public.slow_queries` view over `pg_stat_statements` listing statements averaging > 500 ms (the PER-004 threshold), worst first; revoked from `anon`/`authenticated`, granted to `service_role` only.
- Rollback is `DROP INDEX IF EXISTS …` per index; no table/column is altered. Header notes `CREATE INDEX CONCURRENTLY` if tables have grown large.
- Not duplicated: `customer_feedback.ticket_id` (already UNIQUE) and every `response_evaluations` / override index that already exists.

## Tests (`tests/contracts/test_db_indexing.py`, runs in the existing CI contract job) — 17 cases
- **Every foreign-key column in the three schema files is covered** (existing index, UNIQUE, primary key, or the proposal) — one parametrised case per FK, so a future FK added without an index fails CI.
- The proposal is idempotent (every `CREATE INDEX` has `IF NOT EXISTS`) and non-destructive (no DROP/TRUNCATE/DELETE/ALTER TABLE).
- The slow-query view is not readable by customers and uses the 500 ms threshold.
- The parser is sanity-checked against known FKs.
- **Mutation checks (reverted):** removing the `resolutions` index → fails; making one index non-idempotent → fails; granting the view to `authenticated` → fails.
- `pytest tests/contracts`: 42 passed.

## What is NOT verified (be aware)
- **The SQL has never been executed.** This sandbox has the `psql` client but no PostgreSQL server, no reachable Docker daemon and no authorised Supabase MCP, so the tests are static analysis of the file, not a run against Postgres. Run it first on a copy/branch database if you can.
- **No timing was measured.** I cannot claim "≤ 500 ms" is met; the deliverable is the indexes plus the means to check: the file ends with an `EXPLAIN (ANALYZE, BUFFERS)` recipe. On tiny tables Postgres may legitimately still choose a Seq Scan.
- Index names/columns were derived from `supabase_*.sql`; if your live database has drifted from those files, `IF NOT EXISTS` protects against duplicates by *name* only.
- `pg_stat_statements` query text can contain data; see the note in the file before granting `pg_read_all_stats`.

## Post-apply verification (read-only; run in the SQL Editor and check the results)
```sql
-- 1) all 11 indexes exist (expect 11 rows)
SELECT indexname FROM pg_indexes WHERE schemaname='public' AND indexname IN (
 'idx_ticket_classifications_ticket','idx_ticket_drafts_ticket','idx_ticket_validations_ticket','idx_human_reviews_ticket',
 'idx_resolutions_ticket','idx_ticket_logs_ticket','idx_tickets_user_created','idx_tickets_created',
 'idx_human_reviews_reviewer','idx_resolutions_resolved_by','idx_tickets_escalated');
-- 2) the monitoring view exists and customers cannot read it (expect service_role only)
SELECT grantee, privilege_type FROM information_schema.role_table_grants WHERE table_schema='public' AND table_name='slow_queries';
-- 3) nothing is slow right now
SELECT * FROM public.slow_queries LIMIT 20;
```
(Correction: an earlier draft of this report said 10 indexes; the file creates 11.)
