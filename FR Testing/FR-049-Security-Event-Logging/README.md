# FR-049 — Security Event Logging (SRS priority: Critical)

**Status before:** 🔴 Not Implemented — a rejected request got a bare 401 and left no record anywhere.
**Status after:** 🟡 Partial → the API-layer half is implemented for all three Java services; login *attempts* themselves are still Supabase's (see "What's still open").

## What was wrong

FR-049 requires authentication, authorization and other security-sensitive events to be written
to an audit log. In `api-gateway`, `ticket-core-service` and `agent-review-service`, a request
with a missing, malformed or forged token was answered by Spring Security's default entry point
and nothing else. Anyone could probe the API and there would be no trace of it.

## What changed

New `SecurityAuditLogger` (one copy per service, `com.clario.config`), wired into each
`SecurityConfig` through the resource server's `authenticationEntryPoint` and
`accessDeniedHandler`. Both wrap the stock `BearerTokenAuthenticationEntryPoint` /
`BearerTokenAccessDeniedHandler`, so the HTTP response (status and `WWW-Authenticate` header) is
byte-for-byte unchanged — only the audit record is new.

Each record goes to a dedicated `security.audit` logger at WARN:

```
event=AUTHENTICATION_FAILURE method=GET path=/api/tickets remote=127.0.0.1 reason="InvalidBearerTokenException: ..."
event=ACCESS_DENIED method=DELETE path=/api/tickets/42 remote=10.1.2.3 principal=anonymous reason="AccessDeniedException"
```

Design decisions worth knowing:

- **Credentials are never logged.** The `Authorization` header is deliberately not read, and a
  test asserts a distinctive fake token does not appear in the record.
- **Log-injection resistant.** Path and exception text are attacker-influenced; CR/LF/tab/quote
  are replaced and fields are truncated at 200 chars, so a crafted URL cannot forge a second
  `event=ACCESS_GRANTED` line.
- **Separate logger name** so it can be routed or alerted on independently of application logs
  (SEC-011 builds on this).

## No Supabase changes needed.

## Tests (run with `.env` hidden and Redis unreachable, matching CI)

| Test | Verifies |
|---|---|
| `missingToken_isRejectedAndRecorded` | 401 still returned with `WWW-Authenticate`; exactly one `AUTHENTICATION_FAILURE` record with method + path, at WARN |
| `invalidToken_isRecorded_withoutLeakingTheCredential` | Malformed token → 401, one record, token text absent |
| `validToken_producesNoAuditFailure` | A legitimate request produces no failure record |
| `accessDenied_isRecordedWithThePrincipal` | 403 path records `ACCESS_DENIED` with remote address and principal |
| `attackerControlledValues_cannotForgeAdditionalLogLines` | Newlines in path/message are neutralised (one record, no `\n`) |
| `sanitize_truncatesOversizedValues` | 5000-char value is capped |
| `api-gateway`: missing token / invalid token / health-not-audited | Same guarantees against the real edge service over HTTP |

```
api-gateway:           Tests run: 11, Failures: 0, Errors: 0 -- BUILD SUCCESS
agent-review-service:  Tests run: 17, Failures: 0, Errors: 0 -- BUILD SUCCESS
ticket-core-service:   Tests run: 20, Failures: 0, Errors: 0 -- BUILD SUCCESS
```

## What's still open

- **Login attempts** ("Login attempts are recorded") happen inside Supabase Auth, not this
  codebase. Supabase keeps its own auth logs; nothing here can record them.
- Records go to the log stream only. A queryable, tamper-protected audit *table* (FR-046)
  would need a new Supabase table — not created here.
- Successful authenticated requests are intentionally not logged (volume); only failures.
