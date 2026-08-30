import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { GoogleLogin } from "@react-oauth/google";
import { login, register, googleLogin, setToken, friendlyError } from "../api";
import logoMarkUrl from "../assets/logo-mark.png";

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

  // Separate lampOn boolean: controls lamp illumination & card presence
  const [lampOn, setLampOn] = useState(false);
  // Real form feedback state: "idle" | "loading" | "success" | "error"
  const [lampState, setLampState] = useState("idle");
  const [isCordPulled, setIsCordPulled] = useState(false);

  // Respect user's reduced motion preferences by turning lamp on immediately
  useEffect(() => {
    if (typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setLampOn(true);
    }
  }, []);

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

  async function handleGoogleSuccess(credentialResponse) {
    onError(null);
    setLoading(true);
    setLampState("loading");

    try {
      if (!credentialResponse?.credential) {
        throw new Error("No credential returned from Google sign-in.");
      }
      const token = await googleLogin(credentialResponse.credential);
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

  function handleGoogleError() {
    setLampState("error");
    onError("Google sign-in was cancelled or encountered an error. Please try again.");
    setTimeout(() => {
      setLampState("idle");
    }, 1500);
  }

  function handleCordClick() {
    if (loading) return; // Disallow toggling off mid-submission
    setIsCordPulled(true);
    setTimeout(() => setIsCordPulled(false), 350);

    setLampOn((prev) => {
      const next = !prev;
      if (!next) {
        setLampState("idle");
      }
      return next;
    });
  }

  // Light cone animation variants based on lampOn + form state
  const coneVariants = {
    off: {
      opacity: 0.02,
      scale: 0.96,
      transition: { duration: 0.35, ease: "easeOut" },
    },
    on: {
      opacity: [0.55, 0.68, 0.58],
      scale: 1,
      transition: { duration: 4.5, repeat: Infinity, ease: "easeInOut" },
    },
    loading: {
      opacity: [0.78, 1.0, 0.88],
      scale: [1, 1.05, 1.02],
      transition: { duration: 1.1, repeat: Infinity, ease: "easeInOut" },
    },
    success: {
      opacity: 1,
      scale: 1.08,
      filter: "drop-shadow(0 0 50px rgba(251, 191, 36, 0.7))",
      transition: { duration: 0.35 },
    },
    error: {
      opacity: [0.6, 0.08, 0.65, 0.05, 0.45],
      transition: { duration: 0.85, ease: "easeInOut" },
    },
  };

  const bulbGlowVariants = {
    off: {
      boxShadow: "0 0 0px 0px rgba(251, 191, 36, 0)",
      opacity: 0.08,
      transition: { duration: 0.35 },
    },
    on: {
      boxShadow: "0 0 35px 10px rgba(251, 191, 36, 0.45), 0 0 70px 25px rgba(245, 158, 11, 0.25)",
      opacity: 1,
      transition: { duration: 0.4 },
    },
    loading: {
      boxShadow: "0 0 60px 24px rgba(251, 191, 36, 0.85), 0 0 120px 50px rgba(245, 158, 11, 0.5)",
      opacity: 1,
      transition: { duration: 0.3 },
    },
    success: {
      boxShadow: "0 0 85px 35px rgba(251, 191, 36, 1), 0 0 150px 70px rgba(245, 158, 11, 0.7)",
      opacity: 1,
      transition: { duration: 0.3 },
    },
    error: {
      boxShadow: "0 0 15px 4px rgba(239, 68, 68, 0.3), 0 0 30px 8px rgba(245, 158, 11, 0.15)",
      opacity: 0.8,
      transition: { duration: 0.2 },
    },
  };

  const currentVariant = !lampOn ? "off" : (lampState === "idle" ? "on" : lampState);

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
              animate={currentVariant}
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
            className={`lamp-pull-cord ${!lampOn ? "lamp-cord-off" : "lamp-cord-on"}`}
            title={lampOn ? "Click pull-cord to turn off lamp" : "Click pull-cord to turn on lamp"}
            onClick={handleCordClick}
            role="button"
            tabIndex={0}
            aria-label={lampOn ? "Turn off lamp" : "Turn on lamp"}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                handleCordClick();
              }
            }}
            animate={{
              y: isCordPulled ? 16 : 0,
            }}
            transition={{
              type: "spring",
              stiffness: 450,
              damping: 14,
            }}
          >
            <div className="cord-string" />
            <motion.div
              className="cord-bead"
              animate={
                !lampOn
                  ? {
                      scale: [1, 1.3, 1],
                      boxShadow: [
                        "0 0 8px rgba(251, 191, 36, 0.6)",
                        "0 0 20px rgba(251, 191, 36, 1)",
                        "0 0 8px rgba(251, 191, 36, 0.6)",
                      ],
                    }
                  : { scale: 1 }
              }
              transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
            />
          </motion.div>

          {/* Dynamic Bulb Glow Halo positioned right at the shade mouth */}
          <motion.div
            className="lamp-bulb-glow"
            variants={bulbGlowVariants}
            animate={currentVariant}
            transition={{ duration: 0.4 }}
          />
        </div>

        {/* Screen-reader & keyboard navigation accessibility button */}
        {!lampOn && (
          <button
            type="button"
            className="sr-only-focusable"
            onClick={() => setLampOn(true)}
          >
            Show sign-in form
          </button>
        )}

        {/* Glassmorphic Auth Card or Off Hint */}
        <AnimatePresence mode="wait">
          {lampOn ? (
            <motion.div
              key="auth-glass-card"
              className="clean-auth-card lamp-glass-card"
              initial={{ opacity: 0, y: 26, scale: 0.98 }}
              animate={{
                opacity: 1,
                y: 0,
                scale: 1,
                transition: {
                  delay: 0.22, // ~220ms stagger after the lamp starts brightening
                  duration: 0.45,
                  ease: [0.22, 1, 0.36, 1],
                },
              }}
              exit={{
                opacity: 0,
                y: 18,
                scale: 0.98,
                transition: {
                  duration: 0.24,
                  ease: "easeIn",
                },
              }}
            >
              {/* Card top toolbar with toggle affordance */}
              <div className="auth-card-topbar">
                <button
                  type="button"
                  className="lamp-switch-toggle"
                  onClick={handleCordClick}
                  disabled={loading}
                  title="Switch lamp off"
                >
                  <span className="lamp-switch-icon">🌙</span>
                  <span className="lamp-switch-label">Turn off lamp</span>
                </button>
              </div>

              {/* Brand Header with New Logo */}
              <div className="auth-card-header">
                <div className="auth-copilot-pill">
                  <img
                    src={logoMarkUrl}
                    alt="ShopSense Mark"
                    width="22"
                    height="22"
                    style={{
                      height: "22px",
                      width: "auto",
                      objectFit: "contain",
                      filter: "drop-shadow(0 0 8px rgba(6, 182, 212, 0.7))",
                    }}
                  />
                  <span className="auth-pill-text">
                    <span style={{ fontWeight: 500 }}>shop</span>
                    <span style={{ fontWeight: 800 }}>sense</span>
                    <span style={{ color: "#06b6d4", fontWeight: 900 }}>•</span>
                    <span style={{ opacity: 0.75, marginLeft: "4px", fontSize: "11px", letterSpacing: "0.05em" }}>COPILOT</span>
                  </span>
                </div>

                <h1 className="auth-title">
                  {isRegister ? "Create Account" : "Welcome Back"}
                </h1>
                <p className="auth-subtitle">
                  {isRegister
                    ? "Join shopsense• for real-time deals and AI advice"
                    : "Sign in to access your wishlist, cart & personal assistant"}
                </p>
              </div>

          {/* Google Identity Services (GIS) Sign-In */}
          <div className="social-buttons-group google-gis-wrapper" style={{ display: "flex", justifyContent: "center", width: "100%", minHeight: "44px" }}>
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
                style={{ width: "300px", opacity: 0.85 }}
                onClick={() => onError("Google Sign-In is pending setup. Please set VITE_GOOGLE_CLIENT_ID in Vercel Environment Variables and redeploy.")}
              >
                <svg className="social-btn-icon" viewBox="0 0 24 24" width="18" height="18">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
                </svg>
                Continue with Google
              </button>
            )}
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
          ) : (
            <motion.div
              key="auth-off-hint"
              className="lamp-off-hint"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{
                opacity: 1,
                scale: 1,
                transition: { duration: 0.4, delay: 0.15 },
              }}
              exit={{
                opacity: 0,
                scale: 0.95,
                transition: { duration: 0.2 },
              }}
            >
              <button
                type="button"
                className="lamp-cord-cta-btn"
                onClick={handleCordClick}
              >
                <span className="cta-sparkle">💡</span>
                <span>Pull the cord to switch on & sign in</span>
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
