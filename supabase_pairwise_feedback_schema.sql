-- ============================================================================
-- CLARIO PAIRWISE JUDGE + CUSTOMER FEEDBACK - SUPABASE SCHEMA ADDITIONS
-- ============================================================================
-- This migration adds tables for the offline pairwise-preference judge
-- (compares generated drafts against real human responses from an external
-- dataset) and for customer-submitted response ratings.
-- Run this in Supabase SQL Editor after the base schema and
-- supabase_response_validation_schema.sql.
-- See docs/superpowers/specs/2026-09-03-pairwise-judge-and-customer-
-- feedback-design.md for the full design rationale.
-- ============================================================================

-- ============================================================================
-- 1. PAIRWISE EVALUATIONS
-- ============================================================================
-- Self-contained: NOT a foreign key to tickets. Each row describes a
-- historical/replayed ticket from an external dataset (e.g. Rysera LMS
-- exports) compared against a freshly generated draft - not a live ticket.
CREATE TABLE public.pairwise_evaluations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    eval_run_id TEXT NOT NULL,          -- groups all rows from one script invocation
    source_doc_id TEXT NOT NULL,        -- source row's own identifier, for traceability

    category VARCHAR(100),
    domain VARCHAR(50),
    priority VARCHAR(50),
    source_url TEXT,

    ticket_text TEXT NOT NULL,          -- redacted
    generated_draft TEXT NOT NULL,      -- pre-resolve draft, no real PII
    reference_response TEXT NOT NULL,   -- real response, redacted

    winner_pass1 VARCHAR(20) NOT NULL CHECK (winner_pass1 IN ('draft', 'reference', 'tie')),
    winner_pass2 VARCHAR(20) NOT NULL CHECK (winner_pass2 IN ('draft', 'reference', 'tie')),
    reasoning_pass1 TEXT,
    reasoning_pass2 TEXT,
    final_winner VARCHAR(20) NOT NULL CHECK (final_winner IN ('draft', 'reference', 'tie')),

    absolute_overall_score SMALLINT CHECK (absolute_overall_score BETWEEN 1 AND 5),
    judge_model VARCHAR(100) NOT NULL,
    evaluation_latency_ms INTEGER,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_pairwise_evaluations_run ON public.pairwise_evaluations(eval_run_id);
CREATE INDEX idx_pairwise_evaluations_category ON public.pairwise_evaluations(category);

ALTER TABLE public.pairwise_evaluations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Staff can view all pairwise evaluations" ON public.pairwise_evaluations
    FOR SELECT USING (
        (SELECT role FROM public.users WHERE id = auth.uid()) IN ('admin', 'agent')
    );

CREATE POLICY "System can insert pairwise evaluations" ON public.pairwise_evaluations
    FOR INSERT WITH CHECK (true);  -- Service role bypasses RLS


-- ============================================================================
-- 2. CUSTOMER FEEDBACK
-- ============================================================================
-- One row per ticket - a customer can change their rating before leaving
-- the page, but only the latest value persists (upsert on ticket_id, not
-- an append-only log like evaluation_score_overrides).
CREATE TABLE public.customer_feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id UUID NOT NULL REFERENCES public.tickets(id) ON DELETE CASCADE,
    score SMALLINT NOT NULL CHECK (score BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (ticket_id)
);

ALTER TABLE public.customer_feedback ENABLE ROW LEVEL SECURITY;

-- Customers can view their own feedback.
CREATE POLICY "Customers view own feedback" ON public.customer_feedback
    FOR SELECT USING (
        ticket_id IN (SELECT id FROM public.tickets WHERE user_id = auth.uid())
    );

-- Staff can view all feedback (for the admin dashboard badge).
CREATE POLICY "Staff can view all feedback" ON public.customer_feedback
    FOR SELECT USING (
        (SELECT role FROM public.users WHERE id = auth.uid()) IN ('admin', 'agent')
    );

-- No customer-facing direct-client INSERT/UPDATE policy: writes go through
-- the service-role API route (frontend/src/app/api/customer_feedback/route.ts),
-- which validates ticket ownership in application code the same way
-- api/user_tickets/route.ts already scopes its GET by userId.
