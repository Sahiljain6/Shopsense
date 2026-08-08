"use client";

export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="mx-auto max-w-lg px-4 py-16 text-center">
      <h1 className="text-2xl font-bold text-slate-950">Something went wrong</h1>
      <p className="mt-2 text-sm text-slate-600">{error.message || "An unexpected error occurred."}</p>
      <button onClick={reset} className="mt-6 rounded-xl bg-blue-600 px-5 py-3 font-semibold text-white">Try again</button>
    </main>
  );
}
