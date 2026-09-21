'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { useAuth } from '../../../contexts/AuthContext';
import { supabase } from '../../../lib/supabase';
import { fetchJson } from '../../../lib/fetchJson';
import { ConfirmDialog } from '../../../components/ui/Modal';
import { Badge } from '../../../components/ui/Badge';
import { Button } from '../../../components/ui/Button';
import { Card } from '../../../components/ui/Card';
import { Notice } from '../../../components/ui/Notice';
import { AdminShell } from '../AdminShell';
import { ROLES, STATUSES, type AccountStatus, type ManagedUser, type Role } from '../../../lib/userManagement';

async function authHeaders(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

const SELECT = 'rounded-lg border border-border-strong bg-surface px-3 py-1.5 text-app text-fg disabled:opacity-50';

const STATUS_TONE = { active: 'success', suspended: 'warning', deactivated: 'danger' } as const;

type Pending = { user: ManagedUser; role?: Role; status?: AccountStatus };

export default function AdminUsers() {
  const { user, role, loading, roleLoading } = useAuth();
  const router = useRouter();
  const ready = !loading && !roleLoading;
  const isAdmin = !!user && role === 'admin';

  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [fetching, setFetching] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: 'ok' | 'error'; text: string } | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<Pending | null>(null);

  useEffect(() => {
    if (ready && !isAdmin) router.push('/login');
  }, [ready, isAdmin, router]);

  const load = useCallback(async () => {
    try {
      const json = await fetchJson<{ data: ManagedUser[] }>('/api/admin/users', { headers: await authHeaders() });
      setUsers(json.data);
      setLoadError(null);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : 'Could not load users');
    } finally {
      setFetching(false);
    }
  }, []);

  useEffect(() => {
    if (isAdmin) queueMicrotask(load);
  }, [isAdmin, load]);

  const apply = async (p: Pending) => {
    setConfirm(null);
    setSavingId(p.user.id);
    setNotice(null);
    try {
      const json = await fetchJson<{ user: ManagedUser }>('/api/admin/users', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
        body: JSON.stringify({ id: p.user.id, role: p.role, status: p.status }),
      });
      setUsers((prev) => prev.map((u) => (u.id === p.user.id ? { ...u, ...json.user } : u)));
      setNotice({ tone: 'ok', text: `Updated ${p.user.email}.` });
    } catch (e) {
      setNotice({ tone: 'error', text: e instanceof Error ? e.message : 'The change could not be saved' });
    } finally {
      setSavingId(null);
    }
  };

  // Loss of access is confirmed explicitly; everything else applies straight away.
  const request = (target: ManagedUser, change: { role?: Role; status?: AccountStatus }) => {
    const p: Pending = { user: target, ...change };
    if (change.status && change.status !== 'active') setConfirm(p);
    else void apply(p);
  };

  if (!ready) {
    return (
      <div className="min-h-dvh flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-brand" />
      </div>
    );
  }

  return (
    <AdminShell active="users">
      <div className="max-w-6xl space-y-6">
        <ConfirmDialog
          open={confirm !== null}
          title={confirm?.status === 'deactivated' ? 'Deactivate this account?' : 'Suspend this account?'}
          message={confirm ? `${confirm.user.email} will be signed out of new sessions and will not be able to sign in until an administrator reactivates the account.` : ''}
          confirmLabel={confirm?.status === 'deactivated' ? 'Deactivate' : 'Suspend'}
          onConfirm={() => confirm && apply(confirm)}
          onCancel={() => setConfirm(null)}
        />

        <header>
          <h1 className="text-h2 text-fg">Users</h1>
          <p className="text-app text-fg-muted">Change roles and manage account access. Every change is recorded in the audit log.</p>
        </header>

        {notice && (
          <Notice tone={notice.tone === 'error' ? 'danger' : 'success'} role={notice.tone === 'error' ? 'alert' : 'status'} className="p-3">
            {notice.text}
          </Notice>
        )}

        {loadError && (
          <Notice tone="danger" role="alert">
            {loadError}
            <Button variant="secondary" size="sm" className="ml-3" onClick={() => { setFetching(true); load(); }}>Try again</Button>
          </Notice>
        )}

        {fetching && !loadError && (
          <div className="flex justify-center py-12" role="status" aria-label="Loading users"><Loader2 className="w-6 h-6 animate-spin text-brand" /></div>
        )}

        {!fetching && !loadError && (
          <Card flush className="relative overflow-x-auto">
            <table className="w-full text-app">
              <thead>
                <tr className="border-b border-border text-left text-caption text-fg-muted">
                  <th className="p-4 font-medium">Email</th>
                  <th className="p-4 font-medium">Role</th>
                  <th className="p-4 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {users.map((u) => {
                  const isSelf = u.id === user?.id;
                  const busy = savingId === u.id;
                  return (
                    <tr key={u.id}>
                      <td className="p-4 text-fg">
                        {u.email}
                        {isSelf && <span className="ml-2 text-caption text-fg-muted">(you)</span>}
                      </td>
                      <td className="p-4">
                        <label className="sr-only" htmlFor={`role-${u.id}`}>Role for {u.email}</label>
                        <select
                          id={`role-${u.id}`}
                          value={u.role}
                          disabled={isSelf || busy}
                          title={isSelf ? 'You cannot change your own role' : undefined}
                          onChange={(e) => request(u, { role: e.target.value as Role })}
                          className={SELECT}
                        >
                          {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                        </select>
                      </td>
                      <td className="p-4">
                        <div className="flex items-center gap-3">
                          <Badge tone={STATUS_TONE[u.status] ?? 'neutral'}>{u.status}</Badge>
                          <label className="sr-only" htmlFor={`status-${u.id}`}>Account status for {u.email}</label>
                          <select
                            id={`status-${u.id}`}
                            value={u.status}
                            disabled={isSelf || busy}
                            title={isSelf ? 'You cannot change your own account status' : undefined}
                            onChange={(e) => request(u, { status: e.target.value as AccountStatus })}
                            className={SELECT}
                          >
                            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                          </select>
                          {busy && <Loader2 className="w-4 h-4 animate-spin text-brand" aria-label="Saving" />}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {users.length === 0 && <p className="p-8 text-center text-fg-muted">No users found.</p>}
          </Card>
        )}
      </div>
    </AdminShell>
  );
}
