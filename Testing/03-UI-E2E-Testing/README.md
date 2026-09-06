# 03 — UI / End-to-End Testing

**Status:** Complete — see [`TEST_REPORT.md`](TEST_REPORT.md). 9/9 automated
checks passed, 0 skipped, 0 failed. Two real bugs (a production RLS policy
gap, and a PostgREST relationship-shape bug that broke the star-rating
widget's persistence) were found, fixed, and re-verified live.

**Sample-plan equivalent:** §3.1.3 User Interface Testing.

**Scope for Clario:** browser-driven testing of the customer dashboard
(login, ticket submission, resolution view, 1-5 feedback rating) and the
admin console (ticket search, requester/pipeline/judge data rendering),
covering navigation, form submission, and rendering correctness, against
the real running app, real backend chain, and real production Supabase
project — no mocks. The sample plan's tool (Selenium IDE) targets a legacy
PHP app; for this Next.js app the equivalent used is
[Playwright](https://playwright.dev/) (`frontend/e2e/`), run via `npm run
test:e2e` in `frontend/`.
