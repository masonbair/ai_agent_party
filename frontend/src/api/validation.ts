// frontend/src/api/validation.ts
// Mirrors backend/app/validation.py CHAT_ALLOWED_CHARS_REGEX — keep in sync.
// Printable ASCII (0x20–0x7E): letters, digits, space, and all punctuation.
// Emoji / non-Latin scripts are out of scope.
export const CHAT_MAX_LEN = 65;
export const CHAT_TEXT_REGEX = /^[\x20-\x7E]+$/;

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
