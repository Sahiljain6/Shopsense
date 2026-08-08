"use client";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html>
      <body className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
        <div className="max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-lg">
          <h1 className="text-xl font-bold text-slate-950">ShopSense hit a snag</h1>
          <p className="mt-2 text-sm text-slate-600">{error.message || "Please try again."}</p>
          <button onClick={reset} className="mt-6 rounded-xl bg-blue-600 px-5 py-3 font-semibold text-white">Reload</button>
        </div>
      </body>
    </html>
  );
}
