import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SignIn from '../src/pages/SignIn';

function renderSignIn() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<SignIn />} />
        <Route path="/lobby" element={<div>Lobby page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('SignIn', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ session_id: 'sid-1', username: 'Alice', color: '#ff6b9d' }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      ),
    );
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('redirects to /lobby if a valid session already exists', async () => {
    localStorage.setItem('session_id', 'sid-1');
    renderSignIn();
    expect(await screen.findByText(/lobby page/i)).toBeInTheDocument();
  });

  it('clears stale session_id and stays on sign-in when session 404s', async () => {
    localStorage.setItem('session_id', 'stale-id');
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'not found' }), {
        status: 404,
        headers: { 'content-type': 'application/json' },
      }),
    );
    renderSignIn();
    // Form is still rendered; not redirected to lobby.
    expect(await screen.findByRole('button', { name: /enter/i })).toBeDisabled();
    // Stale id should have been cleared.
    expect(localStorage.getItem('session_id')).toBeNull();
  });

  it('disables submit until input is valid', async () => {
    renderSignIn();
    const button = screen.getByRole('button', { name: /enter/i });
    expect(button).toBeDisabled();

    await userEvent.type(screen.getByLabelText(/username/i), 'Alice');
    expect(button).toBeDisabled();

    await userEvent.click(screen.getAllByRole('radio')[0]);
    expect(button).toBeEnabled();
  });

  it('shows error for invalid username', async () => {
    renderSignIn();
    await userEvent.type(screen.getByLabelText(/username/i), 'bob; DROP');
    expect(
      screen.getByText(/letters and numbers/i),
    ).toBeInTheDocument();
  });

  it('submits and navigates to lobby on success', async () => {
    renderSignIn();
    await userEvent.type(screen.getByLabelText(/username/i), 'Alice');
    await userEvent.click(screen.getAllByRole('radio')[0]);
    await userEvent.click(screen.getByRole('button', { name: /enter/i }));

    expect(await screen.findByText(/lobby page/i)).toBeInTheDocument();
    expect(localStorage.getItem('session_id')).toBe('sid-1');
  });
});
