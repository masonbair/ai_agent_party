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
};

export type PartyConfig = {
  slug: string;
  name: string;
  description: string;
  theme: { floor: string; accent: string };
  zones: Zone[];
  music: { url: string | null; label: string };
  worldSize: { width: number; height: number };
};

export type PartiesListResponse = {
  parties: PartyConfig[];
};
