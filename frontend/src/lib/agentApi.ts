import { supabase } from './supabase';
import { fetchJson } from './fetchJson';
import type { QueueTicket } from './agentQueue';

// /api/tickets is staff-only, so every call carries the caller's session token.
async function authHeaders(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function fetchStaffTickets(): Promise<QueueTicket[]> {
  const json = await fetchJson<{ data: QueueTicket[] }>('/api/tickets', { headers: await authHeaders() });
  return json.data ?? [];
}

/** Sends the human answer. Throws with the server's message (404 unknown, 409 already resolved, ...). */
export async function submitResolution(id: string, finalResponse: string): Promise<void> {
  await fetchJson('/api/tickets', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify({ id, final_response: finalResponse }),
  });
}
