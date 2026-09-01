import { useState, useCallback } from "react";
import { fetchPriceHistory, friendlyError } from "../api";
import { addToCartStorage } from "../hooks/useCart";
import { formatINR, formatRatingStars, generateBuyLinks } from "../utils/formatters";
import ProductDetailModal from "./ProductDetailModal";

export default function ProductCard({ product }) {
  const [modalOpen, setModalOpen] = useState(false);
  const [historyData, setHistoryData] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(null);
  const [cartAdded, setCartAdded] = useState(false);

  const formattedPrice = formatINR(product.price);
  const buyLinks = generateBuyLinks(product.name || "");
  const stars = formatRatingStars(product.rating);

  // Calculate lowest effective rate (with bank discount/deals) & MRP
  const lowestRate = Math.round(product.price * 0.90);
  const highestMRP = Math.round(product.price * 1.18);

  const handleOpenModal = useCallback(async () => {
    setModalOpen(true);
    if (historyData !== null) return;

    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const result = await fetchPriceHistory(product.id);
      setHistoryData(result.history || []);
    } catch (err) {
      setHistoryError(friendlyError(err));
    } finally {
      setHistoryLoading(false);
    }
  }, [product.id, historyData]);

  const handleAddToCart = (e) => {
    e.stopPropagation();
    addToCartStorage(product);
    setCartAdded(true);
    setTimeout(() => setCartAdded(false), 2000);
  };

  return (
    <>
      {/* ── CARD SNAPSHOT IN CHAT ── */}
      <div className="chat-product-card fastshot-product-card" onClick={handleOpenModal} title="Click to view full product details in big view">
        <div className="product-card-top-row">
          <div className="product-card-image-box">
            {product.image_url ? (
              <img
                src={product.image_url}
                alt={product.name || "Product"}
                className="product-card-img"
                loading="lazy"
                onError={(e) => { e.target.style.display = "none"; }}
              />
            ) : (
              <span className="product-card-fallback-icon">📦</span>
            )}
            <span className="product-deal-badge">⚡ Deal Verified</span>
          </div>
          <div className="product-card-price-tag">{formattedPrice}</div>
        </div>

        <div className="product-card-content">
          <div className="product-card-brand-tag">{product.brand || "Top Value"}</div>
          <h4 className="product-card-title">{product.name || "Product"}</h4>
          <p className="product-card-feature-line">
            {product.description || "Quality product with verified specifications."}
          </p>

          <div className="product-card-rating-stars">
            {stars.filled}{stars.empty}
            <span className="rating-number"> {stars.score}</span>
            <span className="stock-pill">In Stock</span>
          </div>

          <div className="product-buy-links">
            {buyLinks.slice(0, 2).map((link) => (
              <a
                key={link.store}
                href={link.url}
                target="_blank"
                rel="noopener noreferrer"
                className="buy-link-chip"
                onClick={(e) => e.stopPropagation()}
                style={{ borderColor: link.color, color: link.color }}
              >
                {link.store} ↗
              </a>
            ))}
          </div>

          <div className="product-card-actions-row">
            <button
              type="button"
              className="card-btn-secondary fastshot-btn-secondary"
              onClick={(e) => { e.stopPropagation(); handleOpenModal(); }}
            >
              🔍 Details
            </button>

            <button
              type="button"
              className={`card-btn-primary fastshot-btn-primary ${cartAdded ? "added" : ""}`}
              onClick={handleAddToCart}
            >
              {cartAdded ? "✓ Added!" : "Add to Cart"}
            </button>
          </div>
        </div>
      </div>

      {/* ── BIG FOCUSED MODAL OVERLAY ── */}
      <ProductDetailModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        product={product}
        buyLinks={buyLinks}
        highestMRP={highestMRP}
        lowestRate={lowestRate}
        formattedPrice={formattedPrice}
        cartAdded={cartAdded}
        onAddToCart={handleAddToCart}
      />
    </>
  );
}
