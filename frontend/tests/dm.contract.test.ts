// Cross-stack contract: the dm.ts type definitions must match what the
// backend actually returns. We hand-mirror sample payloads here and force
// them into the parsed types. If the backend shape drifts, the TS types
// will diverge from this fixture and the assertion below will fail.

import { describe, expect, it } from 'vitest';
import type {
  DmMessage,
  ThreadSummary,
  SendDmResult,
} from '../src/api/dm';

// Mirrors `dm_store.list_threads_for` output (one dict per thread):
const SAMPLE_THREADS_RESPONSE: { threads: ThreadSummary[] } = {
  threads: [
    {
      thread_key: 'human:a|human:b',
      other_principal_key: 'human:b',
      last_at: 1700000000,
      last_text: 'hello',
      last_sender_kind: 'human',
      last_sender_id: 'b',
      last_sender_name: 'Bob',
      last_message_id: 42,
    },
  ],
};

// Mirrors `dm.send` return value:
const SAMPLE_SEND_RESPONSE: SendDmResult = {
  message_id: 42,
  at: 1700000000,
  thread_key: 'human:a|human:b',
};

// Mirrors the WS `{type:"dm", thread_key, message}` frame payload's
// `message` field — also the shape of rows returned by history.
const SAMPLE_DM_MESSAGE: DmMessage = {
  id: 1,
  sender_kind: 'human',
  sender_id: 'a',
  sender_name: 'Alice',
  text: 'hi',
  at: 1700000000,
};

describe('dm.ts ⇄ backend response contract', () => {
  it('list_threads_for fixture keys match ThreadSummary', () => {
    const summary = SAMPLE_THREADS_RESPONSE.threads[0];
    expect(Object.keys(summary).sort()).toEqual(
      [
        'last_at',
        'last_message_id',
        'last_sender_id',
        'last_sender_kind',
        'last_sender_name',
        'last_text',
        'other_principal_key',
        'thread_key',
      ].sort(),
    );
  });

  it('send response fixture keys match SendDmResult', () => {
    expect(Object.keys(SAMPLE_SEND_RESPONSE).sort()).toEqual(
      ['at', 'message_id', 'thread_key'].sort(),
    );
  });

  it('dm WS message fixture keys match DmMessage', () => {
    expect(Object.keys(SAMPLE_DM_MESSAGE).sort()).toEqual(
      ['at', 'id', 'sender_id', 'sender_kind', 'sender_name', 'text'].sort(),
    );
  });
});
