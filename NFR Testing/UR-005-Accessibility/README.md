# UR-005 — Accessibility

**Status before:** 🟡 Partial (weak) — login/register email+password inputs relied on placeholder text only, no `<label>` elements (login), or had visible label text with no `htmlFor`/`id` association to the input (register).
**Status after:** 🟡 Partial → this specific finding is closed; the broader accessibility gap (sparse `aria-*` usage app-wide) remains open.

## What was wrong

- `frontend/src/app/login/page.tsx`: email and password `<input>`s had no `<label>` at all —
  only `placeholder` text, which most screen readers don't reliably announce and which
  disappears the moment the user starts typing.
- `frontend/src/app/register/page.tsx`: **did** have visible `<label>` text ("Email address",
  "Password (min 6 characters)") — the original audit slightly overstated this one — but
  neither label had an `htmlFor` pointing at the input's `id`, so it was just adjacent text,
  not a programmatically associated label. A screen reader wouldn't announce it on focus, and
  clicking the label text wouldn't focus the input.

## What changed

- **Login:** added `sr-only` (visually hidden, screen-reader-only) `<label htmlFor="login-email">`
  / `<label htmlFor="login-password">`, matched to new `id="login-email"` / `id="login-password"`
  on the inputs. No visual change — the placeholder-based design is preserved exactly.
- **Register:** added `htmlFor="register-email"` / `htmlFor="register-password"` to the
  existing visible labels, matched to new `id` props on the `GlassInput` components
  (`GlassInput` already spread `...rest` onto the native `<input>`, so `id` passes through
  with no component change needed).

## No Supabase changes needed.

## Tests

- `frontend/src/app/__tests__/auth.test.tsx` — new test
  `associates an accessible label with the email and password inputs`, using
  `screen.getByLabelText(...)` (Testing Library resolves this via the label/input
  association — it fails if the association is missing, which is exactly what the old
  markup would have done).
- `frontend/src/app/__tests__/register-accessibility.test.tsx` — new file, same technique
  for the register page's two fields.

```
npx vitest run src/app/__tests__/auth.test.tsx src/app/__tests__/register-accessibility.test.tsx
Test Files  2 passed (2)
     Tests  6 passed (6)

npx vitest run   (full suite, regression check)
Test Files  17 passed (17)
     Tests  116 passed (116)   [114 pre-existing + 2 new]
```

## What UR-005 still doesn't cover

This fix is scoped to the two authentication forms specifically named in the original
finding. The broader observation — "sparse `aria-*` usage" across the rest of the
application (dashboard, admin, agent pages) — is unchanged and remains open.
