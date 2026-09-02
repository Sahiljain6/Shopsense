import { useState, useCallback } from "react";
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
  const [ambientMode, setAmbientMode] = useState(() => {
    return localStorage.getItem("shopsense_ambient_mode") === "true";
  });

  const handleToggleAmbient = useCallback(() => {
    setAmbientMode((prev) => {
      const next = !prev;
      localStorage.setItem("shopsense_ambient_mode", String(next));
      return next;
    });
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
    <main className={`app-shell ${ambientMode ? "ambient-mode-active" : ""}`}>
      {ambientMode && (
        <div className="ambient-stage" aria-hidden="true">
          <video className="ambient-stage-video" autoPlay muted loop playsInline>
            <source src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260826_124724_bc041163-d651-425f-aea3-2acc1efc2c96.mp4" type="video/mp4" />
          </video>
          <div className="ambient-stage-overlay" />
        </div>
      )}
      <section className="app-container">
        <Hero
          authed={authed}
          onLogout={handleLogout}
          ambientMode={ambientMode}
          onToggleAmbient={handleToggleAmbient}
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
