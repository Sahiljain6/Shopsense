const ACTIONS = [
  { icon: "⚡", label: "Today's Deals", query: "Find best deals on smartphones under 25000" },
  { icon: "⚖️", label: "Compare Specs", query: "Compare iPhone 15 vs OnePlus 12" },
  { icon: "💳", label: "EMI Calc", query: "Calculate EMI for ₹45,000 for 12 months at 12%" },
  { icon: "📍", label: "Pincode Check", query: "Check delivery to pincode 400001" },
];

export default function QuickActionsToolbar({ onSelectAction }) {
  return (
    <div className="composer-quick-strip" role="toolbar" aria-label="Quick Shopping Actions">
      {ACTIONS.map((action) => (
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
