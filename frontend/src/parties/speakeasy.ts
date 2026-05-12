import type { PartyConfig } from './types';

export const speakeasy: PartyConfig = {
  slug: 'speakeasy',
  name: 'The Speakeasy',
  description: 'A warm prohibition-era bar with low light, a long polished counter, and intimate booths.',
  theme: {
    floor: 'linear-gradient(180deg, #4a3526 0%, #3a2516 100%)',
    accent: '#c89b6a',
  },
  zones: [
    {
      id: 'bar',
      label: 'BAR',
      x: 10.0,
      y: 28.0,
      width: 80.0,
      height: 18.0,
      color: '#d4a574',
      labelColor: '#3a2516',
      borderColor: '#6b4a2a',
    },
    {
      id: 'dance',
      label: 'DANCE',
      x: 8.0,
      y: 52.0,
      width: 40.0,
      height: 40.0,
      color: '#b8336a',
      labelColor: '#ffffff',
      borderColor: '#5a1a35',
    },
    {
      id: 'booths',
      label: 'BOOTHS',
      x: 52.0,
      y: 52.0,
      width: 40.0,
      height: 40.0,
      color: '#7a5836',
      labelColor: '#ffffff',
      borderColor: '#3d2c1c',
    },
  ],
  music: { url: null, label: 'Music coming soon' },
  worldSize: { width: 800, height: 500 },
  room: {
    clipPath: null,
    border: '8px solid #8a6234',
    borderRadius: 8,
    walls: [
      { x: 15.0, y: 22.0, width: 30.0, height: 1.5, color: '#c89b6a' },
      { x: 55.0, y: 22.0, width: 30.0, height: 1.5, color: '#c89b6a' },
    ],
  },
};
