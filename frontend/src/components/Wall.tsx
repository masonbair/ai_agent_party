import type { Wall as WallType } from '../api/types';

type Props = { wall: WallType };

export default function Wall({ wall }: Props) {
  return (
    <div
      data-testid="wall"
      style={{
        position: 'absolute',
        left: `${wall.x}%`,
        top: `${wall.y}%`,
        width: `${wall.width}%`,
        height: `${wall.height}%`,
        background: wall.color,
        pointerEvents: 'none',
      }}
    />
  );
}
