import type { PartyConfig } from './types';

export const creamTerrazzo: PartyConfig = {
  slug: 'cream-terrazzo',
  name: 'Cream Terrazzo Lounge',
  description: 'A bright, friendly room with bold pastel zones.',
  theme: {
    // Flat, opaque fill — one straight color so the page grain doesn't show
    // through the room floor (mirrors backend parties_data.py).
    floor: '#f4ead5',
    accent: '#ff6b9d',
  },
  zones: [
    {
      id: 'dance',
      label: 'DANCE',
      x: 6.0,
      y: 8.0,
      width: 34.0,
      height: 36.0,
      color: '#ff6b9d',
      labelColor: '#ffffff',
      borderColor: '#8b1a4a',
    },
    {
      id: 'chill',
      label: 'CHILL',
      x: 60.0,
      y: 8.0,
      width: 34.0,
      height: 28.0,
      color: '#4dd0e1',
      labelColor: '#ffffff',
      borderColor: '#00606e',
    },
    {
      id: 'snacks',
      label: 'SNACKS',
      x: 28.0,
      y: 58.0,
      width: 44.0,
      height: 34.0,
      color: '#ffb74d',
      labelColor: '#ffffff',
      borderColor: '#6b3a00',
    },
  ],
  music: { url: null, label: 'Music coming soon' },
  worldSize: { width: 800, height: 500 },
  room: {
    clipPath: null,
    border: '6px solid #8b6f47',
    borderRadius: 12,
    walls: [
      { x: 50.0, y: 0.0, width: 0.75, height: 30.0, color: '#8b6f47' },
      { x: 75.0, y: 40.0, width: 25.0, height: 1.2, color: '#8b6f47' },
    ],
  },
};
