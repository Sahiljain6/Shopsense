export default function ClarificationPrompt({ text }: { text: string }) {
  return (
    <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 shadow-sm">
      <p className="mb-1 font-semibold">A quick clarification would help</p>
      <p>{text}</p>
    </div>
  );
}
