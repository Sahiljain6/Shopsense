import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { login, register, googleLogin, setToken, friendlyError } from "../api";

const FIREFLIES = [
  { id: 1, x: "28%", y: "30%", size: 4, duration: 4.6, delay: 0 },
  { id: 2, x: "36%", y: "45%", size: 3, duration: 5.8, delay: 1.1 },
  { id: 3, x: "22%", y: "60%", size: 5, duration: 4.1, delay: 0.4 },
  { id: 4, x: "44%", y: "35%", size: 3, duration: 6.2, delay: 1.9 },
  { id: 5, x: "32%", y: "70%", size: 4, duration: 4.8, delay: 1.5 },
  { id: 6, x: "48%", y: "55%", size: 3, duration: 5.4, delay: 0.7 },
  { id: 7, x: "18%", y: "40%", size: 3.5, duration: 4.9, delay: 2.2 },
];

export default function AuthCard({ onLogin, onError }) {
  const [isRegister, setIsRegister] = useState(false);
  const [loading, setLoading] = useState(false);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  // Lamp animation states: "idle" | "loading" | "success" | "error"
  const [lampState, setLampState] = useState("idle");
  const [isCordPulled, setIsCordPulled] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    onError(null);
    setLoading(true);
    setLampState("loading");

    try {
      const payload = { email, password };
      if (isRegister && fullName) payload.full_name = fullName;
      const token = isRegister ? await register(payload) : await login(payload);
      setToken(token.access_token);
      setLampState("success");
      // Brief golden hold before transitioning
      setTimeout(() => {
        onLogin();
      }, 550);
    } catch (err) {
      setLampState("error");
      onError(friendlyError(err));
      setTimeout(() => {
        setLampState("idle");
      }, 1500);
    } finally {
      setLoading(false);
    }
  }

  async function handleGoogleLogin() {
    onError(null);
    setLoading(true);
    setLampState("loading");

    try {
      const token = await googleLogin();
      setToken(token.access_token);
      setLampState("success");
      setTimeout(() => {
        onLogin();
      }, 550);
    } catch (err) {
      setLampState("error");
      onError(friendlyError(err));
      setTimeout(() => {
        setLampState("idle");
      }, 1500);
    } finally {
      setLoading(false);
    }
  }

  function handleCordClick() {
    setIsCordPulled(true);
    setTimeout(() => setIsCordPulled(false), 350);
    if (lampState === "idle") {
      setLampState("loading");
      setTimeout(() => setLampState("idle"), 900);
    }
  }

  // Light cone animation variants based on real form state
  const coneVariants = {
    idle: {
      opacity: [0.45, 0.52, 0.46],
      scale: 1,
      transition: { duration: 4.5, repeat: Infinity, ease: "easeInOut" },
    },
    loading: {
      opacity: [0.7, 0.95, 0.8],
      scale: [1, 1.04, 1.02],
      transition: { duration: 1.2, repeat: Infinity, ease: "easeInOut" },
    },
    success: {
      opacity: 1,
      scale: 1.08,
      filter: "drop-shadow(0 0 45px rgba(251, 191, 36, 0.6))",
      transition: { duration: 0.35 },
    },
    error: {
      opacity: [0.6, 0.08, 0.65, 0.05, 0.45],
      transition: { duration: 0.85, ease: "easeInOut" },
    },
  };

  const bulbGlowVariants = {
    idle: {
      boxShadow: "0 0 35px 10px rgba(251, 191, 36, 0.4), 0 0 70px 25px rgba(245, 158, 11, 0.2)",
    },
    loading: {
      boxShadow: "0 0 55px 22px rgba(251, 191, 36, 0.75), 0 0 110px 45px rgba(245, 158, 11, 0.45)",
    },
    success: {
      boxShadow: "0 0 80px 30px rgba(251, 191, 36, 0.95), 0 0 140px 60px rgba(245, 158, 11, 0.6)",
    },
    error: {
      boxShadow: "0 0 15px 4px rgba(239, 68, 68, 0.3), 0 0 30px 8px rgba(245, 158, 11, 0.15)",
    },
  };

  return (
    <div className="lamp-auth-viewport">
      {/* Ambient background vignette and subtle table surface */}
      <div className="lamp-auth-backdrop" />

      {/* Floating firefly dust motes */}
      <div className="lamp-fireflies-container" aria-hidden="true">
        {FIREFLIES.map((f) => (
          <motion.span
            key={f.id}
            className="lamp-firefly"
            style={{
              width: f.size,
              height: f.size,
              left: f.x,
              top: f.y,
            }}
            animate={{
              x: [0, 10, -8, 0],
              y: [0, -16, 6, 0],
              opacity: lampState === "loading" ? [0.4, 0.95, 0.5] : [0.15, 0.55, 0.2],
            }}
            transition={{
              duration: f.duration,
              repeat: Infinity,
              ease: "easeInOut",
              delay: f.delay,
            }}
          />
        ))}
      </div>

      {/* Main Lamp + Glassmorphic Card Stage */}
      <div className="lamp-auth-stage">
        {/* Animated Desk Lamp Illustration */}
        <div className="lamp-illustration-box">
          <svg
            className="lamp-svg"
            viewBox="0 0 320 420"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <defs>
              {/* Warm light cone gradient */}
              <linearGradient id="coneGrad" x1="45%" y1="0%" x2="70%" y2="100%">
                <stop offset="0%" stopColor="#fffbeb" stopOpacity="0.85" />
                <stop offset="25%" stopColor="#fef08a" stopOpacity="0.45" />
                <stop offset="60%" stopColor="#f59e0b" stopOpacity="0.2" />
                <stop offset="100%" stopColor="#d97706" stopOpacity="0" />
              </linearGradient>

              {/* Lamp metal gradient */}
              <linearGradient id="metalGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#475569" />
                <stop offset="50%" stopColor="#1e293b" />
                <stop offset="100%" stopColor="#0f172a" />
              </linearGradient>

              {/* Gold reflector gradient inside shade */}
              <linearGradient id="goldReflect" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#fbbf24" />
                <stop offset="100%" stopColor="#d97706" />
              </linearGradient>
            </defs>

            {/* Light Cone projecting down onto the stage */}
            <motion.polygon
              points="168,132 232,158 360,420 80,420"
              fill="url(#coneGrad)"
              variants={coneVariants}
              animate={lampState}
              className="lamp-light-cone"
            />

            {/* Lamp Base (Weighted circular disc) */}
            <ellipse cx="68" cy="385" rx="42" ry="12" fill="#0f172a" />
            <ellipse cx="68" cy="380" rx="40" ry="10" fill="url(#metalGrad)" stroke="#64748b" strokeWidth="1.5" />
            <ellipse cx="68" cy="378" rx="22" ry="6" fill="#334155" />

            {/* Base Swivel Hinge */}
            <rect x="62" y="358" width="12" height="22" rx="3" fill="#1e293b" stroke="#64748b" strokeWidth="1.2" />
            <circle cx="68" cy="368" r="4.5" fill="#94a3b8" />

            {/* Lower Dual Cantilever Rods */}
            <line x1="64" y1="365" x2="108" y2="238" stroke="#334155" strokeWidth="3.5" strokeLinecap="round" />
            <line x1="72" y1="365" x2="116" y2="238" stroke="#475569" strokeWidth="3" strokeLinecap="round" />

            {/* Tension Spring detail */}
            <path
              d="M72,345 Q82,340 76,330 Q86,325 80,315 Q90,310 84,300 Q94,295 88,285 Q98,280 92,270"
              stroke="#64748b"
              strokeWidth="1.4"
              fill="none"
              strokeLinecap="round"
            />

            {/* Elbow Articulated Joint */}
            <circle cx="112" cy="235" r="9" fill="url(#metalGrad)" stroke="#94a3b8" strokeWidth="1.5" />
            <circle cx="112" cy="235" r="4" fill="#cbd5e1" />
            {/* Wing nut / knob */}
            <rect x="119" y="232" width="6" height="6" rx="1.5" fill="#94a3b8" />

            {/* Upper Arm Cantilever */}
            <line x1="112" y1="235" x2="182" y2="135" stroke="#334155" strokeWidth="3.5" strokeLinecap="round" />
            <line x1="117" y1="238" x2="187" y2="138" stroke="#475569" strokeWidth="2.5" strokeLinecap="round" />

            {/* Shade Neck Swivel */}
            <circle cx="184" cy="136" r="7" fill="#1e293b" stroke="#94a3b8" strokeWidth="1.2" />

            {/* Lamp Shade / Hood */}
            <path
              d="M178,130 L166,134 L154,142 L164,152 L224,176 L234,166 L202,126 L188,124 Z"
              fill="url(#metalGrad)"
              stroke="#64748b"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />

            {/* Golden Inner Reflector Rim */}
            <ellipse
              cx="195"
              cy="158"
              rx="36"
              ry="14"
              transform="rotate(22 195 158)"
              fill="url(#goldReflect)"
              stroke="#fef08a"
              strokeWidth="1"
            />

            {/* Incandescent Bulb inside shade */}
            <ellipse
              cx="198"
              cy="156"
              rx="11"
              ry="8"
              transform="rotate(22 198 156)"
              fill="#fffbeb"
              filter="drop-shadow(0 0 8px #fbbf24)"
            />
          </svg>

          {/* Interactive Hanging Pull-Cord */}
          <motion.div
            className="lamp-pull-cord"
            title="Click to pull cord"
            onClick={handleCordClick}
            animate={{
              y: isCordPulled ? 14 : 0,
            }}
            transition={{
              type: "spring",
              stiffness: 400,
              damping: 15,
            }}
          >
            <div className="cord-string" />
            <div className="cord-bead" />
          </motion.div>

          {/* Dynamic Bulb Glow Halo positioned right at the shade mouth */}
          <motion.div
            className="lamp-bulb-glow"
            variants={bulbGlowVariants}
            animate={lampState}
            transition={{ duration: 0.4 }}
          />
        </div>

        {/* Glassmorphic Auth Card */}
        <motion.div
          className="clean-auth-card lamp-glass-card"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, ease: "easeOut" }}
        >
          {/* Brand Header */}
          <div className="auth-card-header">
            <div className="auth-copilot-pill">
              <span className="auth-pill-glow">💡</span>
              <span className="auth-pill-text">AI Shopping Copilot</span>
            </div>

            <h1 className="auth-title">
              {isRegister ? "Create Account" : "Welcome Back"}
            </h1>
            <p className="auth-subtitle">
              {isRegister
                ? "Join ShopSense for real-time deals and AI advice"
                : "Sign in to access your wishlist, cart & personal assistant"}
            </p>
          </div>

          {/* Google One-Click Login */}
          <div className="social-buttons-group">
            <button
              type="button"
              className="social-btn glass-social-btn"
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
            <span>or with email</span>
          </div>

          {/* Email / Password Form */}
          <form className="auth-form" onSubmit={handleSubmit}>
            <AnimatePresence>
              {isRegister && (
                <motion.div
                  className="input-group"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.2 }}
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
              className="auth-primary-btn brand-blue-btn"
              type="submit"
              disabled={loading}
            >
              {loading ? (
                <span className="btn-loading-flex">
                  <span className="spinner-dot" />
                  Please wait...
                </span>
              ) : (
                isRegister ? "Create Account" : "Sign In"
              )}
            </button>
          </form>

          {/* Footer toggle button */}
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
                ? "Already have an account? Sign in"
                : "Don't have an account? Sign up"}
            </button>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
