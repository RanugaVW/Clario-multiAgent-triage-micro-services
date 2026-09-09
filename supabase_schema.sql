-- ==========================================
-- Clario System - Complete Supabase Schema
-- Based on Section 9 (Data View ERD) of SOFTWARE_ARCHITECTURE_DOCUMENT.md
-- ==========================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==========================================
-- 1. USERS (Roles & Profiles)
-- Note: Supabase manages authentication in `auth.users`. 
-- This table links to `auth.users` to store role data.
-- ==========================================
CREATE TABLE public.users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    role VARCHAR(50) DEFAULT 'user' CHECK (role IN ('user', 'agent', 'admin')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Trigger to automatically create a public.user profile when someone signs up
CREATE OR REPLACE FUNCTION public.handle_new_user() 
RETURNS trigger AS $$
BEGIN
  INSERT INTO public.users (id, email, role)
  VALUES (
    new.id, 
    new.email, 
    -- Automatically assign admin/agent role based on email domain for Clario staff
    CASE 
      WHEN new.email LIKE '%admin@clario.com%' THEN 'admin'
      WHEN new.email LIKE '%agent@clario.com%' THEN 'agent'
      ELSE 'user'
    END
  );
  RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();


-- ==========================================
-- 2. TICKETS
-- ==========================================
CREATE TABLE public.tickets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    customer_name VARCHAR(255),
    customer_email VARCHAR(255),
    subject VARCHAR(255),
    raw_text TEXT NOT NULL,
    redacted_text TEXT,
    status VARCHAR(50) DEFAULT 'received',
    
    -- Optimistic Locking Column
    version INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);


-- ==========================================
-- 3. TICKET CLASSIFICATIONS
-- ==========================================
CREATE TABLE public.ticket_classifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id UUID REFERENCES public.tickets(id) ON DELETE CASCADE,
    category VARCHAR(100),
    priority VARCHAR(50),
    sentiment VARCHAR(50),
    confidence FLOAT,
    source VARCHAR(100),
    pii_found JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);


-- ==========================================
-- 4. TICKET DRAFTS
-- ==========================================
CREATE TABLE public.ticket_drafts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id UUID REFERENCES public.tickets(id) ON DELETE CASCADE,
    domain VARCHAR(100),
    draft_text TEXT,
    rag_top_score FLOAT,
    low_relevance BOOLEAN DEFAULT FALSE,
    retrieved_sources JSONB,
    reflection_attempt INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);


-- ==========================================
-- 5. TICKET VALIDATIONS
-- ==========================================
CREATE TABLE public.ticket_validations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id UUID REFERENCES public.tickets(id) ON DELETE CASCADE,
    domain VARCHAR(100),
    passed BOOLEAN,
    failed_rules JSONB,
    judge_ran BOOLEAN DEFAULT FALSE,
    on_topic BOOLEAN,
    grounded_in_context BOOLEAN,
    appropriate_tone BOOLEAN,
    judge_reasoning TEXT,
    failure_type VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);


-- ==========================================
-- 6. HUMAN REVIEWS (Handoff Packages)
-- ==========================================
CREATE TABLE public.human_reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id UUID REFERENCES public.tickets(id) ON DELETE CASCADE,
    reviewer_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    original_draft TEXT,
    final_draft TEXT,
    decision VARCHAR(50),
    notes TEXT,
    reviewed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);


-- ==========================================
-- 7. RESOLUTIONS
-- ==========================================
CREATE TABLE public.resolutions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id UUID REFERENCES public.tickets(id) ON DELETE CASCADE,
    final_response TEXT,
    resolved_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    escalated BOOLEAN DEFAULT FALSE,
    escalation_reasons JSONB,
    total_reflection_count INTEGER DEFAULT 0,
    total_llm_calls INTEGER DEFAULT 0,
    total_latency_ms FLOAT,
    resolved_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);


-- ==========================================
-- 8. TICKET LOGS
-- ==========================================
CREATE TABLE public.ticket_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id UUID REFERENCES public.tickets(id) ON DELETE CASCADE,
    stage VARCHAR(100),
    event VARCHAR(255),
    latency_ms FLOAT,
    logged_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);


-- ==========================================
-- 9. ROW LEVEL SECURITY (RLS) POLICIES
-- ==========================================
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.human_reviews ENABLE ROW LEVEL SECURITY;

-- 1. Users can only see their own profile. Admins/Agents can see all.
CREATE POLICY "Users can view own profile" ON public.users 
    FOR SELECT USING (auth.uid() = id OR (SELECT role FROM public.users WHERE id = auth.uid()) IN ('admin', 'agent'));

-- 2. Customers can only see and insert their own tickets.
CREATE POLICY "Customers view own tickets" ON public.tickets 
    FOR SELECT USING (auth.uid() = user_id);
    
CREATE POLICY "Customers can insert tickets" ON public.tickets 
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- 3. Support Staff (Agents/Admins) can view and update ALL tickets
CREATE POLICY "Staff can view all tickets" ON public.tickets 
    FOR SELECT USING ((SELECT role FROM public.users WHERE id = auth.uid()) IN ('admin', 'agent'));

CREATE POLICY "Staff can update tickets" ON public.tickets 
    FOR UPDATE USING ((SELECT role FROM public.users WHERE id = auth.uid()) IN ('admin', 'agent'));
