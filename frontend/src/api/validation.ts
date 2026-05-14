// frontend/src/api/validation.ts
// Mirrors backend/app/validation.py — keep in sync.
export const CHAT_MAX_LEN = 280;
export const CHAT_TEXT_REGEX = /^[A-Za-z0-9 .,!?'\-]+$/;

export type ChatValidationResult =
  | { ok: true; text: string }
  | { ok: false; reason: 'empty' | 'too_long' | 'invalid_chars' };

export function validateChatText(raw: string): ChatValidationResult {
  const trimmed = raw.trim();
  if (trimmed.length === 0) return { ok: false, reason: 'empty' };
  if (trimmed.length > CHAT_MAX_LEN) return { ok: false, reason: 'too_long' };
  if (!CHAT_TEXT_REGEX.test(trimmed)) {
    return { ok: false, reason: 'invalid_chars' };
  }
  return { ok: true, text: trimmed };
}
