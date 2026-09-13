# 13 — Accessibility Testing (WCAG 2.1 A/AA)

**Status:** Complete — see [`TEST_REPORT.md`](TEST_REPORT.md) (1 real bug found, fixed & re-verified: 6/6).

**Assigned-table mapping:** Basic Accessibility Testing (JAWS, color-contrast
checker, axe DevTools, Google Lighthouse — the tool set the course handed
out for this phase). None of these map to a section of the reference Master
Test Plan (`docs/Sample test plan report.pdf`), which predates WCAG
requirements being a standard phase — this folder follows the repo's
phase-folder convention purely for consistency with 01–12.

## Scope

Automated WCAG 2.1 A/AA scans of all 5 real pages in the frontend
(`/login`, `/register`, `/dashboard`, `/admin`, `/agent`), run against the
live `next dev` server and, for the two auth-gated pages, real
Supabase-authenticated sessions created via this repo's existing
`frontend/e2e` fixtures — no mocking, no static HTML snapshots.

## Why axe-core (`@axe-core/playwright`) + Lighthouse, not WAVE or manual axe DevTools

- **axe-core** is the engine behind both axe DevTools *and* Lighthouse's own
  accessibility category — running it programmatically via
  `@axe-core/playwright` gets the same rule coverage as the axe DevTools
  browser extension, but scriptable, re-runnable, and able to log in as a
  real user first (the browser-extension workflow can only inspect
  whatever's on screen in one tab at a time and can't drive a login flow).
- It plugs directly into the Playwright suite this repo already has
  (`frontend/e2e`, see `Testing/03-UI-E2E-Testing`), so it reuses the real
  auth fixtures instead of needing a separate manual login per page.
- **Lighthouse CLI** was run as a second, independently-implemented
  ruleset against the two public pages, for corroboration and a numeric
  accessibility score.
- **WAVE** wasn't used — it's another browser-extension tool with materially
  the same rule coverage as axe DevTools/axe-core for one-tab-at-a-time
  manual inspection; it adds no automatable, authenticated-session
  capability that axe-core doesn't already provide.
- **JAWS** is a licensed, Windows-only screen reader — unavailable on this
  Linux environment, so it was **not** run. See `TEST_REPORT.md` §6 for
  what was substituted (scripted keyboard-only navigation) and what a real
  JAWS/NVDA pass would still add.
- A manual **color-contrast checker** pass wasn't run separately — axe's
  `color-contrast` rule already implements the same WCAG contrast-ratio
  math and checks every visible text/background pair on the page, which is
  broader coverage than a human spot-checking colors one at a time.

## How to run this

Requires the frontend dev server running (`cd frontend && npm run dev`) and
`frontend/.env.local` populated (real Supabase project — same fixtures
`Testing/03-UI-E2E-Testing` uses).

```bash
cd frontend
npx playwright test e2e/accessibility.spec.ts --project=chromium
```

Lighthouse (public pages only — see `TEST_REPORT.md` §5 for why
authenticated pages aren't run this way):

```bash
npx lighthouse http://localhost:3000/login --only-categories=accessibility \
  --output=json --output-path=login.json --chrome-flags="--headless=new --no-sandbox"
```

## Files in this folder

| File | What it is |
|---|---|
| `accessibility.spec.ts` | Copy of `frontend/e2e/accessibility.spec.ts` — the 6 real Playwright + axe-core scenarios |
| `TEST_REPORT.md` | Findings, the real bug fixed, and two false-positive pitfalls hit and resolved along the way |
| `test-log.txt` | Raw `playwright test` output from the final, all-passing run |
| `results/axe/*.json` | Full axe-core results per page (final, clean run) |
| `results/lighthouse/*.json` | Full Lighthouse accessibility-category results for the two public pages |
