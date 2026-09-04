import { createClient } from '@supabase/supabase-js';
import { writeFileSync, mkdirSync } from 'fs';
import path from 'path';

/**
 * Creates two disposable, real Supabase auth users for this E2E run - one
 * plain 'user' role (customer flows) and one promoted to 'admin' (admin
 * console flows). Both are created with email_confirm:true via the service
 * role key so no real inbox is ever touched, and both are deleted again in
 * global-teardown.ts. Every ticket this suite submits is tagged with the
 * run's marker so it's unambiguous in the admin console and easy to clean up.
 */

const FIXTURES_DIR = path.join(__dirname, '.auth');
const FIXTURES_PATH = path.join(FIXTURES_DIR, 'fixtures.json');

const CUSTOMER_EMAIL = 'clario-e2e-customer@example.com';
const ADMIN_EMAIL = 'clario-e2e-admin@example.com';
const TEST_PASSWORD = 'ClarioE2E-Test-Pass-2026!';

export default async function globalSetup() {
  process.loadEnvFile(path.join(__dirname, '..', '.env.local'));

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !serviceRoleKey) {
    throw new Error('NEXT_PUBLIC_SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing from .env.local');
  }

  const admin = createClient(url, serviceRoleKey, { auth: { autoRefreshToken: false, persistSession: false } });

  // Idempotent: remove any leftover users from a previous run whose
  // teardown didn't complete (e.g. a crashed run), so this run always
  // starts from a clean slate.
  const { data: existing } = await admin.auth.admin.listUsers({ perPage: 1000 });
  for (const u of existing?.users ?? []) {
    if (u.email === CUSTOMER_EMAIL || u.email === ADMIN_EMAIL) {
      await admin.auth.admin.deleteUser(u.id);
    }
  }

  const { data: customer, error: customerErr } = await admin.auth.admin.createUser({
    email: CUSTOMER_EMAIL,
    password: TEST_PASSWORD,
    email_confirm: true,
  });
  if (customerErr || !customer.user) throw new Error(`Failed to create customer test user: ${customerErr?.message}`);

  const { data: adminUser, error: adminErr } = await admin.auth.admin.createUser({
    email: ADMIN_EMAIL,
    password: TEST_PASSWORD,
    email_confirm: true,
  });
  if (adminErr || !adminUser.user) throw new Error(`Failed to create admin test user: ${adminErr?.message}`);

  // The handle_new_user() trigger inserts every new signup as role='user' -
  // promote the second account to admin directly (service role bypasses RLS).
  const { error: promoteErr } = await admin.from('users').update({ role: 'admin' }).eq('id', adminUser.user.id);
  if (promoteErr) throw new Error(`Failed to promote admin test user: ${promoteErr.message}`);

  const runId = `E2E-${Date.now()}`;

  mkdirSync(FIXTURES_DIR, { recursive: true });
  writeFileSync(FIXTURES_PATH, JSON.stringify({
    runId,
    supabaseUrl: url,
    serviceRoleKey,
    customer: { id: customer.user.id, email: CUSTOMER_EMAIL, password: TEST_PASSWORD },
    admin: { id: adminUser.user.id, email: ADMIN_EMAIL, password: TEST_PASSWORD },
  }, null, 2));
}
