# UR-001 — User Interface Consistency

**Status before:** 🟡 Partial — dashboard and admin each hand-built a sidebar, the agent workspace used a different (top-header) layout, and the login page hand-rolled its own card/inputs/button while register used the shared components.
**Status after (updated 2026-09-20):** ✅ **One navigation shell for every workspace.** The customer dashboard, the agent workspace, and the whole admin area (console, Reports, Users) all render inside `AppShell`; all four auth pages use the shared components. There is now exactly one sidebar implementation in the app. Visual review is still needed (see limits).
**Database changes:** none.

## What changed (`frontend`)
- **`components/AppShell.tsx`** (new) — the shared navigation layout: brand block, primary nav (`aria-current="page"` on the active item), signed-in identity, footer links, sign out. Sidebar from `lg` up; the same blocks stacked on top below it. Owns the single `<main>` landmark; visible focus ring on every item.
- **`app/agent/AgentShell.tsx`** (new) — AppShell configured for agents (shows *Admin panel* link for admins). Used by `/agent` and `/agent/[id]`; the old top-header layout was removed.
- **`/admin/reports`** — now inside AppShell (brand "System administration", *Back to administration* link) instead of its own top layout.
- **Login** — rebuilt on `GlassPanel` / `GlassInput` / `PasswordInput` / `GlassButton` like register / forgot-password / reset-password (keeps the decorative animated background). The hand-rolled white button and bespoke input styles are gone.
- The agent Review button was hover-only (invisible to keyboard users) — now always visible with an accessible name (done in the earlier agent-workflow item).

## Tests
| File | Cases | Covers |
|---|---|---|
| `components/AppShell.test.tsx` | 6 | content, landmarks (1 nav / 1 aside / 1 main), `aria-current` only on the active item, sign-out callback, optional parts omitted, **keyboard tab order** |
| `app/__tests__/ui-consistency.test.ts` | 9 | structural guardrail: the 4 auth pages use `GlassPanel`/`GlassButton`, no raw `<input>`, no hand-rolled primary button; agent pages and Reports render inside the shared shell and do not own `<main>`; AgentShell builds on AppShell |
| `app/__tests__/agent-workflow.test.tsx` | +1 | agent page shows the shell nav + identity and signs out to `/login` |
Existing login/register/forgot/reset/reports/agent tests all still pass.

**Mutation checks (reverted):** login back to a hand-rolled button → guard fails; agent page dropping the shell → 2 fail; `aria-current` removed → fails.
**Full verification:** `vitest` 33 files / **306 tests** · `eslint` 0 errors · `next build` OK · `tsc` only the pre-existing `admin-ticket-attachment.test.tsx` error.

## Update 2026-09-20 — dashboard and admin console migrated
- `AppShell` now mirrors the dashboard's original sidebar (sticky on `lg`, single DOM set laid out responsively) and supports **tab items** (`onClick` → `<button type="button">` with `aria-current`) as well as route items (`href` → `<Link>`), a `warn` highlight (queues that need attention), coloured footer links, a rich brand title and `mainClassName`.
- **Customer dashboard:** its hand-built sidebar and `DashboardNavItem` were removed; tabs *New ticket* / *My tickets* are shell nav items (opening *My tickets* still refreshes the history); *Admin panel* / *Agent workspace* are now real links (they navigate, so a link is the correct element — four existing tests that asserted `button` were updated to assert the link and its `href`).
- **Admin console:** the hand-built sidebar, the separate mobile header and the duplicate mobile tab row (`SidebarNavItem`, `TabBtn`, `handleLogout`) were removed. Its five tabs are the shell's nav, with **Reports** and **Users** always beside them (`AdminShell` gained a `console` section). On phones the nav is the shell's horizontally scrolling row, replacing the duplicated tab row.
- New tests: `dashboard-shell.test.tsx` (6: landmarks and tabs, tab switch + `aria-current`, history refresh on tab open, sign-out, admin/agent links only for their roles), `admin-console-shell.test.tsx` (4: five tabs + Reports/Users links, current-tab marker, sign-out, non-admin redirect), AppShell tab/warn/brand cases (3), and the structural guard now also fails if **any** workspace page contains its own `<aside>`.
- Mutation checks (reverted): tab button losing `type="button"`, warn shown while active, admin link for everyone, admin tabs doing nothing, history refresh removed — all caught; the last one **initially survived** (no test covered it), so a test was added.
- Full verification: `vitest` 39 files / **386 tests** · `eslint` 0 errors · `next build` OK · `tsc` only the pre-existing error.
- A test-hygiene note: a `useRouter` mock returning a *new* object each render makes the dashboard's effect loop (it depends on `router`); the real Next router is stable. New tests use a stable router.

## Limits (honest)
- **Not visually verified.** I cannot render pages in a browser here; the login card in particular changed appearance (now the shared glass panel). Please look at `/login`, `/dashboard`, `/agent`, `/admin` (all five tabs), `/admin/reports` and `/admin/users` once, including a narrow window.
- **Visual changes to expect:** the agent/Reports/Users active-tab style now matches the dashboard's amber glow; the admin console's separate mobile header and pill tab row are gone (replaced by the shell's top bar + scrolling nav); the admin sidebar footer shows "Logged in as …" like the dashboard.
- The guardrail test is source-based (regex on page files) — it pins structure, not looks; it is not a substitute for a visual-regression tool.
