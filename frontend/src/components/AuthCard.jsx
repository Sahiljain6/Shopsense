import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { login, register, googleLogin, setToken, friendlyError } from "../api";

export default function AuthCard({ onLogin, onError }) {
  const [isRegister, setIsRegister] = useState(false);
  const [loading, setLoading] = useState(false);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    onError(null);
    setLoading(true);
    try {
      const payload = { email, password };
      if (isRegister && fullName) payload.full_name = fullName;
      const token = isRegister ? await register(payload) : await login(payload);
      setToken(token.access_token);
      onLogin();
    } catch (err) {
      onError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleGoogleLogin() {
    onError(null);
    setLoading(true);
    try {
      const token = await googleLogin();
      setToken(token.access_token);
      onLogin();
    } catch (err) {
      onError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="clean-auth-container">
      <motion.div
        className="clean-auth-card"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: "easeOut" }}
      >
        <div className="auth-logo-mark">
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2V22M2 12H22M4.92893 4.92893L19.0711 19.0711M4.92893 19.0711L19.0711 4.92893" stroke="#18181b" strokeWidth="2.2" strokeLinecap="round"/>
          </svg>
        </div>

        <h1 className="auth-title">
          Welcome to <span className="auth-title-bold">ShopSense</span>
        </h1>

        <div className="social-buttons-group">
          <button
            type="button"
            className="social-btn"
            onClick={handleGoogleLogin}
            disabled={loading}
          >
            <svg width="18" height="18" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
            </svg>
            <span>{loading ? "Signing in..." : "Continue with Google"}</span>
          </button>
        </div>

        <div className="auth-divider">
          <span>or</span>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <AnimatePresence>
            {isRegister && (
              <motion.div
                className="input-group"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
              >
                <label className="input-label">Full name</label>
                <input
                  className="clean-input"
                  type="text"
                  placeholder="Enter your full name"
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
              placeholder="Email address"
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
                placeholder="Password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <button
                type="button"
                className="password-toggle-btn"
                onClick={() => setShowPassword((prev) => !prev)}
              >
                {showPassword ? "👁️" : "🙈"}
              </button>
            </div>
          </div>

          <button className="auth-primary-btn" type="submit" disabled={loading}>
            {loading ? "Please wait..." : "Continue"}
          </button>
        </form>

        <div className="auth-footer-links">
          <button
            type="button"
            className="auth-link-btn"
            onClick={() => {
              setIsRegister((prev) => !prev);
              onError(null);
            }}
          >
            {isRegister
              ? "Already have an account? Log in"
              : "Don't have an account? Sign up"}
          </button>
        </div>
      </motion.div>
    </div>
  );
}
