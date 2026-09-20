import { NextResponse } from 'next/server';
import { requireUser } from '../../../../lib/apiAuth';
import { createServiceClient, type ServiceClient } from '../../../../lib/serviceClient';
import { fetchAllPages } from '../../../../lib/reportData';
import { banDurationFor, validateChange, type AccountStatus, type ManagedUser, type Role } from '../../../../lib/userManagement';

// FR-042 (role management) and FR-043 (account status management). Administrator only.

const SCHEMA_HINT = 'Account status is not set up in the database yet. Run supabase_user_management.sql in the Supabase SQL Editor.';

function log(fields: Record<string, unknown>, failed = false) {
  (failed ? console.error : console.info)(JSON.stringify({ event: 'admin.user_change', at: new Date().toISOString(), ...fields }));
}

async function authorize(request: Request) {
  const user = await requireUser(request);
  if (!user) return { error: NextResponse.json({ error: 'Authentication required' }, { status: 401 }) } as const;
  if (user.role !== 'admin') return { error: NextResponse.json({ error: 'Administrator access required' }, { status: 403 }) } as const;
  return { user } as const;
}

const missingSchema = (message: string | undefined) => !!message && /status/i.test(message) && /(column|schema)/i.test(message);

export async function GET(request: Request) {
  const auth = await authorize(request);
  if (auth.error) return auth.error;
  const client = createServiceClient();
  if (!client) return NextResponse.json({ error: 'SUPABASE_SERVICE_ROLE_KEY is not set on the server' }, { status: 500 });

  try {
    const users = await fetchAllPages<ManagedUser>((from, to) =>
      client.from('users').select('id, email, role, status, created_at').order('email', { ascending: true }).range(from, to) as never
    );
    return NextResponse.json({ data: users });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    if (missingSchema(message)) return NextResponse.json({ error: SCHEMA_HINT }, { status: 503 });
    console.error('user list failed', e);
    return NextResponse.json({ error: 'Could not load users' }, { status: 500 });
  }
}

export async function PATCH(request: Request) {
  const auth = await authorize(request);
  if (auth.error) return auth.error;
  const actor = auth.user;
  const client = createServiceClient();
  if (!client) return NextResponse.json({ error: 'SUPABASE_SERVICE_ROLE_KEY is not set on the server' }, { status: 500 });

  let body: Record<string, unknown>;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Request body must be valid JSON' }, { status: 400 });
  }

  // Look the target up first: validation needs its current values, and a bad request must write nothing.
  let target: ManagedUser | null = null;
  if (typeof body.id === 'string' && body.id) {
    const { data, error } = await client.from('users').select('id, email, role, status').eq('id', body.id).maybeSingle();
    if (error) {
      if (missingSchema(error.message)) return NextResponse.json({ error: SCHEMA_HINT }, { status: 503 });
      return NextResponse.json({ error: 'Could not load the user' }, { status: 500 });
    }
    target = (data as ManagedUser | null) ?? null;
  }

  const verdict = validateChange(actor.id, body, target);
  if (!verdict.ok) {
    log({ outcome: 'rejected', actorId: actor.id, targetId: body.id, reason: verdict.error }, true);
    return NextResponse.json({ error: verdict.error }, { status: verdict.httpStatus });
  }
  const { change } = verdict;
  const before = target as ManagedUser;

  const restore = () => rollback(client, before, change.status !== undefined);
  const update: Record<string, unknown> = { updated_at: new Date().toISOString() };
  if (change.role) update.role = change.role;
  if (change.status) update.status = change.status;

  const { error: updateError } = await client.from('users').update(update).eq('id', before.id);
  if (updateError) {
    log({ outcome: 'failure', step: 'update', actorId: actor.id, targetId: before.id, error: updateError.message }, true);
    return NextResponse.json({ error: 'Could not update the user' }, { status: 500 });
  }

  // FR-043: "suspended users cannot authenticate" is enforced by Supabase Auth itself - a banned user cannot sign in
  // or refresh a session. (requireUser additionally rejects still-valid tokens of a non-active account.)
  if (change.status) {
    const { error: banError } = await client.auth.admin.updateUserById(before.id, { ban_duration: banDurationFor(change.status) });
    if (banError) {
      await restore();
      log({ outcome: 'failure', step: 'auth-ban', actorId: actor.id, targetId: before.id, error: banError.message }, true);
      return NextResponse.json({ error: 'Could not update sign-in access for this account; nothing was changed' }, { status: 502 });
    }
  }

  // FR-042/043: every change is auditable. If the audit row cannot be written the change is undone - an unaudited
  // permission change is worse than a failed one.
  const rows: { actor_id: string; target_user_id: string; action: string; old_value: string; new_value: string }[] = [];
  if (change.role) rows.push({ actor_id: actor.id, target_user_id: before.id, action: 'role_change', old_value: before.role, new_value: change.role });
  if (change.status) rows.push({ actor_id: actor.id, target_user_id: before.id, action: 'status_change', old_value: before.status, new_value: change.status });
  const { error: auditError } = await client.from('admin_audit_log').insert(rows);
  if (auditError) {
    await restore();
    log({ outcome: 'failure', step: 'audit', actorId: actor.id, targetId: before.id, error: auditError.message }, true);
    return NextResponse.json({ error: 'The change could not be recorded in the audit log; nothing was changed' }, { status: 500 });
  }

  log({ outcome: 'success', actorId: actor.id, targetId: before.id, role: change.role ?? null, status: change.status ?? null, from: { role: before.role, status: before.status } });
  return NextResponse.json({ user: { ...before, ...(change.role ? { role: change.role as Role } : {}), ...(change.status ? { status: change.status as AccountStatus } : {}) } });
}

// Best effort: put the row (and the Auth ban) back exactly as they were.
async function rollback(client: ServiceClient, before: ManagedUser, statusTouched: boolean) {
  try {
    await client.from('users').update({ role: before.role, status: before.status, updated_at: new Date().toISOString() }).eq('id', before.id);
    if (statusTouched) await client.auth.admin.updateUserById(before.id, { ban_duration: banDurationFor(before.status) });
  } catch (e) {
    console.error(JSON.stringify({ event: 'admin.user_change', outcome: 'rollback-failed', targetId: before.id, error: e instanceof Error ? e.message : String(e) }));
  }
}
