import { useState, useCallback, useEffect } from "react";
import { getToken, clearToken } from "./api";
import Hero from "./components/Hero";
import ErrorBanner from "./components/ErrorBanner";
import AuthModal from "./components/AuthModal";
import ChatPanel from "./components/ChatPanel";

export default function App() {
  const [authed, setAuthed] = useState(Boolean(getToken()));
  const [error, setError] = useState(null);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authModalMode, setAuthModalMode] = useState("signin");

  useEffect(() => {
    const handleAuthExpired = () => {
      setAuthed(false);
      setShowAuthModal(true);
      setAuthModalMode("signin");
    };
    window.addEventListener("auth-expired", handleAuthExpired);
    return () => window.removeEventListener("auth-expired", handleAuthExpired);
  }, []);

  const handleOpenAuth = useCallback((mode = "signin") => {
    setAuthModalMode(mode);
    setShowAuthModal(true);
    setError(null);
  }, []);

  const handleCloseAuth = useCallback(() => {
    setShowAuthModal(false);
  }, []);

  const handleLogin = useCallback(() => {
    setAuthed(true);
    setError(null);
    setShowAuthModal(false);
  }, []);

  const handleLogout = useCallback(() => {
    clearToken();
    setAuthed(false);
    setError(null);
  }, []);

  const handleError = useCallback((msg) => {
    setError(msg);
  }, []);

  const handleClearError = useCallback(() => {
    setError(null);
  }, []);

  return (
    <main className="app-shell ambient-mode-active">
      <div className="ambient-stage" aria-hidden="true">
        <div className="ambient-stage-glow ambient-glow-top" />
        <div className="ambient-stage-glow ambient-glow-bottom" />
        <div className="ambient-stage-grid" />
      </div>
      <section className="app-container">
        <Hero
          authed={authed}
          onLogout={handleLogout}
          onOpenAuth={handleOpenAuth}
        />
        <ErrorBanner message={error} />
        <ChatPanel
          onError={handleError}
          onClearError={handleClearError}
          isLoggedIn={authed}
          onOpenAuth={handleOpenAuth}
        />
      </section>

      {/* Lightweight Auth Modal Overlay */}
      <AuthModal
        isOpen={showAuthModal}
        initialMode={authModalMode}
        onClose={handleCloseAuth}
        onLogin={handleLogin}
        onError={handleError}
      />
    </main>
  );
}
