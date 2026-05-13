import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  SessionIdProvider,
  useSessionId,
} from '../src/contexts/SessionIdContext';

function Probe() {
  const { sessionId, setSessionId } = useSessionId();
  return (
    <>
      <span data-testid="sid">{sessionId ?? ''}</span>
      <button onClick={() => setSessionId('sid-2')}>set</button>
      <button onClick={() => setSessionId(null)}>clear</button>
    </>
  );
}

describe('SessionIdContext', () => {
  beforeEach(() => {
    localStorage.clear();
  });
  afterEach(() => {
    localStorage.clear();
  });

  it('initializes sessionId from localStorage', () => {
    localStorage.setItem('session_id', 'sid-stored');
    render(
      <SessionIdProvider>
        <Probe />
      </SessionIdProvider>,
    );
    expect(screen.getByTestId('sid').textContent).toBe('sid-stored');
  });

  it('setSessionId(id) updates state and writes localStorage', () => {
    render(
      <SessionIdProvider>
        <Probe />
      </SessionIdProvider>,
    );
    act(() => {
      screen.getByText('set').click();
    });
    expect(screen.getByTestId('sid').textContent).toBe('sid-2');
    expect(localStorage.getItem('session_id')).toBe('sid-2');
  });

  it('setSessionId(null) clears state and removes localStorage entry', () => {
    localStorage.setItem('session_id', 'sid-stored');
    render(
      <SessionIdProvider>
        <Probe />
      </SessionIdProvider>,
    );
    act(() => {
      screen.getByText('clear').click();
    });
    expect(screen.getByTestId('sid').textContent).toBe('');
    expect(localStorage.getItem('session_id')).toBeNull();
  });
});
