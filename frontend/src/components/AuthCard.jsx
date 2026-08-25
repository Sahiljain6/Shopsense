import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { login, register, setToken, friendlyError } from "../api";

export default function AuthCard({ onLogin, onError }) {
  const [isRegister, setIsRegister] = useState(false);
  const [loading, setLoading] = useState(false);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

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

  function toggleMode() {
    setIsRegister((prev) => !prev);
    onError(null);
  }

  return (
    <motion.section
      className="auth-card"
      initial={{ opacity: 0, y: 30, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
    >
      <h2>{isRegister ? "Create your account" : "Log in to continue"}</h2>
      <form className="stacked-form" onSubmit={handleSubmit}>
        <AnimatePresence>
          {isRegister && (
            <motion.input
              key="fullname"
              className="form-input"
              type="text"
              autoComplete="name"
              placeholder="Full name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.25 }}
            />
          )}
        </AnimatePresence>
        <input
          className="form-input"
          type="email"
          autoComplete="email"
          placeholder="Email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <input
          className="form-input"
          type="password"
          autoComplete="current-password"
          placeholder="Password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <motion.button
          className="primary-button full-width"
          type="submit"
          disabled={loading}
          whileHover={!loading ? { scale: 1.02 } : {}}
          whileTap={!loading ? { scale: 0.98 } : {}}
        >
          {loading ? "Please wait…" : isRegister ? "Register" : "Log in"}
        </motion.button>
      </form>
      <button className="link-button" type="button" onClick={toggleMode}>
        {isRegister
          ? "Already have an account? Log in"
          : "Need an account? Register"}
      </button>
    </motion.section>
  );
}
