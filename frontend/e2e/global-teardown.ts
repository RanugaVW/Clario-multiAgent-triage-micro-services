import { createClient } from '@supabase/supabase-js';
import { readFileSync, existsSync } from 'fs';
import path from 'path';

const FIXTURES_PATH = path.join(__dirname, '.auth', 'fixtures.json');

/**
 * Deletes every real row this run created (tickets tagged with the run's
 * marker, then both disposable auth users) so the suite leaves no trace in
 * the real Supabase project between runs.
 */
export default async function globalTeardown() {
  if (process.env.E2E_SKIP_TEARDOWN) return; // debugging escape hatch - clean up manually afterward
  if (!existsSync(FIXTURES_PATH)) return;
  const fixtures = JSON.parse(readFileSync(FIXTURES_PATH, 'utf-8'));

  const admin = createClient(fixtures.supabaseUrl, fixtures.serviceRoleKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });

  const { data: tickets } = await admin
    .from('tickets')
    .select('id')
    .eq('user_id', fixtures.customer.id);

  for (const t of tickets ?? []) {
    await admin.from('customer_feedback').delete().eq('ticket_id', t.id);
    await admin.from('tickets').delete().eq('id', t.id); // cascades to classifications/drafts/resolutions/etc.
  }

  await admin.auth.admin.deleteUser(fixtures.customer.id);
  await admin.auth.admin.deleteUser(fixtures.admin.id);
}
