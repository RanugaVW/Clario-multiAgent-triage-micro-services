# Accessibility Test Report (WCAG 2.1 A/AA) — Clario System

**Date:** 2026-09-13
**Tested by:** Ranuga Weerasekara, Clario QA Team
**Branch:** `main`
**Environment:** The real `next dev` server (`:3000`, Next.js 16.2.12) and the production Supabase project, using the same disposable customer/admin test accounts `frontend/e2e/global-setup.ts` creates for `Testing/03-UI-E2E-Testing`. No mocking, no static HTML snapshots.

**Result: 1 real bug found and fixed. Final result: 6/6 automated checks passed, 0 WCAG 2.1 A/AA violations across all 5 pages.** Two apparent "violations" from the first run turned out to be a test-methodology artifact (mid-CSS-animation sampling), not product bugs — see §4 for how that was confirmed rather than assumed.

## 1. Scope

Per the course's assigned tool set for this phase (JAWS, a color-contrast checker, axe DevTools, Google Lighthouse), this phase automates WCAG 2.1 A/AA coverage across every real page in the frontend:

| Page | Auth required | How it was reached |
|---|---|---|
| `/login` | No | Direct navigation |
| `/register` | No | Direct navigation |
| `/dashboard` | Yes (customer) | Real UI login via the disposable customer fixture |
| `/admin` | Yes (admin) | Real UI login via the disposable admin fixture |
| `/agent` | Yes (agent/admin) — fixed 2026-09-13, see §7 | Real UI login via the disposable admin fixture |

Each page was scanned with axe-core against the `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa` rule tags. A scripted keyboard-only navigation check (tab order + visible focus) was added for `/login` as a substitute for part of what a manual screen-reader pass would cover.

