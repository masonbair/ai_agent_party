import { REACTION_EMOJI, type ReactionEmoji } from '../api/types';

type Props = {
  onSelect: (emoji: ReactionEmoji) => void;
  disabled: boolean;
};

export function ReactionPalette({ onSelect, disabled }: Props) {
  return (
    <div className="reaction-palette" role="toolbar" aria-label="Reactions">
      {REACTION_EMOJI.map((e) => (
        <button
          key={e}
          type="button"
          onClick={() => onSelect(e)}
          disabled={disabled}
          aria-label={`React with ${e}`}
        >
          {e}
        </button>
      ))}
    </div>
  );
}
