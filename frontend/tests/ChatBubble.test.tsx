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

  it('renders injection payloads as inert text, not live DOM', () => {
    const payload = '<img src=x onerror=alert(1)><script>alert(2)</script>';
    const { container } = render(
      <ChatBubble
        text={payload}
        x={50}
        y={50}
        worldWidth={100}
        worldHeight={100}
        expiresAt={Date.now() + 5000}
      />,
    );
    // The literal string is shown to the user...
    expect(screen.getByText(payload)).toBeInTheDocument();
    // ...and React escaped it — no real <img>/<script> nodes were created.
    expect(container.querySelector('img')).toBeNull();
    expect(container.querySelector('script')).toBeNull();
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

  it('uses the speaker color for the border', () => {
    render(
      <ChatBubble
        text="hi"
        color="#4dd0e1"
        x={50}
        y={50}
        worldWidth={100}
        worldHeight={100}
        expiresAt={Date.now() + 5000}
      />,
    );
    const el = screen.getByText('hi').parentElement!;
    // jsdom normalizes hex to rgb in border shorthand; assert the color is present.
    expect(el.style.border).toContain('1px solid');
    expect(el.style.borderColor || el.style.border).toMatch(/77, 208, 225|#4dd0e1/);
  });

  it('renders an ambient puff with no message text', () => {
    render(
      <ChatBubble
        text=""
        ambient
        color="#4dd0e1"
        x={50}
        y={50}
        worldWidth={100}
        worldHeight={100}
        expiresAt={Date.now() + 2000}
      />,
    );
    expect(screen.getByText('···')).toBeInTheDocument();
  });
});
