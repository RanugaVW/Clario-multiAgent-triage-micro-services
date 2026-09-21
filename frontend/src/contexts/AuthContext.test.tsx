import { act, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider, useAuth } from './AuthContext';

const h = vi.hoisted(() => ({
  sessionRejects: false,
  session: null as { user: { id: string } } | null,
  rpc: vi.fn(),
  authCb: null as null | ((event: string, session: { user: { id: string } } | null) => Promise<void> | void),
}));

vi.mock('../lib/supabase', () => ({
  supabase: {
    rpc: (...args: unknown[]) => h.rpc(...args),
    auth: {
      getSession: () => (h.sessionRejects ? Promise.reject(new Error('auth unreachable')) : Promise.resolve({ data: { session: h.session } })),
      onAuthStateChange: (cb: typeof h.authCb) => {
        h.authCb = cb;
        return { data: { subscription: { unsubscribe: vi.fn() } } };
      },
    },
  },
}));

function Probe() {
  const { roleLoading, role, loading } = useAuth();
  return (
    <div>
      <span data-testid="state">{`${loading}|${roleLoading}|${role ?? 'none'}`}</span>
    </div>
  );
}

const state = () => screen.getByTestId('state').textContent;

beforeEach(() => {
  h.session = null;
  h.sessionRejects = false;
  h.rpc.mockReset();
  h.authCb = null;
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

describe('AuthProvider role loading', () => {
  it('resolves the role from get_my_role for a signed-in user', async () => {
    h.session = { user: { id: 'u1' } };
    h.rpc.mockResolvedValue({ data: 'admin', error: null });
    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(state()).toBe('false|false|admin'));
  });

  it('clears roleLoading and leaves role null when the initial role lookup throws', async () => {
    h.session = { user: { id: 'u1' } };
    h.rpc.mockRejectedValue(new Error('network down'));
    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(state()).toBe('false|false|none'));
  });

  it('clears roleLoading and leaves role null when the lookup throws after an auth state change', async () => {
    h.rpc.mockRejectedValue(new Error('network down'));
    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(h.authCb).not.toBeNull());
    await waitFor(() => expect(state()).toBe('false|false|none'));
    // A sign-in event arrives, and the lookup fails; the handler's rejection must not leave roleLoading stuck.
    await act(async () => {
      await Promise.resolve(h.authCb!('SIGNED_IN', { user: { id: 'u2' } })).catch(() => {});
    });
    await waitFor(() => expect(state()).toBe('false|false|none'));
  });

  it('stops loading and behaves as signed out when getSession rejects', async () => {
    h.sessionRejects = true;
    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(state()).toBe('false|false|none'));
  });
});
