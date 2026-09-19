import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const mockFrom = vi.fn();
const mockGetUser = vi.fn();
const mockRpc = vi.fn();
const mockUpdateAuthUser = vi.fn();

vi.mock('@supabase/supabase-js', () => ({
  createClient: vi.fn(() => ({
    from: mockFrom,
    rpc: mockRpc,
    auth: { getUser: mockGetUser, admin: { updateUserById: mockUpdateAuthUser } },
  })),
}));

process.env.NEXT_PUBLIC_SUPABASE_URL = 'https://mock.supabase.co';
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'mock-anon-key';
process.env.SUPABASE_SERVICE_ROLE_KEY = 'mock-service-key';

import { GET, PATCH } from './route';

const ADMIN = 'admin-1';
const req = (method: string, body?: unknown, auth = true) =>
  new Request('http://localhost/api/admin/users', {
    method,
    headers: auth ? { Authorization: 'Bearer t', 'Content-Type': 'application/json' } : {},
    body: body === undefined ? undefined : typeof body === 'string' ? body : JSON.stringify(body),
  });

function asRole(role: string, callerStatus: string | null = 'active') {
  mockGetUser.mockResolvedValue({ data: { user: { id: ADMIN, email: 'a@example.com' } }, error: null });
  mockRpc.mockResolvedValue({ data: role, error: null });
  callerRow = callerStatus === null ? null : { status: callerStatus };
}

let callerRow: { status: string } | null;
let calls: string[];
let updates: Record<string, unknown>[];
let auditRows: Record<string, unknown>[];

/** Fake of the tables the route touches. `failAudit` / `failUpdate` inject faults. */
function stubDb(opts: {
  target?: { id: string; email: string; role: string; status: string } | null;
  list?: unknown[];
  failUpdate?: boolean;
  failAudit?: boolean;
  lookupError?: string;
  listError?: string;
} = {}) {
  const target = opts.target === undefined ? { id: 'u2', email: 'u2@example.com', role: 'user', status: 'active' } : opts.target;
  mockFrom.mockImplementation((table: string) => {
    if (table === 'users') {
      return {
        select: (cols: string) => {
          if (cols === 'status') return { eq: () => ({ maybeSingle: async () => ({ data: callerRow, error: null }) }) };
          if (cols.includes('created_at')) {
            return { order: () => ({ range: async () => (opts.listError ? { data: null, error: { message: opts.listError } } : { data: opts.list ?? [], error: null }) }) };
          }
          return {
            eq: () => ({
              maybeSingle: async () => (opts.lookupError ? { data: null, error: { message: opts.lookupError } } : { data: target, error: null }),
            }),
          };
        },
        update: (row: Record<string, unknown>) => ({
          eq: async () => {
            calls.push('users.update');
            updates.push(row);
            return { error: opts.failUpdate && updates.length === 1 ? { message: 'update failed' } : null };
          },
        }),
      };
    }
    if (table === 'admin_audit_log') {
      return {
        insert: async (rows: Record<string, unknown>[]) => {
          calls.push('audit.insert');
          if (opts.failAudit) return { error: { message: 'audit failed' } };
          auditRows.push(...rows);
          return { error: null };
        },
      };
    }
    throw new Error(`unexpected table ${table}`);
  });
}

