-- ============================================================================
-- CLARIO RESPONSE VALIDATION SYSTEM - SUPABASE SCHEMA ADDITIONS
-- ============================================================================
-- This migration adds tables for LLM judge scoring of draft responses,
-- admin score overrides with audit trail, and a view for effective scores.
-- Run this in Supabase SQL Editor after the base schema.
-- ============================================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- 1. RESPONSE EVALUATIONS (Judge LLM Scores)
-- ============================================================================
-- Stores the structured evaluation from the judge LLM (Gemini/GPT) for each draft.
-- One row per draft per domain (technical/billing).
CREATE TABLE public.response_evaluations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id UUID REFERENCES public.tickets(id) ON DELETE CASCADE,
    draft_id UUID REFERENCES public.ticket_drafts(id) ON DELETE CASCADE,
    domain VARCHAR(100) NOT NULL,

    -- Judge Model Metadata
    judge_model VARCHAR(100) NOT NULL,           -- e.g., 'gemini-2.5-pro', 'gpt-5.6-luna'
    judge_version VARCHAR(50),                   -- Model version/timestamp for reproducibility

    -- Overall Score (1-5)
    overall_score SMALLINT NOT NULL CHECK (overall_score BETWEEN 1 AND 5),

    -- Dimension Scores (1-5 each)
    priority_tone_match_score SMALLINT NOT NULL CHECK (priority_tone_match_score BETWEEN 1 AND 5),
    completeness_score SMALLINT NOT NULL CHECK (completeness_score BETWEEN 1 AND 5),
    accuracy_score SMALLINT NOT NULL CHECK (accuracy_score BETWEEN 1 AND 5),
    policy_compliance_score SMALLINT NOT NULL CHECK (policy_compliance_score BETWEEN 1 AND 5),
    groundedness_score SMALLINT NOT NULL CHECK (groundedness_score BETWEEN 1 AND 5),

    -- Judge Reasoning & Suggestions (JSON for flexibility)
    judge_reasoning TEXT,
    improvement_suggestions JSONB,               -- Array of specific actionable suggestions
    required_phrases_present JSONB,              -- Required phrases found in draft
    required_phrases_missing JSONB,              -- Required phrases missing from draft
    forbidden_phrases_found JSONB,               -- Any forbidden phrases detected

    -- Context at Evaluation Time
    priority_at_evaluation VARCHAR(50),          -- Ticket priority when judged (Urgent/Critical/High/Medium/Low)
    category_at_evaluation VARCHAR(100),         -- Ticket category when judged

    -- Performance
    evaluation_latency_ms INTEGER,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX idx_response_evaluations_ticket ON public.response_evaluations(ticket_id);
CREATE INDEX idx_response_evaluations_draft ON public.response_evaluations(draft_id);
CREATE INDEX idx_response_evaluations_domain ON public.response_evaluations(domain);
CREATE INDEX idx_response_evaluations_score ON public.response_evaluations(overall_score);
CREATE INDEX idx_response_evaluations_priority ON public.response_evaluations(priority_at_evaluation);
CREATE INDEX idx_response_evaluations_created ON public.response_evaluations(created_at DESC);

