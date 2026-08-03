# Clario Frontend & Backend Development Log

## Phase 1: Next.js UI Implementation
**What we did:** 
Built a premium, Next.js 15 App-Router based UI for the Clario platform, strictly adhering to the `SOFTWARE_ARCHITECTURE_DOCUMENT.md`. This included:
1. **Customer Portal (`/`)**: A glassmorphism-themed ticket submission form. Users are routed here upon login if they are standard customers.
2. **Agent Dashboard (`/agent`)**: An internal queue for human support agents to review escalated tickets.
3. **Admin Dashboard (`/admin`)**: A live system-monitoring view. Support Staff (emails containing "admin" or "agent") are routed here automatically upon login.
4. **Auth Context & Registration**: Supabase JWT authentication wrapping the application with self-service registration and email confirmation configured.

**How we did it:** 
We leveraged Next.js App Router and a custom highly polished Vanilla CSS / Tailwind UI rather than relying on standard cookie-cutter libraries like SHADCN. While SHADCN is widely used and excellent for standard dashboards, we opted for a bespoke Glassmorphism theme layered directly on Tailwind CSS (`globals.css`) because the project demanded a "wow factor" and premium aesthetic that goes beyond standard library defaults. 

**Advantage of this approach:** 
- **Security:** The UI acts only as a dumb client. All database transactions happen behind the Spring Boot gateway, preventing exposure of DB queries in the browser.
- **Aesthetics:** The bespoke styling delivers the requested premium feel while maintaining the lightweight performance of Tailwind CSS utilities.

---

## Phase 2: Supabase & Spring Boot Integration
**What we did:** 
Wired the newly built Next.js UI and the Spring Boot API Gateway directly into the Supabase managed PostgreSQL instance.

**How we did it:**
1. **API Keys:** Migrated the `SUPABASE_PUBLIC_API` and `PROJECT_ID` keys from the ML Sidecar's `.env` into `frontend/.env.local` to enable secure JWT session management in Next.js via `@supabase/supabase-js`.
2. **Spring Boot Config:** Created `application.properties` in the Spring Boot backend (`clario-app`), configuring it to connect to Supabase via standard PostgreSQL JDBC using the master database password.
3. **Database Schema:** Drafted a complete `supabase_schema.sql` script to initialize the `tickets` and `handoff_packages` tables with proper UUID primary keys and a `version` column for JPA optimistic locking.

**Advantage of this approach:**
- **Hybrid Monolith Synergy:** Next.js handles JWT authentication gracefully, while Spring Boot leverages Hibernate/JPA to manage complex database transactions and optimistic locking without having to manually write raw SQL. Supabase serves both platforms seamlessly.
