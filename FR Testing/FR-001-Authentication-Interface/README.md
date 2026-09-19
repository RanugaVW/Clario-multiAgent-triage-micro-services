# FR-001 (UI half) — Authentication Interface, SRS §3.9.1

**Status before:** 🟡 Partial — the login form lacked two components the SRS lists as **required**: a *Forgot Password option* and a *Password visibility toggle*.
**Status after:** ✅ Both implemented, with the two pages that make "Forgot password" actually work.

(Authentication itself remains delegated to Supabase Auth — an accepted architecture decision. This item is the *interface* the SRS specifies.)

## ⚠️ One manual Supabase step (dashboard setting, no SQL)

The recovery email's link must return to this app. In **Supabase → Authentication → URL Configuration → Redirect URLs**,
add the deployed origin's reset page, e.g.:

```
http://localhost:3000/reset-password
https://<your-production-host>/reset-password
```

Without it Supabase ignores `redirectTo` and sends users to the Site URL, so the link would not reach `/reset-password`.
The default "Reset Password" email template needs no change.

## What changed (`frontend`)

- **`PasswordInput`** (`components/ui.tsx`): a password field with a show/hide toggle. The toggle is a real
  `<button type="button">` — focusable and operable with Enter/Space, exposes `aria-label` ("Show password"/"Hide password")
  and `aria-pressed`, hides its decorative icon from screen readers, and cannot submit the surrounding form.
  Used on login, register and the reset page (both fields).
- **Login:** "Forgot password?" link → `/forgot-password`. (Removed the input's own `pr-4`, which would have fought the
  toggle's padding — Tailwind resolves conflicts by CSS order, not attribute order.)
- **`/forgot-password`:** email form → `supabase.auth.resetPasswordForEmail` with `redirectTo = <origin>/reset-password`.
  The confirmation is **identical whether or not the address has an account** (no account enumeration) and never echoes the
  address. Service errors (e.g. rate limiting) are shown in an `alert` and the form stays usable.
- **`/reset-password`:** landing page for the emailed link. It shows the form **only** when Supabase reports a recovery
  session (`PASSWORD_RECOVERY`, or an existing session); with no session it says the link is invalid or expired and links to
  request a new one, instead of showing a form that cannot work. Enforces the same 6-character minimum as registration and a
  matching confirmation *before* calling Supabase; on success it signs the temporary recovery session out and points to sign-in.
  Unsubscribes from auth events on unmount.

## Tests

| File | Cases |
|---|---|
| `password-input.test.tsx` | starts hidden and toggles; announces state (`aria-pressed`); operable by keyboard alone (Tab, Enter, Space); **never submits the surrounding form**; typing passes through |
| `auth.test.tsx` (login) | Forgot-password link target; toggle reveals the password without submitting |
| `register-accessibility.test.tsx` | register form offers the toggle |
| `forgot-password.test.tsx` (5) | calls Supabase with the right `redirectTo`; neutral confirmation, no address echoed; service error shown and form still usable; email required; link back to sign-in |
| `reset-password.test.tsx` (10) | invalid state with no session; neutral "verifying" state; form on recovery; a trailing `INITIAL_SESSION(null)` doesn't override a recovery; too-short and mismatched passwords **never reach Supabase**; success updates, signs out, links to sign-in; service error keeps the form; both fields have toggles; unsubscribes on unmount |

**Mutation checks** (reverted): making the toggle `type="submit"` fails the "never submits" test; disabling the mismatch check
fails "refuses mismatched passwords".

```
vitest:        24 files, 166 tests passed (143 before this item + 23 new)
eslint:        0 errors (2 pre-existing <img> warnings)
tsc --noEmit:  only the pre-existing, unrelated error in admin-ticket-attachment.test.tsx
next build:    succeeds; /forgot-password and /reset-password are registered routes
```

## What's still open

- **Not exercised against real Supabase.** Tests mock the client; the actual email delivery and the recovery-session event
  sequence can only be confirmed with the dashboard setting above and a real inbox — worth one manual pass.
- **The SRS's Profile interface** (change password while signed in, edit details, preferences, session info) is still not built.
- No password-strength meter; the rule is Supabase's / the 6-character minimum already used at registration.
