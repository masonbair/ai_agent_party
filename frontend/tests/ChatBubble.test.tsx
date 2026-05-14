// frontend/tests/ChatBubble.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ChatBubble from '../src/components/ChatBubble';

describe('ChatBubble', () => {
  it('renders the message text', () => {
    render(
      <ChatBubble
        text="hello there"
        x={50}
        y={50}
        worldWidth={100}
        worldHeight={100}
        expiresAt={Date.now() + 5000}
      />,
    );
    expect(screen.getByText('hello there')).toBeInTheDocument();
  });

  it('positions itself as a percentage of world dimensions', () => {
    render(
      <ChatBubble
        text="x"
        x={25}
        y={75}
        worldWidth={100}
        worldHeight={100}
        expiresAt={Date.now() + 5000}
      />,
    );
    const el = screen.getByText('x').parentElement!;
    expect(el.style.left).toBe('25%');
    expect(el.style.top).toBe('75%');
  });

  it('applies fading class when within 500ms of expiry', () => {
    render(
      <ChatBubble
        text="x"
        x={0}
        y={0}
        worldWidth={100}
        worldHeight={100}
        expiresAt={Date.now() + 200}
      />,
    );
    const el = screen.getByText('x').parentElement!;
    expect(el.getAttribute('data-fading')).toBe('true');
  });

  it('does not mark fading when far from expiry', () => {
    render(
      <ChatBubble
        text="x"
        x={0}
        y={0}
        worldWidth={100}
        worldHeight={100}
        expiresAt={Date.now() + 4000}
      />,
    );
    const el = screen.getByText('x').parentElement!;
    expect(el.getAttribute('data-fading')).toBeNull();
  });
});
