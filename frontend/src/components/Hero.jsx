import { motion } from "framer-motion";

export default function Hero({ authed, onLogout }) {
  return (
    <motion.header
      className="hero"
      initial={{ opacity: 0, y: -24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="hero-mesh-glow" />
      <div className="hero-content">
        <div className="hero-text-block">
          <div className="eyebrow-container">
            <span className="ai-badge">
              <span className="ai-badge-dot" />
              AI Shopping Copilot v2.0
            </span>
            <span className="model-badge">Live Intelligence</span>
          </div>

          <h1 className="hero-title">
            Shop Smarter. <span className="gradient-text">Save Faster.</span>
          </h1>

          <p className="hero-copy">
            Compare live prices, uncover hidden deals, trace price histories, and get grounded catalog recommendations powered by AI.
          </p>

          <div className="hero-feature-pills">
            <span className="feature-pill">⚡ Instant Comparison</span>
            <span className="feature-pill">🎯 Price Drop Tracking</span>
            <span className="feature-pill">📸 Visual Product Search</span>
            <span className="feature-pill">🔗 Smart Link Scraper</span>
          </div>
        </div>

        {authed && (
          <motion.button
            className="logout-button"
            type="button"
            onClick={onLogout}
            whileHover={{ scale: 1.04, y: -2 }}
            whileTap={{ scale: 0.96 }}
            title="Log out of your session"
          >
            <span className="logout-icon">⏻</span>
            <span>Log out</span>
          </motion.button>
        )}
      </div>
    </motion.header>
  );
}
