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

  it('exposes the keybind hint in the placeholder', () => {
    render(
      <ChatInput
        slug="cream-terrazzo"
        principal={{ kind: 'human', id: 'me' }}
        disabled={false}
      />,
    );
    const input = screen.getByRole('textbox') as HTMLInputElement;
    expect(input.placeholder).toMatch(/press t/i);
  });

  it('focuses the input when T is pressed on the window', () => {
    render(
      <ChatInput
        slug="cream-terrazzo"
        principal={{ kind: 'human', id: 'me' }}
        disabled={false}
      />,
    );
    const input = screen.getByRole('textbox') as HTMLInputElement;
    expect(input).not.toHaveFocus();
    fireEvent.keyDown(window, { key: 't' });
    expect(input).toHaveFocus();
  });

  it('does not hijack T when the user is already typing in an input', () => {
    render(
      <>
        <input data-testid="other" />
        <ChatInput
          slug="cream-terrazzo"
          principal={{ kind: 'human', id: 'me' }}
          disabled={false}
        />
      </>,
    );
    const other = screen.getByTestId('other') as HTMLInputElement;
    other.focus();
    fireEvent.keyDown(other, { key: 't' });
    expect(other).toHaveFocus();
  });

  it('blurs on Escape', () => {
    render(
      <ChatInput
        slug="cream-terrazzo"
        principal={{ kind: 'human', id: 'me' }}
        disabled={false}
      />,
    );
    const input = screen.getByRole('textbox') as HTMLInputElement;
    input.focus();
    expect(input).toHaveFocus();
    fireEvent.keyDown(input, { key: 'Escape' });
    expect(input).not.toHaveFocus();
  });

  it('stops click propagation so the floor does not receive the click', () => {
    const onFloorClick = vi.fn();
    render(
      <div onClick={onFloorClick}>
        <ChatInput
          slug="cream-terrazzo"
          principal={{ kind: 'human', id: 'me' }}
          disabled={false}
        />
      </div>,
    );
    fireEvent.click(screen.getByRole('textbox'));
    expect(onFloorClick).not.toHaveBeenCalled();
  });
});
