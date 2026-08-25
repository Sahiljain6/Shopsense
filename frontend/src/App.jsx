import { useState, useCallback } from "react";
import { getToken, clearToken } from "./api";
import Hero from "./components/Hero";
import ErrorBanner from "./components/ErrorBanner";
import AuthCard from "./components/AuthCard";
import ChatPanel from "./components/ChatPanel";

export default function App() {
  const [authed, setAuthed] = useState(Boolean(getToken()));
  const [error, setError] = useState(null);

  const handleLogin = useCallback(() => {
    setAuthed(true);
    setError(null);
  }, []);

  const handleLogout = useCallback(() => {
    clearToken();
    setAuthed(false);
    setError(null);
  }, []);

  const handleError = useCallback((msg) => setError(msg), []);
  const handleClearError = useCallback(() => setError(null), []);

  return (
    <main className="app-shell">
      <section className="app-container">
        <Hero authed={authed} onLogout={handleLogout} />
        <ErrorBanner message={error} />
        {!authed ? (
          <AuthCard onLogin={handleLogin} onError={handleError} />
        ) : (
          <ChatPanel onError={handleError} onClearError={handleClearError} />
        )}
      </section>
    </main>
  );
}
