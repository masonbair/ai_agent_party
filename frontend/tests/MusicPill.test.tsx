import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import MusicPill from '../src/components/MusicPill';

describe('MusicPill', () => {
  it('renders fallback label when no trackId provided', () => {
    render(<MusicPill label="Music coming soon" />);
    expect(screen.getByText(/Music coming soon/)).toBeInTheDocument();
  });

  it('renders the trackId when provided', () => {
    render(<MusicPill label="Music coming soon" trackId="lofi-loop" />);
    expect(screen.getByText(/lofi-loop/)).toBeInTheDocument();
  });

  it('renders the fallback label when trackId is null', () => {
    render(<MusicPill label="Music coming soon" trackId={null} />);
    expect(screen.getByText(/Music coming soon/)).toBeInTheDocument();
  });
});
