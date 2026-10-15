import React from "react";
import UiIcon from "./UiIcon";
import { formatINR } from "../utils/formatters";

function formatCheckedTime(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function LiveDealCard({ deal }) {
  const price = typeof deal.price === "number" && Number.isFinite(deal.price) ? deal.price : null;
  const oldPrice = typeof deal.old_price === "number" && Number.isFinite(deal.old_price) ? deal.old_price : null;
  const discount = typeof deal.discount_percentage === "number" ? deal.discount_percentage : null;
  const source = deal.source || "Google Shopping";
  const checkedTime = formatCheckedTime(deal.retrieved_at);

  return (
    <article className="chat-product-card fastshot-product-card live-deal-card">
      <div className="product-card-top-row">
        <div className="product-card-image-box">
          {deal.image_url ? (
            <img
              src={deal.image_url}
              alt={deal.title || "Product listing"}
              className="product-card-img"
              loading="lazy"
              decoding="async"
              width="160"
              height="160"
              referrerPolicy="no-referrer"
              onError={(event) => {
                event.currentTarget.style.display = "none";
              }}
            />
          ) : (
            <span className="product-card-fallback-icon">
              <UiIcon name="package" size={40} strokeWidth={1.5} />
            </span>
          )}
          <span className="product-deal-badge">
            <UiIcon name="zap" size={12} /> Live listing
          </span>
        </div>
        <div className="product-card-price-tag">
          {price === null ? "Price unavailable" : formatINR(price)}
        </div>
      </div>

      <div className="product-card-content">
        <div className="product-card-brand-tag">
          {source}
          {deal.is_verified ? " · Trusted retailer" : ""}
        </div>
        <h4 className="product-card-title">{deal.title || "Product listing"}</h4>

        {oldPrice !== null && price !== null && oldPrice > price && (
          <div className="live-deal-pricing-line">
            <span className="live-deal-old-price">{formatINR(oldPrice)}</span>
            {discount !== null && <span className="live-deal-discount">{Math.round(discount)}% lower than listed old price</span>}
          </div>
        )}

        <p className="product-card-feature-line">
          {deal.snippet || "Product listing from a live shopping search. Confirm the final price, delivery and seller terms at checkout."}
        </p>

        {(deal.rating !== null && deal.rating !== undefined) && (
          <div className="live-deal-rating">
            <span aria-hidden="true">★</span> {Number(deal.rating).toFixed(1)}
            {deal.reviews !== null && deal.reviews !== undefined && (
              <span> · {Number(deal.reviews).toLocaleString("en-IN")} reviews</span>
            )}
          </div>
        )}

        {!deal.is_verified && (
          <p className="live-deal-trust-note">
            {deal.warning || "Check the seller's return policy and warranty before buying."}
          </p>
        )}

        <div className="live-deal-actions">
          <a
            href={deal.url}
            target="_blank"
            rel="noopener noreferrer nofollow"
            className="live-deal-visit-link"
          >
            View at {source} <UiIcon name="arrow-up-right" size={14} />
          </a>
        </div>

        <p className="live-deal-freshness">
          {checkedTime ? `Fetched at ${checkedTime}` : "Live search result"} · Checkout price may change
        </p>
      </div>
    </article>
  );
}

export default React.memo(LiveDealCard);
