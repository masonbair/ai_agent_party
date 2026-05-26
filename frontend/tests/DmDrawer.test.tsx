import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import DmDrawer from '../src/components/DmDrawer';
import type { ThreadSummary } from '../src/api/dm';

const baseProps = {
  open: true,
  onClose: vi.fn(),
  principal: { kind: 'human' as const, id: 'me' },
  unreadCount: () => 0,
  openedKey: null,
  openedThread: null,
  onCloseThread: vi.fn(),
  onMarkRead: vi.fn(),
};

const sampleThread: ThreadSummary = {
  thread_key: 'human:friend|human:me',
  other_principal_key: 'human:friend',
  last_at: 100,
  last_text: 'hello',
  last_sender_kind: 'human',
  last_sender_id: 'friend',
  last_sender_name: 'Friend',
  last_message_id: 1,
};

describe('DmDrawer', () => {
  it('shows the empty state when there are no threads', () => {
    render(
      <DmDrawer
        {...baseProps}
        threads={[]}
        onOpenThread={async () => {}}
      />,
    );
    expect(screen.getByText(/no threads yet/i)).toBeInTheDocument();
  });

  it('renders the thread list when threads exist', () => {
    render(
      <DmDrawer
        {...baseProps}
        threads={[sampleThread]}
        onOpenThread={async () => {}}
      />,
    );
    expect(screen.getByText('Friend')).toBeInTheDocument();
    expect(screen.getByText('hello')).toBeInTheDocument();
  });

  it('shows the open thread view with back button when openedKey is set', () => {
    const opened = {
      messages: [
        {
          id: 1,
          sender_kind: 'human' as const,
          sender_id: 'friend',
          sender_name: 'Friend',
          text: 'hi',
          at: 100,
        },
      ],
      loadOlder: async () => {},
      send: async () => {},
      sendError: null,
      canSend: true,
    };
    const onCloseThread = vi.fn();
    render(
      <DmDrawer
        {...baseProps}
        threads={[sampleThread]}
        openedKey={sampleThread.thread_key}
        openedThread={opened}
        onOpenThread={async () => {}}
        onCloseThread={onCloseThread}
      />,
    );
    expect(screen.getByText('hi')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('Back to thread list'));
    expect(onCloseThread).toHaveBeenCalled();
  });

  it('returns null when not open', () => {
    const { container } = render(
      <DmDrawer
        {...baseProps}
        open={false}
        threads={[]}
        onOpenThread={async () => {}}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('clicking a thread invokes onOpenThread', async () => {
    const onOpenThread = vi.fn(async () => {});
    render(
      <DmDrawer
        {...baseProps}
        threads={[sampleThread]}
        onOpenThread={onOpenThread}
      />,
    );
    fireEvent.click(screen.getByText('Friend'));
    await waitFor(() =>
      expect(onOpenThread).toHaveBeenCalledWith(sampleThread.thread_key),
    );
  });
});
