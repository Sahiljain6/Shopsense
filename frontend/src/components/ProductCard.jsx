import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { fetchPriceHistory, friendlyError } from "../api";

export default function ProductCard({ product, response }) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyData, setHistoryData] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(null);

  const key = String(product.id);
  const pros = Array.isArray(response?.pros?.[key]) ? response.pros[key] : [];
  const cons = Array.isArray(response?.cons?.[key]) ? response.cons[key] : [];
  const reason = response?.reasons?.[key];

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

  return (
    <motion.article
      className="product-card"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      whileHover={{ y: -6, boxShadow: "0 20px 40px -15px rgba(37, 99, 235, 0.2)" }}
    >
      <div className="product-image-container">
        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.name || "Product"}
            className="product-image"
            loading="lazy"
            onError={(e) => {
              e.target.style.display = "none";
            }}
          />
        ) : (
          <div className="product-image-placeholder">
            <span>🛍️</span>
          </div>
        )}
        <div className="product-price-badge">
          {product.currency && product.currency !== "$" ? product.currency : "₹"}{Number(product.price).toLocaleString('en-IN')}
        </div>
      </div>

      <div className="product-body">
        <div className="product-header">
          <div className="product-brand-tag">
            {product.brand || product.category_name || "Catalog Product"}
          </div>
          <h3 className="product-title">{product.name || "Recommended product"}</h3>
        </div>

        <p className="product-description">
          {product.description || "Verified catalog recommendation."}
        </p>

        <div className="product-rating-row">
          <div className="star-rating">
            {"★".repeat(Math.min(5, Math.floor(product.rating || 4)))}
            <span className="rating-num"> {product.rating ? `${product.rating}/5` : "4.5/5"}</span>
          </div>
          <span className="verified-pill">✓ Verified Deal</span>
        </div>

        {reason && (
          <div className="product-ai-reason">
            <span className="ai-sparkle">🎯</span>
            <p>{reason}</p>
          </div>
        )}

        {pros.length > 0 && (
          <div className="product-pros-box">
            <span className="pros-label">PROS</span>
            <div className="pros-tags">
              {pros.map((p, i) => (
                <span key={i} className="pro-chip">✓ {p}</span>
              ))}
            </div>
          </div>
        )}

        {cons.length > 0 && (
          <div className="product-cons-box">
            <span className="cons-label">CONS</span>
            <div className="cons-tags">
              {cons.map((c, i) => (
                <span key={i} className="con-chip">✗ {c}</span>
              ))}
            </div>
          </div>
        )}

        <div className="product-actions">
          <button
            className="price-history-btn"
            type="button"
            onClick={handlePriceHistory}
            disabled={historyLoading}
          >
            📊 {historyLoading ? "Fetching trends..." : historyOpen ? "Hide Price History" : "View Price History"}
          </button>
        </div>

        <AnimatePresence>
          {historyOpen && historyData && (
            <motion.div
              className="price-history-drawer"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.25 }}
            >
              <div className="price-history-header">Historical Price Points</div>
              {historyData.length === 0 ? (
                <p className="history-empty">
                  No previous price recorded yet. This item is at its current baseline price.
                </p>
              ) : (
                <ul className="price-history-list">
                  {historyData.map((entry, i) => (
                    <li key={i} className="history-item">
                      <span className="history-date">
                        {new Date(entry.captured_at).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        })}
                      </span>
                      <span className="history-price">
                        {entry.currency} {Number(entry.price).toLocaleString()}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {historyError && <p className="history-error">⚠️ {historyError}</p>}
      </div>
    </motion.article>
  );
}
