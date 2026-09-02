import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { GoogleLogin } from "@react-oauth/google";
import { login, register, googleLogin, setToken, friendlyError } from "../api";
import logoMarkUrl from "../assets/logo-mark.png";

export default function AuthModal({
  isOpen,
  initialMode = "signin",
  onClose,
  onLogin,
  onError,
}) {
  const [mode, setMode] = useState(initialMode);
  const [loading, setLoading] = useState(false);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  // Sync mode whenever initialMode updates upon opening
  useEffect(() => {
    if (isOpen) {
      setMode(initialMode);
    }
  }, [isOpen, initialMode]);

  // Handle ESC key to dismiss modal
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && !loading) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, loading, onClose]);

  const isRegister = mode === "signup";

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget && !loading) {
      onClose();
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (loading) return;
    onError(null);
    setLoading(true);

    try {
      const payload = { email, password };
      if (isRegister && fullName) payload.full_name = fullName;

      const token = isRegister ? await register(payload) : await login(payload);
      setToken(token.access_token);
      onLogin();
      onClose();
    } catch (err) {
      onError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSuccess = async (credentialResponse) => {
    onError(null);
    setLoading(true);

    try {
      if (!credentialResponse?.credential) {
        throw new Error("No credential returned from Google sign-in.");
      }
      const token = await googleLogin(credentialResponse.credential);
      setToken(token.access_token);
      onLogin();
      onClose();
    } catch (err) {
      onError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleError = () => {
    onError("Google sign-in was cancelled or encountered an error. Please try again.");
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div
          className="auth-modal-backdrop"
          onClick={handleBackdropClick}
          role="dialog"
          aria-modal="true"
          aria-labelledby="auth-modal-title"
        >
          <motion.div
            className="auth-modal-card"
            initial={{ opacity: 0, scale: 0.94, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 16 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
          >
            {/* Close Button */}
            <button
              type="button"
              className="auth-modal-close-btn"
              onClick={onClose}
              disabled={loading}
              aria-label="Close auth dialog"
            >
              ✕
            </button>

            {/* Brand Header */}
            <div className="auth-modal-header">
              <div className="auth-modal-pill">
                <img
                  src={logoMarkUrl}
                  alt="ShopSense Mark"
                  width="20"
                  height="20"
                  style={{
                    height: "20px",
                    width: "auto",
                    objectFit: "contain",
                    filter: "drop-shadow(0 0 8px rgba(6, 182, 212, 0.7))",
                  }}
                />
                <span className="auth-modal-pill-text">
                  <span style={{ fontWeight: 500 }}>shop</span>
                  <span style={{ fontWeight: 800 }}>sense</span>
                  <span style={{ color: "#06b6d4", fontWeight: 900 }}>•</span>
                  <span
                    style={{
                      opacity: 0.75,
                      marginLeft: "4px",
                      fontSize: "10px",
                      letterSpacing: "0.05em",
                    }}
                  >
                    COPILOT
                  </span>
                </span>
              </div>

              <h2 id="auth-modal-title" className="auth-modal-title">
                {isRegister ? "Create Account" : "Welcome Back"}
              </h2>
              <p className="auth-modal-subtitle">
                {isRegister
                  ? "Join shopsense• for real-time deals and AI shopping assistance"
                  : "Sign in to access your cart, wishlist & personalized recommendations"}
              </p>
            </div>

            {/* Segmented Mode Tabs */}
            <div className="auth-modal-tabs" role="tablist">
              <button
                type="button"
                role="tab"
                aria-selected={!isRegister}
                className={`auth-tab-btn ${!isRegister ? "active" : ""}`}
                onClick={() => {
                  setMode("signin");
                  onError(null);
                }}
              >
                Sign In
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={isRegister}
                className={`auth-tab-btn ${isRegister ? "active" : ""}`}
                onClick={() => {
                  setMode("signup");
                  onError(null);
                }}
              >
                Create Account
              </button>
            </div>

            {/* Google OAuth */}
            <div className="auth-modal-social">
              {import.meta.env.VITE_GOOGLE_CLIENT_ID ? (
                <GoogleLogin
                  onSuccess={handleGoogleSuccess}
                  onError={handleGoogleError}
                  theme="filled_blue"
                  shape="pill"
                  text="continue_with"
                  width="300"
                />
              ) : (
                <button
                  type="button"
                  className="social-auth-btn google-btn"
                  style={{ width: "100%", maxWidth: "300px", opacity: 0.88 }}
                  onClick={() =>
                    onError(
                      "Google Sign-In is pending setup. Please set VITE_GOOGLE_CLIENT_ID in environment variables."
                    )
                  }
                >
                  <svg
                    className="social-btn-icon"
                    viewBox="0 0 24 24"
                    width="18"
                    height="18"
                  >
                    <path
                      fill="#4285F4"
                      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                    />
                    <path
                      fill="#34A853"
                      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                    />
                    <path
                      fill="#FBBC05"
                      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                    />
                    <path
                      fill="#EA4335"
                      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                    />
                  </svg>
                  Continue with Google
                </button>
              )}
            </div>

            <div className="auth-modal-divider">
              <span>or with email</span>
            </div>

            {/* Form */}
            <form className="auth-modal-form" onSubmit={handleSubmit}>
              <AnimatePresence>
                {isRegister && (
                  <motion.div
                    className="input-group"
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.18 }}
                  >
                    <label className="input-label">Full Name</label>
                    <input
                      className="clean-input"
                      type="text"
                      placeholder="e.g. Alex Kumar"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                    />
                  </motion.div>
                )}
              </AnimatePresence>

              <div className="input-group">
                <label className="input-label">Email address</label>
                <input
                  className="clean-input"
                  type="email"
                  placeholder="you@example.com"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>

              <div className="input-group">
                <label className="input-label">Password</label>
                <div className="password-input-wrapper">
                  <input
                    className="clean-input"
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  <button
                    type="button"
                    className="password-toggle-btn"
                    onClick={() => setShowPassword((prev) => !prev)}
                    title={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? "👁️" : "🙈"}
                  </button>
                </div>
              </div>

              <button
                className="auth-modal-submit-btn"
                type="submit"
                disabled={loading}
              >
                {loading ? (
                  <span className="btn-loading-flex">
                    <span className="spinner-dot" />
                    Please wait...
                  </span>
                ) : isRegister ? (
                  "Create Account"
                ) : (
                  "Sign In"
                )}
              </button>
            </form>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
