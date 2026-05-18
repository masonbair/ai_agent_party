// frontend/tests/ChatInput.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ChatInput from '../src/components/ChatInput';
import * as partyApi from '../src/api/party';

describe('ChatInput', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders an input', () => {
    render(
      <ChatInput
        slug="cream-terrazzo"
        principal={{ kind: 'human', id: 'me' }}
        disabled={false}
      />,
    );
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('calls chatInParty on Enter and clears the input', async () => {
    const spy = vi
      .spyOn(partyApi, 'chatInParty')
      .mockResolvedValue({ cursor: 1 });
    render(
      <ChatInput
        slug="cream-terrazzo"
        principal={{ kind: 'human', id: 'me' }}
        disabled={false}
      />,
    );
    const input = screen.getByRole('textbox') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'hi there' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(spy).toHaveBeenCalledWith('cream-terrazzo', { kind: 'human', id: 'me' }, 'hi there');
    // Wait a microtask for the awaited then-clear.
    await Promise.resolve();
    expect(input.value).toBe('');
  });

  it('refuses to send invalid characters and shows a message', () => {
    const spy = vi.spyOn(partyApi, 'chatInParty');
    render(
      <ChatInput
        slug="cream-terrazzo"
        principal={{ kind: 'human', id: 'me' }}
        disabled={false}
      />,
    );
    const input = screen.getByRole('textbox') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'hi 🙂' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(spy).not.toHaveBeenCalled();
    expect(screen.getByText(/disallowed/i)).toBeInTheDocument();
  });

  it('refuses to send empty input', () => {
    const spy = vi.spyOn(partyApi, 'chatInParty');
    render(
      <ChatInput
        slug="cream-terrazzo"
        principal={{ kind: 'human', id: 'me' }}
        disabled={false}
      />,
    );
    const input = screen.getByRole('textbox') as HTMLInputElement;
    fireEvent.change(input, { target: { value: '   ' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(spy).not.toHaveBeenCalled();
  });

  it('disables the input when status is closed', () => {
    render(
      <ChatInput
        slug="cream-terrazzo"
        principal={{ kind: 'human', id: 'me' }}
        disabled={true}
      />,
    );
    const input = screen.getByRole('textbox') as HTMLInputElement;
    expect(input.disabled).toBe(true);
  });
});
