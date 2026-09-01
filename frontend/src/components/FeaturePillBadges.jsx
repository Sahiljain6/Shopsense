export default function FeaturePillBadges() {
  const pills = [
    { icon: "⚡", label: "22 Stacks" },
    { icon: "🎯", label: "Deal Radar" },
    { icon: "💳", label: "Live EMI" },
  ];

  return (
    <nav className="navbar-center-links" aria-label="Feature Highlights">
      {pills.map((pill) => (
        <span key={pill.label} className="nav-feature-pill">
          {pill.icon} {pill.label}
        </span>
      ))}
    </nav>
  );
}
