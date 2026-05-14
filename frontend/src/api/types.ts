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
