import { motion } from "framer-motion";

export default function Hero({ authed, onLogout }) {
  return (
    <motion.header
      className="hero"
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="hero-content">
        <div>
          <p className="eyebrow">ShopSense</p>
          <h1>Your AI shopping copilot</h1>
          <p className="hero-copy">
            Paste a link, upload a photo, or just ask — get recommendations,
            price history, and comparisons.
          </p>
        </div>
        {authed && (
          <motion.button
            className="logout-button"
            type="button"
            onClick={onLogout}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            Log out
          </motion.button>
        )}
      </div>
    </motion.header>
  );
}
