import { POPULAR_PROMPTS } from "../utils/constants";

export default function WelcomePromptGrid({ onSelectPrompt }) {
  return (
    <div className="chat-welcome-state fastshot-welcome-card">
      <div className="welcome-brand-mark">
        <svg width="32" height="32" viewBox="0 0 34 34">
          <circle cx="17" cy="17" r="17" fill="#9C86CE" />
          <circle cx="17" cy="17" r="8.6" fill="#FFFFFF" />
          <circle cx="17" cy="17" r="3.7" fill="#151519" />
        </svg>
      </div>
      <h3 className="welcome-title">Describe a product. We'll find the best deal.</h3>
      <p className="welcome-desc">
        ShopSense AI connects live pricing, verified specs, EMI calculations, and delivery checks across India.
      </p>

      <div className="welcome-chips fastshot-prompts-grid">
        {POPULAR_PROMPTS.map((item) => (
          <button
            key={item.title}
            type="button"
            className="welcome-chip fastshot-hero-chip"
            onClick={() => onSelectPrompt(item.query)}
          >
            <span className="hero-chip-icon">{item.icon}</span>
            <div className="hero-chip-text">
              <span className="hero-chip-title">{item.title}</span>
              <span className="hero-chip-sub">{item.query}</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
