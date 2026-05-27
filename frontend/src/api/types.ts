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

// Observe event types

export type ActorKind = 'human' | 'agent';

export interface ActorRef {
  actor_id: string;
  actor_username: string;
  actor_kind: ActorKind;
}

export interface JoinEvent extends ActorRef {
  type: 'join';
  seq: number;
  x: number;
  y: number;
  zone: string | null;
  at: number;
  room_wide?: boolean;
}

export interface LeaveEvent extends ActorRef {
  type: 'leave';
  seq: number;
  at: number;
  room_wide?: boolean;
}

export interface MoveEvent extends ActorRef {
  type: 'move';
  seq: number;
  x: number;
  y: number;
  zone?: string | null;
  at: number;
  room_wide?: boolean;
}

export interface ChatEvent extends ActorRef {
  type: 'chat';
  seq: number;
  text: string;
  at: number;
  room_wide?: boolean;
}

export interface ReactionEvent extends ActorRef {
  type: 'reaction';
  seq: number;
  emoji: string;
  expires_at: number;
  at: number;
  room_wide?: boolean;
}

export interface ApiError {
  error: string;
  message: string;
  // Optional context — varies by error code.
  allowed_colors?: string[];
  allowed_widths?: string[];
  allowed_emojis?: string[];
  fields?: Array<{ field: string | null; message: string }>;
  // Any extra context provided by the server.
  [key: string]: unknown;
}

export interface ApiErrorResponse {
  detail: ApiError;
}

/**
 * Full module state. When the requesting participant is NOT inside the
 * module's `interactionRect`, the server omits `notes`/`strokes`/`vote`
 * (proximity-scoped observe). Consumers should treat these as optional.
 */
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
      /** Only present when requester is inside the module's interactionRect. */
      notes?: StickyNote[];
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
      /** Only present when requester is inside the module's interactionRect. */
      strokes?: Stroke[];
      /** Only present when requester is inside the module's interactionRect. */
      vote?: { votes: number; needed: number };
    };

// All event types gain an optional room_wide flag (default false when absent).
export interface BaseEvent {
  seq: number;
  at: number;
  room_wide?: boolean;
}

/**
 * One-shot snapshot emitted when the requester walks into proximity of another
 * participant or into a module's interactionRect. Not repeated on the next poll
 * without further movement.
 */
export interface ProximitySnapshotEvent extends BaseEvent {
  type: 'proximity_snapshot';
  entered: { kind: 'module' | 'participant'; id: string };
  /** Full module snapshot (notes/strokes/vote). Present when entered.kind === 'module'. */
  module?: ModuleSnapshot | null;
  /** Recent chats from the participant. Present when entered.kind === 'participant'. */
  recent_chat?: ChatEvent[] | null;
}

/**
 * Emitted when the requester walks out of a participant's proximity radius
 * or out of a module's interactionRect.
 */
export interface ProximityLeftEvent extends BaseEvent {
  type: 'proximity_left';
  left: { kind: 'module' | 'participant'; id: string };
}

export type MusicTrackId =
  | 'lofi-loop'
  | 'jazz-club'
  | 'synthwave'
  | 'ambient-1'
  | 'party-mix';

export const MUSIC_TRACK_IDS: ReadonlyArray<MusicTrackId> = [
  'lofi-loop',
  'jazz-club',
  'synthwave',
  'ambient-1',
  'party-mix',
];

export type MusicAction = 'play' | 'pause' | 'skip' | 'set_volume';

export type MusicState = {
  track_id: MusicTrackId | null;
  playing: boolean;
  volume: number;
  since: number | null;
};

export type MusicChangedEvent = {
  type: 'music_changed';
  seq: number;
  track_id: MusicTrackId;
  playing: boolean;
  volume: number;
  at: number;
  actor_id: string | null;
  actor_username: string | null;
  actor_kind: 'human' | 'agent' | null;
  room_wide: true;
};
