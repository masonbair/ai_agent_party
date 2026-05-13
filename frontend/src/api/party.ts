import { apiPost } from './client';
import type { Participant } from './types';

export type Principal = { kind: 'human' | 'agent'; id: string };

export async function joinParty(
  slug: string,
  principal: Principal,
): Promise<{ participant: Participant; cursor: number }> {
  return apiPost(`/api/parties/${slug}/join`, { principal });
}

export async function leaveParty(slug: string, principal: Principal): Promise<void> {
  await apiPost(`/api/parties/${slug}/leave`, { principal });
}

export async function moveInParty(
  slug: string,
  principal: Principal,
  x: number,
  y: number,
): Promise<{ x: number; y: number; cursor: number }> {
  return apiPost(`/api/parties/${slug}/move`, { principal, x, y });
}

export async function chatInParty(
  slug: string,
  principal: Principal,
  text: string,
): Promise<{ cursor: number }> {
  return apiPost(`/api/parties/${slug}/chat`, { principal, text });
}
