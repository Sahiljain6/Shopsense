import { useRef, useState } from "react";
import {
  motion,
  useMotionValueEvent,
  useReducedMotion,
  useScroll,
  useTransform,
} from "framer-motion";
import UiIcon from "./UiIcon";

const BENEFITS = [
  {
    id: "ai-picks",
    eyebrow: "01 / AI PICKS",
    title: "A shortlist built around you.",
    description:
      "Describe the product, budget, brand or use case. ShopSense turns your needs into focused recommendations.",
    icon: "zap",
    accent: "cyan",
    ticket: "AI",
    ticketTitle: "SMART PICKS",
    ticketDetail: "matched to you",
  },
  {
    id: "live-prices",
    eyebrow: "02 / LIVE RETAILER SEARCH",
    title: "See the market, not just one store.",
    description:
      "Explore current retailer listings with prices, images, ratings and store links when the source provides them.",
    icon: "tag",
    accent: "slate",
    ticket: "LIVE",
    ticketTitle: "LIVE PRICES",
    ticketDetail: "across retailers",
  },
  {
    id: "compare",
    eyebrow: "03 / PRODUCT COMPARISON",
    title: "Make the trade-offs clear.",
    description:
      "Compare products and specifications side by side, then get an explanation of what matters for your use case.",
    icon: "scale",
    accent: "amber",
    ticket: "VS",
    ticketTitle: "COMPARE",
    ticketDetail: "side by side",
  },
  {
    id: "budget",
    eyebrow: "04 / BUDGET + CART",
    title: "Plan the whole purchase.",
    description:
      "Explore EMI scenarios and ask follow-up questions with your shopping cart included as useful context.",
    icon: "credit-card",
    accent: "green",
    ticket: "₹",
    ticketTitle: "EMI PLAN",
    ticketDetail: "budget with context",
  },
];

const IMPACT_POINTS = [0.22, 0.44, 0.66, 0.88];

function BenefitTicket({ benefit, index, progress, reduceMotion }) {
  const start = [0.08, 0.3, 0.52, 0.74][index];
  const impact = IMPACT_POINTS[index];
  const settle = Math.min(1, impact + 0.06);

  const x = useTransform(
    progress,
    [start, impact, settle],
    [index % 2 === 0 ? -150 : 150, 0, 0]
  );
  const y = useTransform(progress, [start, impact, settle], [-210, 16, 0]);
  const rotate = useTransform(
    progress,
    [start, impact, settle],
    [index % 2 === 0 ? -12 : 12, index % 2 === 0 ? 3 : -3, 0]
  );
  const scale = useTransform(progress, [start, impact, settle], [0.76, 1.04, 0.86]);
  const opacity = useTransform(
    progress,
    [Math.max(0, start - 0.025), start, impact, settle],
    [0, 0.96, 1, 1]
  );

  const style = reduceMotion
    ? { x: 0, y: 0, rotate: 0, scale: 0.86, opacity: 1 }
    : { x, y, rotate, scale, opacity };

  return (
    <motion.article
      className={`ss-ticket ss-ticket--${benefit.accent}`}
      style={{ ...style, transformOrigin: "center bottom" }}
    >
      <span className="ss-ticket-eyebrow">{benefit.ticket}</span>
      <strong>{benefit.ticketTitle}</strong>
      <small>{benefit.ticketDetail}</small>
    </motion.article>
  );
}

function ShoppingCartArtwork({ progress, reduceMotion }) {
  return (
    <div className="ss-cart-visual" aria-label="ShopSense shopping cart illustration">
      <svg
        className="ss-cart-base"
        viewBox="0 0 640 270"
        role="img"
        aria-hidden="true"
      >
        <path
          d="M24 25H546Q556 25 552 38L514 164Q509 182 490 182H92Q74 182 68 164L27 39Q23 25 24 25Z"
          fill="#111b29"
        />
      </svg>

      <div className="ss-cart-ticket-layer" aria-hidden="true">
        {BENEFITS.map((benefit, index) => (
          <BenefitTicket
            key={benefit.id}
            benefit={benefit}
            index={index}
            progress={progress}
            reduceMotion={reduceMotion}
          />
        ))}
      </div>

      <svg
        className="ss-cart-foreground"
        viewBox="0 0 640 270"
        aria-hidden="true"
        focusable="false"
      >
        <path
          d="M22 25H548Q558 25 554 38L516 166Q511 186 490 186H92Q72 186 67 166L26 39"
          fill="none"
          stroke="#22d3ee"
          strokeWidth="9"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M548 25H610L569 193"
          fill="none"
          stroke="#22d3ee"
          strokeWidth="11"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {Array.from({ length: 12 }, (_, index) => (
          <rect
            key={index}
            x={72 + index * 40}
            y="52"
            width="18"
            height="40"
            rx="9"
            fill="#07090e"
          />
        ))}
        <text
          x="315"
          y="145"
          textAnchor="middle"
          fill="#67e8f9"
          fontSize="16"
          fontWeight="700"
          letterSpacing="2"
        >
          SMART FINDS INSIDE
        </text>
        <path
          d="M90 184L101 219H511"
          fill="none"
          stroke="#22d3ee"
          strokeWidth="10"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="132" cy="226" r="20" fill="#111b29" stroke="#22d3ee" strokeWidth="8" />
        <circle cx="484" cy="226" r="20" fill="#111b29" stroke="#22d3ee" strokeWidth="8" />
      </svg>
      <div className="ss-cart-shadow" aria-hidden="true" />
    </div>
  );
}

