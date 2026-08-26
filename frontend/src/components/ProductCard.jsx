import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { fetchPriceHistory, friendlyError } from "../api";

export default function ProductCard({ product, response }) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyData, setHistoryData] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(null);
  const [addedToCart, setAddedToCart] = useState(false);

  const handlePriceHistory = useCallback(async () => {
    if (historyData !== null) {
      setHistoryOpen((prev) => !prev);
      return;
    }
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const result = await fetchPriceHistory(product.id);
      setHistoryData(result.history || []);
      setHistoryOpen(true);
    } catch (err) {
      setHistoryError(friendlyError(err));
    } finally {
      setHistoryLoading(false);
    }
  }, [product.id, historyData]);

  const handleAddToCart = () => {
    setAddedToCart(true);
    setTimeout(() => setAddedToCart(false), 2000);
  };

  const formattedPrice = `${product.currency && product.currency !== "$" ? product.currency : "₹"}${Number(product.price).toLocaleString('en-IN')}`;

  return (
    <div className="chat-product-card">
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
            <span className="product-card-fallback-icon">🎧</span>
          )}
        </div>
        <div className="product-card-price-tag">{formattedPrice}</div>
      </div>

      <div className="product-card-content">
        <h4 className="product-card-title">{product.name || "Recommended Product"}</h4>
        <p className="product-card-feature-line">
          {product.description || "Excellent ANC & battery performance."}
        </p>

        <div className="product-card-rating-stars">
          {"★".repeat(Math.min(5, Math.floor(product.rating || 5)))}
        </div>

        <div className="product-card-actions-row">
          <button
            type="button"
            className="card-btn-secondary"
            onClick={handlePriceHistory}
            disabled={historyLoading}
          >
            {historyLoading ? "Loading..." : historyOpen ? "Hide Specs" : "View Details"}
          </button>

          <button
            type="button"
            className="card-btn-primary"
            onClick={handleAddToCart}
          >
            {addedToCart ? "✓ Added" : "Add to Cart"}
          </button>
        </div>

        <AnimatePresence>
          {historyOpen && historyData && (
            <motion.div
              className="card-details-drawer"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
            >
              <div className="drawer-header">Price History & Specs</div>
              {historyData.length === 0 ? (
                <p className="drawer-empty">Current baseline price: {formattedPrice}</p>
              ) : (
                <ul className="drawer-list">
                  {historyData.map((entry, i) => (
                    <li key={i}>
                      {new Date(entry.captured_at).toLocaleDateString()} — {entry.currency} {Number(entry.price).toLocaleString()}
                    </li>
                  ))}
                </ul>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {historyError && <p className="drawer-error">⚠️ {historyError}</p>}
      </div>
    </div>
  );
}