describe('/api/admin/users (FR-042 / FR-043)', () => {
  let info: ReturnType<typeof vi.spyOn>;
  let error: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    [mockFrom, mockGetUser, mockRpc, mockUpdateAuthUser].forEach((m) => m.mockReset());
    calls = []; updates = []; auditRows = [];
    mockUpdateAuthUser.mockResolvedValue({ error: null });
    info = vi.spyOn(console, 'info').mockImplementation(() => {});
    error = vi.spyOn(console, 'error').mockImplementation(() => {});
  });
  afterEach(() => { info.mockRestore(); error.mockRestore(); });

  describe('authorization', () => {
    it('401 with no token', async () => {
      expect((await PATCH(req('PATCH', {}, false))).status).toBe(401);
      expect((await GET(req('GET', undefined, false))).status).toBe(401);
    });
    it.each(['user', 'agent'])('403 for %s on both verbs, and nothing is read or written', async (role) => {
      asRole(role);
      stubDb();
      expect((await PATCH(req('PATCH', { id: 'u2', role: 'admin' }))).status).toBe(403);
      expect((await GET(req('GET'))).status).toBe(403);
      expect(calls).toEqual([]);
      expect(mockUpdateAuthUser).not.toHaveBeenCalled();
    });
    it('a suspended administrator is rejected even with a still-valid token', async () => {
      asRole('admin', 'suspended');
      stubDb();
      expect((await PATCH(req('PATCH', { id: 'u2', role: 'agent' }))).status).toBe(401);
      expect(calls).toEqual([]);
    });
  });

  describe('GET', () => {
    it('lists users', async () => {
      asRole('admin');
      stubDb({ list: [{ id: 'u2', email: 'u2@example.com', role: 'user', status: 'active' }] });
      const res = await GET(req('GET'));
      expect(res.status).toBe(200);
      expect((await res.json()).data).toHaveLength(1);
    });
    it('503 with the migration hint when the status column does not exist yet', async () => {
      asRole('admin');
      stubDb({ listError: 'column users.status does not exist' });
      const res = await GET(req('GET'));
      expect(res.status).toBe(503);
      expect((await res.json()).error).toContain('supabase_user_management.sql');
    });
    it('500 with a generic message otherwise (no internals leaked)', async () => {
      asRole('admin');
      stubDb({ listError: 'permission denied for table secret' });
      const res = await GET(req('GET'));
      expect(res.status).toBe(500);
      expect(JSON.stringify(await res.json())).not.toContain('secret');
    });
  });

  describe('PATCH - role change (FR-042)', () => {
    it('updates the role, writes one audit row with old and new values, logs it', async () => {
      asRole('admin');
      stubDb();
      const res = await PATCH(req('PATCH', { id: 'u2', role: 'agent' }));

      expect(res.status).toBe(200);
      expect((await res.json()).user).toMatchObject({ id: 'u2', role: 'agent', status: 'active' });
      expect(updates[0]).toMatchObject({ role: 'agent' });
      expect(updates[0]).not.toHaveProperty('status');
      expect(auditRows).toEqual([{ actor_id: ADMIN, target_user_id: 'u2', action: 'role_change', old_value: 'user', new_value: 'agent' }]);
      expect(mockUpdateAuthUser).not.toHaveBeenCalled(); // a role change never touches sign-in access
      expect(JSON.parse(String(info.mock.calls[0][0]))).toMatchObject({ event: 'admin.user_change', outcome: 'success', actorId: ADMIN, targetId: 'u2', role: 'agent' });
    });

    it.each([
      ['unknown role', { id: 'u2', role: 'root' }, 400],
      ['no change', { id: 'u2', role: 'user' }, 400],
      ['own role', { id: ADMIN, role: 'user' }, 403],
      ['missing id', { role: 'agent' }, 400],
    ])('A1: rejects %s (%i) and writes nothing', async (_n, body, status) => {
      asRole('admin');
      stubDb(status === 403 ? { target: { id: ADMIN, email: 'a@example.com', role: 'admin', status: 'active' } } : {});
      const res = await PATCH(req('PATCH', body));
      expect(res.status).toBe(status);
      expect(calls).toEqual([]);
      expect(auditRows).toEqual([]);
      expect(JSON.parse(String(error.mock.calls[0][0]))).toMatchObject({ outcome: 'rejected' });
    });

    it('404 for a user that does not exist', async () => {
      asRole('admin');
      stubDb({ target: null });
      expect((await PATCH(req('PATCH', { id: 'ghost', role: 'agent' }))).status).toBe(404);
      expect(calls).toEqual([]);
    });

    it('400 for malformed JSON', async () => {
      asRole('admin');
      stubDb();
      expect((await PATCH(req('PATCH', '{nope'))).status).toBe(400);
    });
  });

  describe('PATCH - account status (FR-043)', () => {
    it('suspending bans the account in Supabase Auth so it cannot sign in, and audits it', async () => {
      asRole('admin');
      stubDb();
      const res = await PATCH(req('PATCH', { id: 'u2', status: 'suspended' }));

      expect(res.status).toBe(200);
      expect(mockUpdateAuthUser).toHaveBeenCalledWith('u2', { ban_duration: '876000h' });
      expect(auditRows).toEqual([{ actor_id: ADMIN, target_user_id: 'u2', action: 'status_change', old_value: 'active', new_value: 'suspended' }]);
    });

    it('reactivating lifts the ban', async () => {
      asRole('admin');
      stubDb({ target: { id: 'u2', email: 'u2@example.com', role: 'user', status: 'suspended' } });
      await PATCH(req('PATCH', { id: 'u2', status: 'active' }));
      expect(mockUpdateAuthUser).toHaveBeenCalledWith('u2', { ban_duration: 'none' });
    });

    it('deactivating also bans', async () => {
      asRole('admin');
      stubDb();
      await PATCH(req('PATCH', { id: 'u2', status: 'deactivated' }));
      expect(mockUpdateAuthUser).toHaveBeenCalledWith('u2', { ban_duration: '876000h' });
    });

    it('a role and a status change together produce two audit rows', async () => {
      asRole('admin');
      stubDb();
      await PATCH(req('PATCH', { id: 'u2', role: 'agent', status: 'suspended' }));
      expect(auditRows.map((r) => r.action)).toEqual(['role_change', 'status_change']);
    });

    it('cannot suspend yourself', async () => {
      asRole('admin');
      stubDb({ target: { id: ADMIN, email: 'a@example.com', role: 'admin', status: 'active' } });
      const res = await PATCH(req('PATCH', { id: ADMIN, status: 'suspended' }));
      expect(res.status).toBe(403);
      expect(mockUpdateAuthUser).not.toHaveBeenCalled();
    });
  });

  describe('failure handling - never leave a half-applied change', () => {
    it('rolls the row back and reports 502 when the Auth ban fails', async () => {
      asRole('admin');
      stubDb();
      mockUpdateAuthUser.mockResolvedValueOnce({ error: { message: 'auth down' } });
      const res = await PATCH(req('PATCH', { id: 'u2', status: 'suspended' }));

      expect(res.status).toBe(502);
      expect(updates).toHaveLength(2);
      expect(updates[1]).toMatchObject({ role: 'user', status: 'active' }); // restored
      expect(auditRows).toEqual([]); // nothing audited for a change that did not happen
    });

    it('undoes both the row and the ban when the audit row cannot be written', async () => {
      asRole('admin');
      stubDb({ failAudit: true });
      const res = await PATCH(req('PATCH', { id: 'u2', status: 'suspended' }));

      expect(res.status).toBe(500);
      expect(updates[1]).toMatchObject({ role: 'user', status: 'active' });
      expect(mockUpdateAuthUser).toHaveBeenLastCalledWith('u2', { ban_duration: 'none' });
      expect((await res.json()).error).toMatch(/audit log; nothing was changed/);
    });

    it('a failed role change on the audit step is undone too', async () => {
      asRole('admin');
      stubDb({ failAudit: true });
      const res = await PATCH(req('PATCH', { id: 'u2', role: 'admin' }));
      expect(res.status).toBe(500);
      expect(updates[1]).toMatchObject({ role: 'user' });
      expect(mockUpdateAuthUser).not.toHaveBeenCalled();
    });

    it('a failed row update is a plain 500 with no ban and no audit', async () => {
      asRole('admin');
      stubDb({ failUpdate: true });
      const res = await PATCH(req('PATCH', { id: 'u2', status: 'suspended' }));
      expect(res.status).toBe(500);
      expect(mockUpdateAuthUser).not.toHaveBeenCalled();
      expect(auditRows).toEqual([]);
    });

    it('503 with the migration hint when the status column is missing', async () => {
      asRole('admin');
      stubDb({ lookupError: 'column users.status does not exist' });
      const res = await PATCH(req('PATCH', { id: 'u2', status: 'suspended' }));
      expect(res.status).toBe(503);
      expect(calls).toEqual([]);
    });
  });
});
