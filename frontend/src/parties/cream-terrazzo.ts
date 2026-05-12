import type { PartyConfig } from './types';

export const creamTerrazzo: PartyConfig = {
  slug: 'cream-terrazzo',
  name: 'Cream Terrazzo Lounge',
  description: 'A bright, friendly room with soft pastel zones.',
  theme: {
    floor:
      '#f4ead5 radial-gradient(circle 2px at 10% 20%, #c0a070 1px, transparent 2px), ' +
      'radial-gradient(circle 2px at 40% 60%, #a85d3a 1px, transparent 2px), ' +
      'radial-gradient(circle 2px at 70% 30%, #c0a070 1px, transparent 2px), ' +
      'radial-gradient(circle 2px at 85% 80%, #8b6f47 1px, transparent 2px), ' +
      'radial-gradient(circle 2px at 25% 85%, #c0a070 1px, transparent 2px)',
    accent: '#ff6b9d',
  },
  zones: [
    {
      id: 'dance',
      label: 'DANCE',
      x: 25.0,
      y: 24.0,
      width: 40.0,
      height: 36.0,
      color: 'rgba(255,107,157,0.25)',
      labelColor: '#8b1a4a',
    },
    {
      id: 'chill',
      label: 'CHILL',
      x: 75.0,
      y: 24.0,
      width: 40.0,
      height: 36.0,
      color: 'rgba(77,208,225,0.25)',
      labelColor: '#00606e',
    },
    {
      id: 'snacks',
      label: 'SNACKS',
      x: 50.0,
      y: 76.0,
      width: 40.0,
      height: 36.0,
      color: 'rgba(255,167,38,0.30)',
      labelColor: '#6b3a00',
    },
  ],
  music: { url: null, label: 'Music coming soon' },
  worldSize: { width: 800, height: 500 },
};
