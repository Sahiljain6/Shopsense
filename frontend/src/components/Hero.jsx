import { motion } from "framer-motion";

export default function Hero({ authed, onLogout }) {
  return (
    <motion.header
      className="hero-commerce"
      initial={{ opacity: 0, y: -16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="hero-top-bar">
        <div className="brand-group">
          <div className="brand-symbol">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M4 7H20L18.5 17H5.5L4 7Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M9 7V5C9 3.89543 9.89543 3 11 3H13C14.1046 3 15 3.89543 15 5V7" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              <circle cx="9" cy="20" r="1" fill="currentColor"/>
              <circle cx="15" cy="20" r="1" fill="currentColor"/>
            </svg>
          </div>
          <span className="brand-name">ShopSense India</span>
          <span className="live-indicator">
            <span className="live-pulse" />
            IN Catalog & Live Web Engine
          </span>
        </div>

        {authed && (
          <motion.button
            className="hero-logout-btn"
            type="button"
            onClick={onLogout}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            title="Log out"
          >
            <span>Log out</span>
          </motion.button>
        )}
      </div>

      <div className="hero-main-content">
        <div className="hero-copy-column">
          <h1 className="hero-headline">
            Smart AI Shopping Copilot for <span className="highlight-coral">India 🇮🇳</span>
          </h1>
          <p className="hero-subtext">
            Instant price discovery, grounded spec benchmarks, and deal recommendations across Amazon India, Flipkart, Croma, and verified catalog items.
          </p>

          <div className="hero-metadata-strip">
            <span className="meta-tag">🇮🇳 INR Price Discovery</span>
            <span className="meta-tag">⚡ Live Deal Sync</span>
            <span className="meta-tag">⚖️ Multi-Product Benchmark</span>
            <span className="meta-tag">📷 Visual Product Search</span>
          </div>
        </div>
      </div>
    </motion.header>
  );
}