export default function HomePage({ onEnterChat, authed, onOpenAuth }) {
  const storyRef = useRef(null);
  const [collectedCount, setCollectedCount] = useState(0);
  const reduceMotion = useReducedMotion();
  const { scrollYProgress } = useScroll({
    target: storyRef,
    offset: ["start start", "end end"],
  });

  useMotionValueEvent(scrollYProgress, "change", (latest) => {
    const nextCount = IMPACT_POINTS.filter((point) => latest >= point).length;
    setCollectedCount((current) => (current === nextCount ? current : nextCount));
  });

  const visibleCount = reduceMotion ? 4 : collectedCount;

  return (
    <div className="ss-home-page">
      <motion.div className="ss-home-progress" style={{ scaleX: scrollYProgress }} aria-hidden="true" />

      <section className="ss-story" ref={storyRef} aria-label="Explore ShopSense">
        <div className="ss-story-sticky">
          <div className="ss-stage-inner">
            <div className="ss-hero-copy">
              <div className="ss-eyebrow">
                <span className="ss-eyebrow-dot" />
                <span>AI PICKS. BETTER BUYS.</span>
              </div>

              <h1 className="ss-hero-title">
                Shop smarter.
                <br />
                Spend better.
              </h1>

              <p className="ss-hero-description">
                AI-powered picks, live retailer prices and clear product comparisons—so your next buy feels right.
              </p>

              <div className="ss-hero-actions">
                <button className="ss-primary-action" type="button" onClick={onEnterChat}>
                  <span>Find my best match</span>
                  <UiIcon name="arrow-up-right" size={18} />
                </button>
                {!authed && onOpenAuth && (
                  <button
                    className="ss-secondary-action"
                    type="button"
                    onClick={() => onOpenAuth("signin")}
                  >
                    Sign in
                  </button>
                )}
              </div>
            </div>

            <div className="ss-scroll-cue" aria-hidden="true">
              <span className="ss-scroll-mouse"><span /></span>
              <span>Scroll. Collect. Choose.</span>
            </div>

            <div className="ss-collected-counter" aria-live="polite">
              <span className="ss-counter-value">{visibleCount}</span>
              <span className="ss-counter-copy">
                <strong>shopping tools explored</strong>
                <small>Four ways to shop with confidence.</small>
              </span>
            </div>

            <ShoppingCartArtwork progress={scrollYProgress} reduceMotion={reduceMotion} />

            <div className="ss-stage-footer">
              <span>SHOPSENSE / AI SHOPPING</span>
              <span>Smarter picks. Better buys.</span>
            </div>
          </div>
        </div>
      </section>

      <section className="ss-home-section ss-benefits-section" id="shopsense-benefits">
        <div className="ss-section-heading">
          <span className="ss-section-eyebrow">THE GOOD STUFF</span>
          <h2>Everything you need to buy with confidence.</h2>
          <p>
            One place to discover products, check the market and understand the trade-offs before you decide.
          </p>
        </div>

        <div className="ss-benefit-grid">
          {BENEFITS.map((benefit) => (
            <article className={`ss-benefit-card ss-benefit-card--${benefit.accent}`} key={benefit.id}>
              <div className="ss-benefit-card-top">
                <span className="ss-benefit-icon">
                  <UiIcon name={benefit.icon} size={22} strokeWidth={1.8} />
                </span>
                <span>{benefit.eyebrow}</span>
              </div>
              <h3>{benefit.title}</h3>
              <p>{benefit.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="ss-home-section ss-how-section" id="shopsense-how-it-works">
        <div className="ss-section-heading">
          <span className="ss-section-eyebrow">A BETTER WAY TO SHOP</span>
          <h2>From “I need this” to “this is the one.”</h2>
        </div>

        <div className="ss-steps-grid">
          <article className="ss-step">
            <span>01</span>
            <h3>Tell us what matters.</h3>
            <p>Share your budget, must-haves and what you plan to use the product for.</p>
          </article>
          <article className="ss-step">
            <span>02</span>
            <h3>Explore the options.</h3>
            <p>Review product matches, retailer listings and side-by-side comparisons.</p>
          </article>
          <article className="ss-step">
            <span>03</span>
            <h3>Choose with context.</h3>
            <p>Understand the trade-offs, plan the spend and keep useful products in your cart.</p>
          </article>
        </div>

        <div className="ss-final-cta">
          <div>
            <span className="ss-section-eyebrow">READY WHEN YOU ARE</span>
            <h2>Let's find your next great buy.</h2>
          </div>
          <button className="ss-primary-action" type="button" onClick={onEnterChat}>
            <span>Open ShopSense</span>
            <UiIcon name="arrow-up-right" size={18} />
          </button>
        </div>
      </section>

      <footer className="ss-home-footer">
        <span className="ss-footer-brand">ShopSense<span>•</span></span>
        <p>
          AI shopping assistance for better-informed purchases. Retailer listings are snapshots; confirm the final price and availability with the seller.
        </p>
        <span>© {new Date().getFullYear()} ShopSense</span>
      </footer>
    </div>
  );
}
