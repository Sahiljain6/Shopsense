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
          <span className="brand-name">ShopSense</span>
          <span className="live-indicator">
            <span className="live-pulse" />
            Live Catalog Index
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
            The AI Copilot for <span className="highlight-coral">Confident Buying.</span>
          </h1>
          <p className="hero-subtext">
            Grounded price comparisons, instant deal verification, and historical price intelligence across thousands of catalog items.
          </p>

          <div className="hero-metadata-strip">
            <span className="meta-tag">⚡ Live Deal Sync</span>
            <span className="meta-tag">🏷️ Price History Tracking</span>
            <span className="meta-tag">⚖️ Multi-Product Benchmark</span>
            <span className="meta-tag">📷 Visual Match</span>
          </div>
        </div>

        {/* Live commerce pulse mini widget */}
        <div className="hero-ticker-card">
          <div className="ticker-header">
            <span className="ticker-title">MARKET ACTIVITY</span>
            <span className="ticker-live-badge">REAL-TIME</span>
          </div>
          <div className="ticker-items">
            <div className="ticker-row">
              <span className="ticker-dot green" />
              <span className="ticker-name">Sony WH-1000XM5</span>
              <span className="ticker-price-drop">-$70.00</span>
            </div>
            <div className="ticker-row">
              <span className="ticker-dot blue" />
              <span className="ticker-name">MacBook Air M3</span>
              <span className="ticker-tag">Best Value</span>
            </div>
            <div className="ticker-row">
              <span className="ticker-dot amber" />
              <span className="ticker-name">Galaxy S24 Ultra</span>
              <span className="ticker-tag">Price Drop</span>
            </div>
          </div>
        </div>
      </div>
    </motion.header>
  );
}
