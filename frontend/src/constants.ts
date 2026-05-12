export const USERNAME_REGEX = /^[A-Za-z0-9]{2,20}$/;

export const ALLOWED_COLORS = [
  '#ff6b9d',
  '#9c27b0',
  '#4dd0e1',
  '#ffd54f',
  '#81c784',
  '#ff8a65',
  '#7986cb',
  '#f06292',
  '#4db6ac',
  '#ba68c8',
  '#ffb74d',
  '#a1887f',
] as const;

export type AllowedColor = (typeof ALLOWED_COLORS)[number];
