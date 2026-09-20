// Rules for FR-042 (role management) and FR-043 (account status). Pure, so every rejection path can be tested
// without a database and the API route only has to do I/O.

export const ROLES = ['user', 'agent', 'admin'] as const;
export const STATUSES = ['active', 'suspended', 'deactivated'] as const;
export type Role = (typeof ROLES)[number];
export type AccountStatus = (typeof STATUSES)[number];

export type ManagedUser = {
  id: string;
  email: string;
  role: Role;
  status: AccountStatus;
  created_at?: string | null;
};

export type ChangeRequest = { id?: unknown; role?: unknown; status?: unknown };
export type ValidChange = { id: string; role?: Role; status?: AccountStatus };

export type Validation =
  | { ok: true; change: ValidChange }
  | { ok: false; httpStatus: 400 | 403 | 404; error: string };

const isRole = (v: unknown): v is Role => typeof v === 'string' && (ROLES as readonly string[]).includes(v);
const isStatus = (v: unknown): v is AccountStatus => typeof v === 'string' && (STATUSES as readonly string[]).includes(v);

/**
 * A1 - Invalid Role Assignment: anything not explained here is rejected, and nothing is written.
 * `target` is the user as currently stored (null when the id does not exist).
 */
export function validateChange(actorId: string, req: ChangeRequest, target: ManagedUser | null): Validation {
  if (typeof req.id !== 'string' || !req.id) return { ok: false, httpStatus: 400, error: 'id is required' };
  if (req.role === undefined && req.status === undefined) {
    return { ok: false, httpStatus: 400, error: 'Provide a role and/or a status to change' };
  }
  if (req.role !== undefined && !isRole(req.role)) {
    return { ok: false, httpStatus: 400, error: `role must be one of: ${ROLES.join(', ')}` };
  }
  if (req.status !== undefined && !isStatus(req.status)) {
    return { ok: false, httpStatus: 400, error: `status must be one of: ${STATUSES.join(', ')}` };
  }
  if (!target) return { ok: false, httpStatus: 404, error: 'User not found' };

  // An administrator locking themselves out (or dropping their own privileges) is almost always a mistake and can
  // leave the platform with nobody able to undo it. Another administrator can make the change deliberately.
  if (target.id === actorId) {
    return { ok: false, httpStatus: 403, error: 'You cannot change your own role or account status' };
  }

  const change: ValidChange = { id: target.id };
  if (req.role !== undefined && req.role !== target.role) change.role = req.role as Role;
  if (req.status !== undefined && req.status !== target.status) change.status = req.status as AccountStatus;
  if (change.role === undefined && change.status === undefined) {
    return { ok: false, httpStatus: 400, error: 'No change: the user already has these values' };
  }
  return { ok: true, change };
}

/** Whether the account is allowed to sign in / call the API. */
export function isActive(status: string | null | undefined): boolean {
  // A missing status means the column has not been applied yet (or the row predates it): treat as active,
  // never lock everyone out because of a schema lag.
  return status === undefined || status === null || status === 'active';
}

/** Supabase Auth ban duration for a status: 'none' lifts the ban; the long value is effectively indefinite. */
export function banDurationFor(status: AccountStatus): string {
  return status === 'active' ? 'none' : '876000h'; // ~100 years
}
