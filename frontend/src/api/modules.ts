import type { Principal } from './party';
import type { LightingPreset, ReactionEmoji, StickyNote, Stroke } from './types';

const headers = { 'Content-Type': 'application/json' };

export async function react(slug: string, principal: Principal, emoji: ReactionEmoji) {
  const r = await fetch(`/api/parties/${slug}/react`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ principal, emoji }),
  });
  if (!r.ok) throw new Error(`react failed: ${r.status}`);
  return r.json();
}

export async function setLighting(
  slug: string,
  principal: Principal,
  preset: LightingPreset,
) {
  const r = await fetch(`/api/parties/${slug}/lighting`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ principal, preset }),
  });
  if (!r.ok) throw new Error(`setLighting failed: ${r.status}`);
  return r.json();
}

export async function createNote(
  slug: string,
  moduleId: string,
  principal: Principal,
  text: string,
  color: StickyNote['color'],
  x: number,
  y: number,
) {
  const r = await fetch(`/api/parties/${slug}/modules/${moduleId}/notes`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ principal, text, color, x, y }),
  });
  if (!r.ok) throw r;
  return (await r.json()).note as StickyNote;
}

export async function patchNote(
  slug: string,
  moduleId: string,
  noteId: string,
  principal: Principal,
  patch: Partial<Pick<StickyNote, 'text' | 'color' | 'x' | 'y'>>,
) {
  const r = await fetch(`/api/parties/${slug}/modules/${moduleId}/notes/${noteId}`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify({ principal, ...patch }),
  });
  if (!r.ok) throw r;
  return (await r.json()).note as StickyNote;
}

export async function deleteNote(
  slug: string,
  moduleId: string,
  noteId: string,
  principal: Principal,
) {
  const r = await fetch(`/api/parties/${slug}/modules/${moduleId}/notes/${noteId}`, {
    method: 'DELETE',
    headers,
    body: JSON.stringify({ principal }),
  });
  if (!r.ok && r.status !== 204) throw r;
}

export async function addStroke(
  slug: string,
  moduleId: string,
  principal: Principal,
  color: string,
  width: Stroke['width'],
  points: { x: number; y: number }[],
) {
  const r = await fetch(`/api/parties/${slug}/modules/${moduleId}/strokes`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ principal, color, width, points }),
  });
  if (!r.ok) throw r;
  return (await r.json()).stroke as Stroke;
}

export async function voteClear(slug: string, moduleId: string, principal: Principal) {
  const r = await fetch(`/api/parties/${slug}/modules/${moduleId}/clear`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ principal }),
  });
  if (!r.ok) throw r;
  return r.json() as Promise<{ votes: number; needed: number; cleared: boolean }>;
}
