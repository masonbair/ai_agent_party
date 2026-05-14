// frontend/tests/validation.test.ts
import { describe, it, expect } from 'vitest';
import {
  CHAT_MAX_LEN,
  CHAT_TEXT_REGEX,
  validateChatText,
} from '../src/api/validation';

describe('chat validation', () => {
  it('exports the same max length as the backend', () => {
    expect(CHAT_MAX_LEN).toBe(280);
  });

  it('accepts allowed characters', () => {
    expect(CHAT_TEXT_REGEX.test('hello, world!')).toBe(true);
  });

  it('rejects disallowed characters', () => {
    expect(CHAT_TEXT_REGEX.test('hi 🙂')).toBe(false);
    expect(CHAT_TEXT_REGEX.test('a@b')).toBe(false);
  });

  it('validateChatText returns trimmed text on success', () => {
    expect(validateChatText('  hi  ')).toEqual({ ok: true, text: 'hi' });
  });

  it('validateChatText returns reason on empty input', () => {
    expect(validateChatText('   ')).toEqual({
      ok: false,
      reason: 'empty',
    });
  });

  it('validateChatText returns reason on over-length input', () => {
    const long = 'a'.repeat(CHAT_MAX_LEN + 1);
    expect(validateChatText(long)).toEqual({
      ok: false,
      reason: 'too_long',
    });
  });

  it('validateChatText returns reason on disallowed chars', () => {
    expect(validateChatText('hi 🙂')).toEqual({
      ok: false,
      reason: 'invalid_chars',
    });
  });
});
