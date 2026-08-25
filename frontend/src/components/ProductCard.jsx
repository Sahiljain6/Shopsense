import { useState, useCallback } from "react";
import { motion } from "framer-motion";
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
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      whileHover={{ y: -4, boxShadow: "0 12px 32px rgba(15,23,42,0.14)" }}
    >
      {product.image_url && (
        <img
          src={product.image_url}
          alt=""
          className="product-image"
          loading="lazy"
        />
      )}
      <div className="product-body">
        <div>
          <p className="product-brand">
            {product.brand || product.category_name || "ShopSense"}
          </p>
          <h3>{product.name || "Recommended product"}</h3>
        </div>
        <p className="product-description">
          {product.description || "No description available."}
        </p>
        <div className="product-meta">
          <span>
            {product.currency || "$"}
            {product.price}
          </span>
          <span className="rating">★ {product.rating || "N/A"}</span>
        </div>
        {reason && <p className="reason">{reason}</p>}
        {pros.length > 0 && <p className="pros">Pros: {pros.join(", ")}</p>}
        {cons.length > 0 && <p className="cons">Cons: {cons.join(", ")}</p>}
        <button
          className="link-button"
          type="button"
          onClick={handlePriceHistory}
          disabled={historyLoading}
        >
          {historyLoading ? "Loading…" : "View price history"}
        </button>
        {historyOpen && historyData && (
          <div className="price-history">
            {historyData.length === 0 ? (
              <p className="reason">
                No price history yet — this product hasn't been re-fetched over time.
              </p>
            ) : (
              <ul className="price-history-list">
                {historyData.map((entry, i) => (
                  <li key={i}>
                    {new Date(entry.captured_at).toLocaleDateString()} — {entry.currency} {entry.price}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        {historyError && <p className="cons">{historyError}</p>}
      </div>
    </motion.article>
  );
}
