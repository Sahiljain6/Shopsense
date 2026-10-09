import { motion, useReducedMotion } from "framer-motion";
import { POPULAR_PROMPTS } from "../utils/constants";
import logoMarkUrl from "../assets/logo-mark.png";
import UiIcon from "./UiIcon";

const CATEGORY_TAGS = {
  "Best Earbuds": "Audio",
  "Compare Phones": "Mobile",
  "Mechanical Keyboard": "Hardware",
  "EMI Breakdown": "Finance",
};

export default function WelcomePromptGrid({ onSelectPrompt }) {
  const shouldReduceMotion = useReducedMotion();

  return (
    <div className="chat-welcome-state fastshot-welcome-card">
      <motion.div
        className="welcome-brand-mark"
        initial={shouldReduceMotion ? false : { scale: 0.96, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.22 }}
      >
        <img
          src={logoMarkUrl}
          alt="ShopSense"
          width="48"
          height="48"
          style={{
            height: "48px",
            width: "auto",
            objectFit: "contain",
          }}
        />
      </motion.div>

      <h3 className="welcome-title">
        Describe a product. <span className="welcome-title-accent">We'll find the best deal.</span>
      </h3>
      <p className="welcome-desc">
        ShopSense AI connects live pricing across Amazon, Flipkart & Croma, verified specifications, and instant EMI calculations for India.
      </p>

      <div className="welcome-chips fastshot-prompts-grid">
        {POPULAR_PROMPTS.map((item, index) => (
          <motion.button
            key={item.title}
            type="button"
            className="welcome-chip fastshot-hero-chip"
            onClick={() => onSelectPrompt(item.query)}
            initial={shouldReduceMotion ? false : { opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.18, delay: index * 0.035 }}
            whileHover={shouldReduceMotion ? undefined : { y: -2 }}
            whileTap={shouldReduceMotion ? undefined : { scale: 0.99 }}
          >
            <div className="hero-chip-top-row">
              <span className="hero-chip-icon"><UiIcon name={item.icon} size={22} strokeWidth={1.8} /></span>
              <span className="hero-chip-category-pill">
                {CATEGORY_TAGS[item.title] || "Shopping"}
              </span>
            </div>

            <div className="hero-chip-text">
              <span className="hero-chip-title">{item.title}</span>
              <span className="hero-chip-sub">{item.query}</span>
            </div>

            <div className="hero-chip-hover-arrow" aria-hidden="true">
              <span>Ask AI</span>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M5 12h14" />
                <path d="m12 5 7 7-7 7" />
              </svg>
            </div>
          </motion.button>
        ))}
      </div>
    </div>
  );
}