-- ============================================================================
-- 2. EVALUATION SCORE OVERRIDES (Admin Edits with Audit Trail)
-- ============================================================================
-- Records every admin modification to judge scores with full history.
-- Immutable append-only log for compliance and model improvement tracking.
CREATE TABLE public.evaluation_score_overrides (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    evaluation_id UUID REFERENCES public.response_evaluations(id) ON DELETE CASCADE,
    admin_id UUID REFERENCES public.users(id) ON DELETE SET NULL,

    -- Override Values (NULL = not overridden, keeps judge score)
    -- Only include fields the admin actually changed
    overall_score SMALLINT CHECK (overall_score BETWEEN 1 AND 5),
    priority_tone_match_score SMALLINT CHECK (priority_tone_match_score BETWEEN 1 AND 5),
    completeness_score SMALLINT CHECK (completeness_score BETWEEN 1 AND 5),
    accuracy_score SMALLINT CHECK (accuracy_score BETWEEN 1 AND 5),
    policy_compliance_score SMALLINT CHECK (policy_compliance_score BETWEEN 1 AND 5),
    groundedness_score SMALLINT CHECK (groundedness_score BETWEEN 1 AND 5),

    -- Required: Human justification for override
    override_reason TEXT NOT NULL,

    -- Audit: Snapshot of judge scores at time of override
    previous_scores JSONB NOT NULL,

    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_evaluation_overrides_eval ON public.evaluation_score_overrides(evaluation_id);
CREATE INDEX idx_evaluation_overrides_admin ON public.evaluation_score_overrides(admin_id);
CREATE INDEX idx_evaluation_overrides_created ON public.evaluation_score_overrides(created_at DESC);

-- ============================================================================
-- 3. VIEW: EFFECTIVE EVALUATION SCORES (Judge + Admin Override)
-- ============================================================================
-- Single source of truth: merges judge scores with latest admin override.
-- Use this view for all dashboards, analytics, and downstream consumers.
CREATE VIEW public.effective_evaluation_scores AS
SELECT
    e.id AS evaluation_id,
    e.ticket_id,
    e.draft_id,
    e.domain,
    e.judge_model,
    e.judge_version,

    -- Effective Scores (COALESCE: override takes precedence)
    COALESCE(o.overall_score, e.overall_score) AS effective_overall_score,
    COALESCE(o.priority_tone_match_score, e.priority_tone_match_score) AS effective_priority_tone_score,
    COALESCE(o.completeness_score, e.completeness_score) AS effective_completeness_score,
    COALESCE(o.accuracy_score, e.accuracy_score) AS effective_accuracy_score,
    COALESCE(o.policy_compliance_score, e.policy_compliance_score) AS effective_policy_score,
    COALESCE(o.groundedness_score, e.groundedness_score) AS effective_groundedness_score,

    -- Override Metadata
    CASE WHEN o.id IS NOT NULL THEN true ELSE false END AS has_admin_override,
    o.id AS override_id,
    o.admin_id AS override_admin_id,
    o.override_reason,
    o.created_at AS override_at,
    o.previous_scores AS judge_scores_before_override,

    -- Judge Output
    e.judge_reasoning,
    e.improvement_suggestions,
    e.required_phrases_present,
    e.required_phrases_missing,
    e.forbidden_phrases_found,
    e.priority_at_evaluation,
    e.category_at_evaluation,
    e.evaluation_latency_ms,
    e.created_at AS judge_evaluated_at
FROM public.response_evaluations e
LEFT JOIN LATERAL (
    -- Get the LATEST override for this evaluation (if any)
    SELECT * FROM public.evaluation_score_overrides
    WHERE evaluation_id = e.id
    ORDER BY created_at DESC
    LIMIT 1
) o ON true;

-- ============================================================================
-- 4. ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================

ALTER TABLE public.response_evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluation_score_overrides ENABLE ROW LEVEL SECURITY;

-- Admins/Agents can view all evaluations
CREATE POLICY "Staff can view all evaluations" ON public.response_evaluations
    FOR SELECT USING (
        (SELECT role FROM public.users WHERE id = auth.uid()) IN ('admin', 'agent')
    );

-- Admins/Agents can insert evaluations (system writes via service role)
CREATE POLICY "System can insert evaluations" ON public.response_evaluations
    FOR INSERT WITH CHECK (true);  -- Service role bypasses RLS

-- Admins/Agents can view all overrides
CREATE POLICY "Staff can view all overrides" ON public.evaluation_score_overrides
    FOR SELECT USING (
        (SELECT role FROM public.users WHERE id = auth.uid()) IN ('admin', 'agent')
    );

-- Admins/Agents can create overrides
CREATE POLICY "Staff can create overrides" ON public.evaluation_score_overrides
    FOR INSERT WITH CHECK (
        (SELECT role FROM public.users WHERE id = auth.uid()) IN ('admin', 'agent')
    );

-- No UPDATE/DELETE on overrides (immutable audit log)
-- Service role can insert evaluations (handled by FastAPI service role key)

-- ============================================================================
-- 5. HELPER FUNCTION: Get Effective Score for a Ticket
-- ============================================================================
CREATE OR REPLACE FUNCTION public.get_ticket_effective_scores(p_ticket_id UUID)
RETURNS TABLE (
    evaluation_id UUID,
    domain VARCHAR,
    judge_model VARCHAR,
    effective_overall_score SMALLINT,
    effective_priority_tone_score SMALLINT,
    effective_completeness_score SMALLINT,
    effective_accuracy_score SMALLINT,
    effective_policy_score SMALLINT,
    effective_groundedness_score SMALLINT,
    has_admin_override BOOLEAN,
    override_admin_id UUID,
    override_reason TEXT,
    judge_reasoning TEXT,
    improvement_suggestions JSONB,
    priority_at_evaluation VARCHAR,
    judge_evaluated_at TIMESTAMPTZ
) LANGUAGE sql SECURITY DEFINER AS $$
    SELECT
        evaluation_id,
        domain,
        judge_model,
        effective_overall_score,
        effective_priority_tone_score,
        effective_completeness_score,
        effective_accuracy_score,
        effective_policy_score,
        effective_groundedness_score,
        has_admin_override,
        override_admin_id,
        override_reason,
        judge_reasoning,
        improvement_suggestions,
        priority_at_evaluation,
        judge_evaluated_at
    FROM public.effective_evaluation_scores
    WHERE ticket_id = p_ticket_id
    ORDER BY judge_evaluated_at DESC;
$$;

-- Grant execute to authenticated roles
GRANT EXECUTE ON FUNCTION public.get_ticket_effective_scores(UUID) TO authenticated;

-- ============================================================================
-- 6. TRIGGER: Auto-calculate evaluation stats (optional, for materialized view)
-- ============================================================================
-- If you want a materialized view for dashboard stats, create it separately:
-- CREATE MATERIALIZED VIEW public.evaluation_stats AS
-- SELECT
--     COUNT(*) as total_evaluations,
--     COUNT(*) FILTER (WHERE has_admin_override) as override_count,
--     AVG(effective_overall_score) as avg_overall_score,
--     percentile_cont(0.5) WITHIN GROUP (ORDER BY effective_overall_score) as median_overall_score
-- FROM public.effective_evaluation_scores;
--
-- CREATE UNIQUE INDEX ON public.evaluation_stats (true); -- dummy for refresh
-- REFRESH MATERIALIZED VIEW public.evaluation_stats;