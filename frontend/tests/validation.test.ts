// frontend/tests/validation.test.ts
import { describe, it, expect } from 'vitest';
import {
  CHAT_MAX_LEN,
  CHAT_TEXT_REGEX,
  validateChatText,
} from '../src/api/validation';
import { USERNAME_REGEX } from '../src/constants';

describe('username validation', () => {
  it('accepts punctuated printable-ASCII usernames', () => {
    for (const u of ['ab', 'Alice42', 'foo.bar', 'a_b-c']) {
      expect(USERNAME_REGEX.test(u)).toBe(true);
    }
  });

  it('rejects spaces, emoji, and out-of-range lengths', () => {
    for (const u of ['has space', 'a', 'ab🙂', 'héllo', 'a'.repeat(21)]) {
      expect(USERNAME_REGEX.test(u)).toBe(false);
    }
  });
});

describe('chat validation', () => {
  it('exports the same max length as the backend', () => {
    expect(CHAT_MAX_LEN).toBe(65);
  });

  it('accepts the full printable-ASCII punctuation set', () => {
    expect(CHAT_TEXT_REGEX.test('hello, world!')).toBe(true);
    expect(CHAT_TEXT_REGEX.test('a@b: (hi) #1 ~ [x] {y} "q"')).toBe(true);
    expect(CHAT_TEXT_REGEX.test('<script>alert(1)</script>')).toBe(true);
  });

  it('rejects non-ASCII (emoji / other scripts)', () => {
    expect(CHAT_TEXT_REGEX.test('hi 🙂')).toBe(false);
    expect(CHAT_TEXT_REGEX.test('héllo')).toBe(false);
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
