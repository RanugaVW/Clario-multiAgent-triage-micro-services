-- ============================================================================
-- CLARIO USER MANAGEMENT - ACCOUNT STATUS + ADMIN AUDIT LOG (FR-042 / FR-043)
-- ============================================================================
-- STATUS: APPLIED by the project owner on 2026-09-20 (reported; verify with the queries in FR Testing/FR-042-043-User-Management/REPORT.md).
-- Idempotent: safe to run more than once.
--
-- The app works with or without this file applied:
--   * before: the Users admin page reports that the schema is missing (503) and every other page is unaffected;
--   * after:  admins can change roles and suspend/reactivate/deactivate accounts, each change audited.
--
-- ROLLBACK:
--   DROP TABLE IF EXISTS public.admin_audit_log;
--   ALTER TABLE public.users DROP COLUMN IF EXISTS status;
-- ============================================================================

-- 1) Account status (FR-043). Existing users become 'active'.
ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'active'
  CHECK (status IN ('active', 'suspended', 'deactivated'));

-- 2) Audit trail for role and status changes (FR-042: "permission updates are logged";
--    FR-043: "status changes are auditable"). Append-only by convention: the app only ever inserts.
CREATE TABLE IF NOT EXISTS public.admin_audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    target_user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL CHECK (action IN ('role_change', 'status_change')),
    old_value VARCHAR(50),
    new_value VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- RLS on with NO policies: anon/authenticated (customers, agents) can neither read nor write it.
-- Only the service role (used by the Next.js admin API after it verifies the caller is an admin) can.
ALTER TABLE public.admin_audit_log ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_admin_audit_target ON public.admin_audit_log (target_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_audit_actor  ON public.admin_audit_log (actor_id, created_at DESC);
