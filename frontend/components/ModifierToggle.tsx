const modes = [
  { value: "compare", label: "Compare" },
  { value: "budget_optimizer", label: "Budget" },
  { value: "gift_mode", label: "Gift" },
  { value: "quick_answer", label: "Quick answer" },
];

export default function ModifierToggle({ mode, setMode }: { mode: string | null; setMode: (mode: string | null) => void }) {
  return (
    <div className="flex flex-wrap gap-2" aria-label="Shopping assistant mode">
      {modes.map((item) => {
        const active = mode === item.value;
        return (
          <button
            key={item.value}
            type="button"
            aria-pressed={active}
            onClick={() => setMode(active ? null : item.value)}
            className={`rounded-full border px-4 py-2 text-sm font-medium transition ${active ? "border-blue-600 bg-blue-600 text-white shadow" : "border-slate-200 bg-white text-slate-700 hover:border-blue-300 hover:text-blue-700"}`}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
