export type User = {
  session_id: string;
  username: string;
  color: string;
};

export type Zone = {
  id: string;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
  color: string;
  labelColor: string;
  borderColor: string;
};

export type Wall = {
  x: number;
  y: number;
  width: number;
  height: number;
  color: string;
};

export type Room = {
  clipPath: string | null;
  border: string;
  borderRadius?: number;
  walls: Wall[];
};

export type PartyConfig = {
  slug: string;
  name: string;
  description: string;
  theme: { floor: string; accent: string };
  zones: Zone[];
  music: { url: string | null; label: string };
  worldSize: { width: number; height: number };
  room: Room;
};

export type PartiesListResponse = {
  parties: PartyConfig[];
};

export type Participant = {
  id: string;
  kind: 'human' | 'agent';
  username: string;
  color: string;
  x: number;
  y: number;
};

export type ReactionEmoji =
  | '❤️'
  | '😂'
  | '👀'
  | '🎉'
  | '👍'
  | '👋'
  | '🤔'
  | '😮'
  | '🔥'
  | '✨'
  | '😴'
  | '🫶';

export const REACTION_EMOJI: ReadonlyArray<ReactionEmoji> = [
  '❤️',
  '😂',
  '👀',
  '🎉',
  '👍',
  '👋',
  '🤔',
  '😮',
  '🔥',
  '✨',
  '😴',
  '🫶',
];

export type LightingPreset = 'day' | 'dusk' | 'night' | 'party';

export type StickyNote = {
  id: string;
  module_id: string;
  author_id: string;
  author_kind: 'human' | 'agent';
  text: string;
  color: 'yellow' | 'pink' | 'blue' | 'green';
  x: number;
  y: number;
  created_at: number;
};

export type Stroke = {
  id: string;
  module_id: string;
  author_id: string;
  author_kind: 'human' | 'agent';
  color: string;
  width: 'thin' | 'med' | 'thick';
  points: { x: number; y: number }[];
  created_at: number;
};

export type ApproachSlot = { x: number; y: number; occupied: boolean };

export type ModuleSnapshot =
  | {
      id: string;
      kind: 'stickynotes';
      x: number;
      y: number;
      w: number;
      h: number;
      interactionRect: { x: number; y: number; w: number; h: number };
      approachSlots: ApproachSlot[];
      notes: StickyNote[];
    }
  | {
      id: string;
      kind: 'drawboard';
      x: number;
      y: number;
      w: number;
      h: number;
      interactionRect: { x: number; y: number; w: number; h: number };
      approachSlots: ApproachSlot[];
      strokes: Stroke[];
      vote: { votes: number; needed: number };
    };