**Not covered:** the `/agent/[ticketId]` detail route, the ticket-submission modal/flow, and any state reachable only with the Java backend services running (this environment only ran the frontend + Supabase — see `Testing/03-UI-E2E-Testing`'s README for why that's sufficient for the routes this repo's auth flow actually depends on). A real JAWS/NVDA screen-reader pass is also not covered — see §6.

## 2. Tool choice: why axe-core + Lighthouse, not WAVE / manual axe DevTools / a separate contrast checker

The course handed out four reference tools (JAWS, a color-contrast checker, axe DevTools, Google Lighthouse). All four are real, standard tools — the choice made here was *how* to run the two automatable ones so they'd actually integrate with this repo's existing infrastructure, rather than which vendor's engine to trust:

- **axe DevTools' underlying engine is axe-core**, and it's also what Lighthouse's own accessibility category runs internally. `@axe-core/playwright` runs that exact engine programmatically inside the Playwright suite this repo already has (`frontend/e2e`, `playwright.config.ts`). That matters concretely here: `/dashboard` and `/admin` require a real logged-in session, and the manual axe DevTools extension can only inspect whatever's already on screen in the current tab — it can't drive `frontend/e2e/helpers.ts`'s `loginViaUi()` first. Scripting it means the authenticated pages actually got scanned in their real logged-in state, not skipped.
- **WAVE** is another browser extension with essentially the same manual, one-tab-at-a-time workflow and materially overlapping rule coverage with axe DevTools — it doesn't add authenticated-session automation either, so running both extensions manually would have meant double the manual effort for the same two public pages, and still no coverage of `/dashboard`/`/admin`.
- **Lighthouse** was run via its CLI as a second, independently-implemented check (not just "axe again") against the two pages it can reach without a login session, both for corroboration and for a standard numeric accessibility score.
- **A standalone color-contrast checker** (e.g. the browser extension in the reference list) checks one foreground/background pair at a time, by hand. axe's `color-contrast` rule implements the same WCAG contrast-ratio formula but checks every visible text node on the page automatically — strictly broader coverage for the static/resting-state case (see §4 for the one case where that same automation needed a correction).
- **JAWS** is licensed and Windows-only. This is a Linux environment with no license — see §6 for what was substituted and what's still a follow-up.

## 3. Environment & tooling

| | |
|---|---|
| Test script | `frontend/e2e/accessibility.spec.ts` (`@playwright/test` 1.62 + `@axe-core/playwright` 4.13.0) |
| Corroboration | `lighthouse` 13.4.1 CLI, `google-chrome` as the launch target |
| Frontend under test | `next dev` on `:3000`, started fresh for this phase |
| Supabase | Production project, real GoTrue auth for the two disposable e2e accounts (`clario-e2e-customer@example.com`, `clario-e2e-admin@example.com`) |
| Axe rule set | `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa` |

## 4. False-positive color-contrast violations from CSS-animation timing — found, diagnosed, and fixed in the test methodology

The **first** run of the suite reported `color-contrast` violations on `/dashboard` (1 node) and `/admin` (48 nodes), e.g.:

> Element has insufficient color contrast of 1.94 (foreground color: `#404249`, background color: `#0b0c10`, ...). Expected contrast ratio of 4.5:1
> — `<p class="text-xs text-[#8A8F98] mt-0.5">Uptime: 98.5%</p>`

The class on that element (`text-[#8A8F98]`) resolves to a light gray that should pass comfortably — the color axe actually measured (`#404249`) never appears in that class anywhere in the source. That mismatch was the signal this wasn't a real product bug.

**Root cause:** `frontend/src/app/globals.css` defines `.animate-fade-in` as a one-shot 0.3s opacity/transform animation, and several sections in `admin/page.tsx` and `dashboard/page.tsx` apply it with a staggered `animationDelay` up to `0.4s` (e.g. `dashboard/page.tsx`'s footer). The very first test run called `axe.analyze()` immediately after page load/login, before some of these delayed animations had reached their resting opacity of 1 — so axe correctly measured a real (but transient, sub-second) low-contrast frame that no user would perceive as the page's actual state.

**How this was confirmed rather than assumed:** the spec was changed to wait past the animation window (`page.waitForTimeout(1000)`, comfortably past the longest `0.4s` delay + `0.3s` duration = `0.7s`) before scanning, and re-run. Every one of those 49 findings disappeared — 0 `color-contrast` violations on `/dashboard` and `/admin` afterward, with no other code changes. That's the confirmation: if these were real fixed-state color choices, a longer wait would not have changed the result.

**Fix applied:** `frontend/e2e/accessibility.spec.ts` `scan()` now waits 1000ms before invoking axe, with a comment explaining why. This is a fix to the test's methodology, not to the product — the product's resting-state colors were correct all along.

## 5. Real bug found and fixed: login page's decorative background `<iframe>` had no accessible name

After the timing fix above, one genuine violation remained on `/login`:

> `frame-title`: Frames must have an accessible name — `<iframe src="/landing.html?bgOnly=true" class="absolute inset-0 w-full h-full border-none pointer-events-none" style="z-index:0"></iframe>`

`frontend/src/app/login/page.tsx` embeds a purely decorative 3D background animation via an `<iframe>` with no `title`, no `aria-label`, and no `role="presentation"`. A screen reader encountering this page announces an unlabeled, content-less frame to the user — noise with no purpose, since the iframe is `pointer-events-none` and carries no interactive content.

**Fix (`frontend/src/app/login/page.tsx`):** added `title="Decorative background animation"`, `aria-hidden="true"`, and `tabIndex={-1}` to the iframe — `aria-hidden` removes it from the accessibility tree entirely (the correct fix for something purely decorative, rather than giving it a title screen readers would still announce), and `tabIndex={-1}` stops it from being reachable by keyboard `Tab` even though the browser would otherwise let a `Tab` press focus into an iframe's own document regardless of `pointer-events: none` on the outer element.

**Re-verified:** re-ran the full suite after the fix — `/login`'s axe scan reports 0 violations, and the keyboard-navigation test (§6) no longer lands on the iframe at all.

## 6. Keyboard-only navigation (`/login`) — substituting for part of a JAWS pass

axe-core checks DOM/ARIA structure, not runtime keyboard behavior, so a screen-reader/keyboard pass covers a genuinely different failure class (tab order, visible focus, keyboard traps) that no automated DOM scan catches. Since a licensed JAWS install wasn't available in this Linux environment, `accessibility.spec.ts` scripts real `Tab` keypresses across `/login` and asserts every focused element has a visible focus indicator (a non-`none` outline or box-shadow).

This also caught two false positives worth recording as methodology notes, not bugs:
- Before the `/login` iframe fix (§5), `Tab` could land on the iframe itself, which reported no visible focus indicator — resolved as a side effect of making the iframe `tabIndex={-1}` and `aria-hidden`, since it's no longer focusable.
- The Next.js dev server injects its own `nextjs-portal` element (the dev error-overlay indicator), which doesn't exist in a production build. The check now explicitly skips that tag with a comment explaining why — it's a dev-tooling artifact, not part of the shipped page.

**Final result:** all 8 tab stops on `/login` (email field, password field, sign-in button, and further nav links) have a visible focus indicator.

**What this doesn't cover, and would need a real JAWS/NVDA pass to verify:** whether form labels, error messages, and live regions are announced in a sensible order and with sensible wording when actually spoken aloud — the scripted check only verifies focus *lands* somewhere and is *visible*, not what a screen reader says about it. This is a recommended manual follow-up on a Windows machine with a JAWS or NVDA license.

## 7. Observation, fixed by the owning phase: `/agent` had no enforced auth redirect

While reaching `/agent` for its axe scan, `frontend/src/app/agent/page.tsx` was found to have its login-redirect commented out (`// router.push('/login');`), so the page and its mock ticket queue were reachable without authenticating. This is an access-control issue, not an accessibility one, so it was left for the phase that owns this class of finding — **`Testing/05-Security-Access-Control-Testing` fixed and verified it on 2026-09-13 (see that report's §10)**. The `/agent` axe scan below was updated to log in first (as an admin, an authorized role for this page), since visiting `/agent` unauthenticated is no longer this page's real behavior.

## 8. Lighthouse corroboration (public pages)

Lighthouse's accessibility category was run via CLI against the two pages reachable without a login session (its CLI launches a fresh, unauthenticated Chrome instance — driving it through a real Supabase login would need Lighthouse's puppeteer-based user-flow API, not justified here since axe-core already scanned `/dashboard` and `/admin` directly in their real authenticated state):

| Page | Lighthouse accessibility score |
|---|---|
| `/login` | **100 / 100** (after the §5 fix — see `results/lighthouse/login.json`) |
| `/register` | **100 / 100** (`results/lighthouse/register.json`) |

Independent confirmation of §5: Lighthouse also flags `frame-title` for the `/login` iframe when run against the pre-fix code (same underlying axe-core rule, different runner), and reports the page clean at 100/100 after the fix.

## 9. Final verification

```
Running 6 tests using 1 worker

  ✓  login page has no WCAG 2.1 A/AA violations (4.7s)
  ✓  register page has no WCAG 2.1 A/AA violations (3.9s)
  ✓  customer dashboard (authenticated) has no WCAG 2.1 A/AA violations (7.0s)
  ✓  admin console (authenticated) has no WCAG 2.1 A/AA violations (8.0s)
  ✓  agent dashboard has no WCAG 2.1 A/AA violations (4.5s)
  ✓  login page is fully keyboard-operable with visible focus (4.1s)

  6 passed (37.6s)
```

Full raw output: `test-log.txt`. Per-page axe results (final clean run): `results/axe/*.json`. Lighthouse results: `results/lighthouse/*.json`.

The existing `frontend/e2e/auth.spec.ts` suite (5 tests) was re-run after the `/login` fix to confirm no regression to the real login flow — all 5 still pass.

## 10. Recommended follow-up (not done in this phase)

- A real manual pass with JAWS or NVDA on `/login`, `/register`, `/dashboard`, and `/admin`, focused on what §6 can't verify: announcement order and wording, not just focus visibility.
- Extending axe coverage to the `/agent/[ticketId]` detail route and the ticket-submission modal once decided how to reach them without the Java backend services running.
