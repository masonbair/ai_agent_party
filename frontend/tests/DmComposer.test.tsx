import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import DmComposer from '../src/components/DmComposer';

describe('DmComposer', () => {
  it('sends valid text and clears the input', async () => {
    const onSend = vi.fn(async () => {});
    render(<DmComposer onSend={onSend} sendError={null} />);
    const input = screen.getByLabelText('DM message') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'hello' } });
    fireEvent.click(screen.getByText('Send'));
    await waitFor(() => expect(onSend).toHaveBeenCalledWith('hello'));
    await waitFor(() => expect(input.value).toBe(''));
  });

  it('rejects invalid characters before calling onSend', () => {
    const onSend = vi.fn();
    render(<DmComposer onSend={onSend} sendError={null} />);
    fireEvent.change(screen.getByLabelText('DM message'), {
      target: { value: 'nope 🙂' },
    });
    fireEvent.click(screen.getByText('Send'));
    expect(onSend).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('disables the composer when sendError says not_co_located', () => {
    render(<DmComposer onSend={vi.fn()} sendError="not_co_located" />);
    const input = screen.getByLabelText('DM message') as HTMLInputElement;
    expect(input).toBeDisabled();
    expect(screen.getByRole('alert').textContent).toMatch(/same party/i);
  });

  it('disables the composer when recipient is not present', () => {
    render(<DmComposer onSend={vi.fn()} sendError="recipient_not_present" />);
    expect(screen.getByLabelText('DM message')).toBeDisabled();
    expect(screen.getByRole('alert').textContent).toMatch(
      /isn.?t in any party/i,
    );
  });
});
