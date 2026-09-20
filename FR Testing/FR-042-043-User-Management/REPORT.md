# FR-042 Role Management · FR-043 Account Status Management (SRS §3.1.12)

**Status before:** 🔴 both — no UI or endpoint to change a role after signup; `public.users` had no status column; nothing could suspend an account.
**Status after:** ✅ (app side, verified with a mocked database) — administrators manage roles and account status from `/admin/users`, every change is audited, and a suspended account cannot sign in.
**Database changes:** `supabase_user_management.sql` was **applied by you on 2026-09-20 (reported by the user; not verified by me)**. Verification queries are at the end of this report. If it was not applied, the Users page shows a clear "run the migration" message (503) and every other page/route behaves as before.

Acceptance criteria — FR-042: *role changes take effect immediately* · *permission updates are logged*. FR-043: *suspended users cannot authenticate* · *status changes are auditable*. A1: *invalid role assignment is rejected*.

## The SQL you need to run (`supabase_user_management.sql`, idempotent)
1. `ALTER TABLE public.users ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','deactivated'))` — existing users become `active`.
2. `CREATE TABLE IF NOT EXISTS public.admin_audit_log (…actor_id, target_user_id, action, old_value, new_value, created_at)` with **RLS enabled and no policies** (only the service role can touch it) and two indexes on the FK columns.
Rollback: `DROP TABLE public.admin_audit_log; ALTER TABLE public.users DROP COLUMN status;`

## What was built
- **`lib/userManagement.ts`** — pure rules: valid roles/statuses (allow-list; `constructor`, `''`, wrong types rejected), 404 for unknown user, no-op requests rejected, and **an administrator cannot change their own role or status** (prevents locking out the platform).
- **`/api/admin/users`** (admin only): `GET` lists users (paginated); `PATCH {id, role?, status?}`:
  1. verifies caller is admin, loads the target, validates → 400 / 403 / 404 with nothing written;
  2. updates `public.users`;
  3. on a status change, sets/lifts a **Supabase Auth ban** via the Admin API (`ban_duration` `876000h` for suspended/deactivated, `none` for active) — this is what makes "suspended users cannot authenticate" true: a banned user cannot sign in or refresh a session;
  4. writes one `admin_audit_log` row per change (old → new, actor, target) and a structured `admin.user_change` log line;
  5. **if the ban or the audit write fails, the row (and ban) are restored and an error is returned** — no half-applied or unaudited change.
- **`requireUser` (all `/api/*` routes)** now also checks the caller's own account status, so a suspension bites **immediately** even for an access token issued before it (bans don't invalidate live tokens). Fail-open on lookup problems (including the column not existing yet) by design — the Auth ban is the primary control; a schema lag must not lock everyone out.
- **`/admin/users`** page inside the shared admin shell: role and status selects per user (own row disabled), **confirmation before suspend/deactivate**, reactivation and role changes apply directly, server rejections shown, missing-migration hint shown; linked from the admin sidebar.
- **Login** now says "This account has been suspended or deactivated. Please contact an administrator." instead of Supabase's raw "User is banned".
- New shared `AdminShell` (Reports + Users) on the `AppShell` from UR-001.

## Tests (frontend `vitest` 37 files / **370 tests**; `pytest tests/contracts` **43**)
| File | Cases | Covers |
|---|---|---|
| `lib/userManagement.test.ts` | 16 | valid changes, only-what-changes, no-op, 8 invalid-input forms, 404 ordering, self-change forbidden, `isActive`, ban duration |
| `lib/apiAuth.test.ts` | 9 | active accepted; suspended/deactivated rejected despite valid token; status of the *verified caller* is what's read; fail-open ×4; bad token never reaches the lookup |
| `api/admin/users/route.test.ts` | 24 | 401 / 403 (user, agent, **suspended admin**), list, 503 hint, no internals leaked, role change + audit row + log, A1 rejections ×4, 404, bad JSON, suspend→ban, reactivate→unban, deactivate, two audit rows, cannot suspend self, **rollback on ban failure, on audit failure (row + ban), plain update failure, missing column** |
| `__tests__/admin-users.test.tsx` | 12 | list + token, role change without prompt, confirm/cancel/apply suspend, stronger deactivate prompt, reactivate, own row disabled, server rejection shown & list unchanged, 503 hint, non-admin redirects ×3 |
| `__tests__/auth.test.tsx` | +1 | suspended-account message |
| `tests/contracts/test_db_indexing.py` | +1 | migration is idempotent, RLS on/no policies, FK columns indexed, non-destructive |
| existing route tests | – | 18 assertions of "never queried data" now ignore the new `users` status lookup (documented in each file) |

**Mutation checks (each reverted, all caught):** self-change allowed · suspended treated as active · ban never applied · `requireUser` ignoring status · no rollback after audit failure · no rollback after ban failure · agent allowed to manage users · no suspend confirmation · raw "banned" message.
**Also:** `eslint` 0 errors · `next build` OK (`/admin/users`, `/api/admin/users`) · `tsc` only the pre-existing `admin-ticket-attachment.test.tsx` error.

## Limits — please read
- **Never run against real Supabase.** Everything is verified against a mocked client; I could not authorise the Supabase MCP, run the SQL, or call the Auth Admin API. Two assumptions to confirm after you apply it: (a) `auth.admin.updateUserById(id, { ban_duration })` with `'876000h'` / `'none'` behaves as documented, (b) the `users` table has **no UPDATE policy for customers** (per `supabase_schema.sql` only SELECT exists) — otherwise a customer could edit their own role/status. Quick check: try `UPDATE users SET role='admin'` as a normal user via the anon key; it must affect 0 rows.
- **Java services:** they validate the Supabase JWT themselves and do not consult `users.status`. A suspended user's *already-issued* token (up to its expiry, typically 1 h) could still call the ticket-submission API until it expires; the Auth ban stops any refresh. The Next.js API routes check status on every request. Closing the Java gap needs either a shorter JWT lifetime or a status check in the gateway — not done.
- **"Role changes take effect immediately"** holds for the Next.js routes (role is read from the DB per request) and the UI on next load. If the Java services or `AuthContext` cache a role from the JWT, they see the change at next token refresh.
- No self-service "last admin" guard beyond "you cannot change yourself" (with ≥1 other admin that is sufficient; the first admin must be created in SQL).
- The audit log has no viewer UI (service-role only by design); read it in the SQL Editor. Adding an admin-facing audit page would be a small follow-up.
- Existing `handle_new_user` trigger is unchanged; new signups get `status='active'` from the column default.

## Post-apply verification (read-only; run in the SQL Editor)
```sql
-- 1) status column exists, existing users are all active
SELECT status, count(*) FROM public.users GROUP BY status;                      -- expect: active | <n>
-- 2) audit table exists, RLS on, and NO policies (service role only)
SELECT relrowsecurity FROM pg_class WHERE oid = 'public.admin_audit_log'::regclass;   -- expect: true
SELECT count(*) FROM pg_policies WHERE tablename = 'admin_audit_log';                  -- expect: 0
-- 3) customers must not be able to edit their own row (expect: no UPDATE policy on users)
SELECT policyname, cmd FROM pg_policies WHERE tablename = 'users';                    -- expect: only SELECT policies
```
Then, in the app as an admin: change a test user's role and suspend/reactivate a test user, and confirm a suspended user gets the "suspended or deactivated" message at login. Rows appear in `SELECT * FROM public.admin_audit_log ORDER BY created_at DESC;`.
