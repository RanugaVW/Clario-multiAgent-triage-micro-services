# 05 — Security & Access Control Testing (Planned)

**Status:** Not yet executed.

**Sample-plan equivalent:** §3.1.6 Security and Access Control Testing.

**Scope for Clario:** verify Supabase Row Level Security policies actually
restrict customers to their own tickets and staff/admin routes to staff
accounts; verify service-role API routes (e.g.
`frontend/src/app/api/customer_feedback/route.ts`, `user_tickets`) enforce
ownership in application code where RLS is bypassed by the service-role
client; verify PII redaction (`mask_pii` / `mask_pii_reversible`) never
leaks unredacted customer text to the judge LLM or ChromaDB, including on
the cache-hit path where `surrogate_node` is skipped.
