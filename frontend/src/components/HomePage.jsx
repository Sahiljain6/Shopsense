import { useState, useEffect } from "react";
import UiIcon from "./UiIcon";

export default function HomePage({ onEnterChat, authed, onOpenAuth }) {
  const [scrollProgress, setScrollProgress] = useState(0);

  useEffect(() => {
    const handleScroll = () => {
      const totalScroll = document.documentElement.scrollHeight - document.documentElement.clientHeight;
      const currentScroll = window.scrollY;
      setScrollProgress((currentScroll / totalScroll) * 100);
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <div className="homepage-wrapper">
      <div className="scroll-progress-bar" style={{ width: `${scrollProgress}%` }} />

      <section className="home-hero-section">
        <div className="home-hero-badge">
          <span className="pulse-dot" />
          <span>AI Shopping Copilot for India • v2.4 Live</span>
        </div>
        <h1 className="home-hero-title">
          Smartest Price Comparison & <span className="gradient-text">AI Shopping Copilot</span>
        </h1>
        <p className="home-hero-subtitle">
          Compare live prices instantly across Amazon India, Flipkart, and Croma. Get grounded recommendations, EMI planners, and instant cart-aware assistance.
        </p>
        <div className="home-hero-cta-group">
          <button className="primary-enter-btn" onClick={onEnterChat}>
            <UiIcon name="message-square" size={18} />
            <span>Open AI Copilot Chat</span>
          </button>
          {!authed && (
            <button className="secondary-signin-btn" onClick={() => onOpenAuth("signin")}>
              Sign In / Register
            </button>
          )}
        </div>
      </section>

      <section className="home-ticker-section">
        <div className="ticker-header">
          <UiIcon name="zap" size={16} />
          <span>LIVE DEAL RADAR & PRICE DROPS</span>
        </div>
        <div className="ticker-track">
          <div className="ticker-item">?? Apple iPhone 15 (128GB) — ?64,990 (Flipkart Drop)</div>
          <div className="ticker-item">? Sony WH-1000XM5 — ?26,990 (Amazon Prime Deal)</div>
          <div className="ticker-item">?? Samsung Galaxy S24 Ultra — ?1,19,999 + No Cost EMI</div>
          <div className="ticker-item">?? Dell XPS 14 OLED — ?1,42,500 (Croma Exclusive)</div>
        </div>
      </section>

      <section className="home-features-section">
        <h2 className="section-title">Why ShopSense?</h2>
        <p className="section-subtitle">Engineered for Indian e-commerce with uncompromising precision.</p>
        
        <div className="features-grid">
          <div className="feature-card">
            <div className="feature-icon"><UiIcon name="scale" size={24} /></div>
            <h3>3-Store Price Comparison</h3>
            <p>Real-time scraping & API aggregation across Amazon, Flipkart, and Croma with instant benchmark diffs.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon"><UiIcon name="credit-card" size={24} /></div>
            <h3>No-Cost EMI & Financing</h3>
            <p>Month-by-month reducing balance amortization schedules and Razorpay IFSC validation.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon"><UiIcon name="shopping-cart" size={24} /></div>
            <h3>Cart-Aware Assistant</h3>
            <p>Your shopping cart syncs directly with the AI copilot so follow-up questions understand your items.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon"><UiIcon name="shield-check" size={24} /></div>
            <h3>Bank-Grade Security</h3>
            <p>Encrypted sessions, RBI-compliant Razorpay checkout gateway, and verified seller scoring.</p>
          </div>
        </div>
      </section>

      <footer className="enterprise-footer">
        <div className="footer-content">
          <div className="footer-col">
            <h4>ShopSense Technologies</h4>
            <p>The next-generation AI shopping copilot empowering smart buyers across India with transparent pricing and instant comparison.</p>
            <div className="footer-socials">
              <span>???? Made for India</span>
              <span>?? SSL Secured</span>
            </div>
          </div>
          <div className="footer-col">
            <h5>Legal & Compliance</h5>
            <a href="#privacy">Privacy Policy</a>
            <a href="#terms">Terms of Service</a>
            <a href="#grievance">Grievance Officer Redressal</a>
            <a href="#refund">Cancellation & Refund Policy</a>
          </div>
          <div className="footer-col">
            <h5>Trust & Safety</h5>
            <a href="#sec">Information Security</a>
            <a href="#compliance">RBI Payment Guidelines</a>
            <a href="#consumer">Consumer Rights & FAQ</a>
            <a href="#cookies">Cookie Preferences</a>
          </div>
          <div className="footer-col">
            <h5>Support & Contact</h5>
            <p>support@shopsense.ai</p>
            <p>Toll-free: 1800-SHOP-SENSE</p>
            <p>Mon - Sat: 9:00 AM - 8:00 PM IST</p>
          </div>
        </div>
        <div className="footer-bottom">
          <p>© 2026 ShopSense India Pvt. Ltd. All rights reserved. Compliant with IT Act 2000 and Consumer Protection (E-Commerce) Rules 2020.</p>
        </div>
      </footer>
    </div>
  );
}
