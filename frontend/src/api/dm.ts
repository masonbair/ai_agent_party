import { apiGet, apiPost } from './client';
import type { Principal } from './party';

export type DmMessage = {
  id: number;
  sender_kind: 'human' | 'agent';
  sender_id: string;
  sender_name: string;
  text: string;
  at: number;
};

export type ThreadSummary = {
  thread_key: string;
  other_principal_key: string;
  last_at: number;
  last_text: string;
  last_sender_kind: 'human' | 'agent';
  last_sender_id: string;
  last_sender_name: string;
  last_message_id: number;
};

export type Recipient = { kind: 'human' | 'agent'; id: string };

export type SendDmResult = {
  message_id: number;
  at: number;
  thread_key: string;
};

export async function sendDm(
  principal: Principal,
  recipient: Recipient,
  text: string,
): Promise<SendDmResult> {
  return apiPost('/api/dm/send', { principal, recipient, text });
}

export async function listThreads(
  principal: Principal,
): Promise<{ threads: ThreadSummary[] }> {
  const qs = new URLSearchParams({
    principal_kind: principal.kind,
    principal_id: principal.id,
  });
  return apiGet(`/api/dm/threads?${qs}`);
}

export async function getThreadHistory(
  thread_key: string,
  principal: Principal,
  opts: { beforeId?: number; limit?: number } = {},
): Promise<{ thread_key: string; messages: DmMessage[] }> {
  const qs = new URLSearchParams({
    principal_kind: principal.kind,
    principal_id: principal.id,
  });
  if (opts.beforeId != null) qs.set('before_id', String(opts.beforeId));
  if (opts.limit != null) qs.set('limit', String(opts.limit));
  return apiGet(`/api/dm/threads/${encodeURIComponent(thread_key)}/history?${qs}`);
}

export function principalKey(p: { kind: string; id: string }): string {
  return `${p.kind.toLowerCase()}:${p.id}`;
}

export function threadKey(a: string, b: string): string {
  return [a, b].sort().join('|');
}
