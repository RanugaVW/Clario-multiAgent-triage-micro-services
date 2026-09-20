'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { useAuth } from '../../../contexts/AuthContext';
import { supabase } from '../../../lib/supabase';
import { fetchJson } from '../../../lib/fetchJson';
import { ConfirmDialog, StatusBadge } from '../../../components/ui';
import { AdminShell } from '../AdminShell';
import { ROLES, STATUSES, type AccountStatus, type ManagedUser, type Role } from '../../../lib/userManagement';

async function authHeaders(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

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
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-[#E8A33D]" />
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
          <h1 className="text-2xl font-bold text-[#ECECEC]">Users</h1>
          <p className="text-sm text-[#8A8F98]">Change roles and manage account access. Every change is recorded in the audit log.</p>
        </header>

        {notice && (
          <div role={notice.tone === 'error' ? 'alert' : 'status'} className={`text-sm p-3 rounded-xl border ${notice.tone === 'error' ? 'bg-[#FB7185]/10 border-[#FB7185]/30 text-[#FB7185]' : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'}`}>
            {notice.text}
          </div>
        )}

        {loadError && (
          <div role="alert" className="bg-[#FB7185]/10 border border-[#FB7185]/30 text-[#FB7185] text-sm p-4 rounded-2xl">
            {loadError}
            <button onClick={() => { setFetching(true); load(); }} className="ml-3 underline underline-offset-4">Try again</button>
          </div>
        )}

        {fetching && !loadError && (
          <div className="flex justify-center py-12" role="status" aria-label="Loading users"><Loader2 className="w-6 h-6 animate-spin text-[#E8A33D]" /></div>
        )}

        {!fetching && !loadError && (
          <div className="glass-panel rounded-[28px] overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[#8A8F98] border-b border-white/10">
                  <th className="p-4 font-medium">Email</th>
                  <th className="p-4 font-medium">Role</th>
                  <th className="p-4 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {users.map((u) => {
                  const isSelf = u.id === user?.id;
                  const busy = savingId === u.id;
                  return (
                    <tr key={u.id}>
                      <td className="p-4 text-[#ECECEC]">
                        {u.email}
                        {isSelf && <span className="ml-2 text-xs text-[#8A8F98]">(you)</span>}
                      </td>
                      <td className="p-4">
                        <label className="sr-only" htmlFor={`role-${u.id}`}>Role for {u.email}</label>
                        <select
                          id={`role-${u.id}`}
                          value={u.role}
                          disabled={isSelf || busy}
                          title={isSelf ? 'You cannot change your own role' : undefined}
                          onChange={(e) => request(u, { role: e.target.value as Role })}
                          className="glass-input rounded-xl px-3 py-1.5 disabled:opacity-50"
                        >
                          {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                        </select>
                      </td>
                      <td className="p-4">
                        <div className="flex items-center gap-3">
                          <StatusBadge label={u.status} tone={STATUS_TONE[u.status] ?? 'neutral'} />
                          <label className="sr-only" htmlFor={`status-${u.id}`}>Account status for {u.email}</label>
                          <select
                            id={`status-${u.id}`}
                            value={u.status}
                            disabled={isSelf || busy}
                            title={isSelf ? 'You cannot change your own account status' : undefined}
                            onChange={(e) => request(u, { status: e.target.value as AccountStatus })}
                            className="glass-input rounded-xl px-3 py-1.5 disabled:opacity-50"
                          >
                            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                          </select>
                          {busy && <Loader2 className="w-4 h-4 animate-spin text-[#E8A33D]" aria-label="Saving" />}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {users.length === 0 && <p className="p-8 text-center text-[#8A8F98]">No users found.</p>}
          </div>
        )}
      </div>
    </AdminShell>
  );
}
