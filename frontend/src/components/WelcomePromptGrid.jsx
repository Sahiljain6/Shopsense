import { POPULAR_PROMPTS } from "../utils/constants";
import logoMarkUrl from "../assets/logo-mark.png";

export default function WelcomePromptGrid({ onSelectPrompt }) {
  return (
    <div className="chat-welcome-state fastshot-welcome-card">
      <div className="welcome-brand-mark">
        <img
          src={logoMarkUrl}
          alt="ShopSense"
          width="44"
          height="44"
          style={{
            height: "44px",
            width: "auto",
            objectFit: "contain",
            filter: "drop-shadow(0 2px 14px rgba(6, 182, 212, 0.5))",
          }}
        />
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
