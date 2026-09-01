import { QUICK_ACTIONS } from "../utils/constants";

export default function QuickActionsToolbar({ onSelectAction }) {
  return (
    <div className="composer-quick-strip" role="toolbar" aria-label="Quick Shopping Actions">
      {QUICK_ACTIONS.map((action) => (
        <button
          key={action.label}
          type="button"
          className="fastshot-chip"
          onClick={() => onSelectAction(action.query)}
        >
          <span className="chip-bullet">{action.icon}</span>
          <span>{action.label}</span>
        </button>
      ))}
    </div>
  );
}
