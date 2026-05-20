import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import InboxButton from '../src/components/InboxButton';

describe('InboxButton', () => {
  it('renders without a badge when unread is 0', () => {
    render(<InboxButton unreadCount={0} onClick={() => {}} />);
    expect(screen.queryByTestId('inbox-unread-badge')).toBeNull();
  });

  it('renders a badge with the unread count', () => {
    render(<InboxButton unreadCount={3} onClick={() => {}} />);
    expect(screen.getByTestId('inbox-unread-badge')).toHaveTextContent('3');
  });

  it('invokes onClick when activated', async () => {
    const onClick = vi.fn();
    render(<InboxButton unreadCount={1} onClick={onClick} />);
    screen.getByRole('button', { name: /direct messages/i }).click();
    expect(onClick).toHaveBeenCalled();
  });
});
