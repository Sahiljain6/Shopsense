import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { fetchPriceHistory, friendlyError } from "../api";

const CART_KEY = "shopsense_cart";

function getCart() {
  try {
    return JSON.parse(localStorage.getItem(CART_KEY) || "[]");
  } catch {
    return [];
  }
}

function addToCart(product) {
  const cart = getCart();
  const existing = cart.find((item) => item.id === product.id);
  if (existing) {
    existing.qty += 1;
  } else {
    cart.push({
      id: product.id,
      name: product.name,
      price: product.price,
      currency: product.currency || "₹",
      image_url: product.image_url,
      qty: 1,
    });
  }
  localStorage.setItem(CART_KEY, JSON.stringify(cart));
  // Dispatch event so navbar can update cart badge
  window.dispatchEvent(new Event("cart-updated"));
  return cart;
}

function generateBuyLinks(productName) {
  const q = encodeURIComponent(productName);
  return [
    { store: "Amazon India", url: `https://www.amazon.in/s?k=${q}`, color: "#ff9900" },
    { store: "Flipkart", url: `https://www.flipkart.com/search?q=${q}`, color: "#2874f0" },
    { store: "Croma", url: `https://www.croma.com/searchB?q=${q}`, color: "#0f7d1c" },
  ];
}

export default function ProductCard({ product, response }) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [historyData, setHistoryData] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(null);
  const [cartAdded, setCartAdded] = useState(false);

  const formattedPrice = `₹${Number(product.price).toLocaleString('en-IN')}`;
  const buyLinks = generateBuyLinks(product.name || "");

  const handleViewDetails = useCallback(async () => {
    if (detailsOpen) {
      setDetailsOpen(false);
      return;
    }
    setDetailsOpen(true);
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
  }, [product.id, historyData, detailsOpen]);

  const handleAddToCart = () => {
    addToCart(product);
    setCartAdded(true);
    setTimeout(() => setCartAdded(false), 2000);
  };

  const cheapest = historyData && historyData.length > 0
    ? Math.min(...historyData.map((h) => h.price))
    : product.price;
  const highest = historyData && historyData.length > 0
    ? Math.max(...historyData.map((h) => h.price))
    : product.price;

  return (
    <div className="chat-product-card">
      {/* Product Image + Price Badge */}
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
        </div>
        <div className="product-card-price-tag">{formattedPrice}</div>
      </div>

      {/* Product Info */}
      <div className="product-card-content">
        <h4 className="product-card-title">{product.name || "Product"}</h4>
        <p className="product-card-feature-line">
          {product.description || "Quality product with verified specifications."}
        </p>

        <div className="product-card-rating-stars">
          {"★".repeat(Math.min(5, Math.floor(product.rating || 4)))}
          {"☆".repeat(5 - Math.min(5, Math.floor(product.rating || 4)))}
          <span className="rating-number"> {(product.rating || 4).toFixed(1)}</span>
        </div>

        {/* Buy Links — Indian Stores */}
        <div className="product-buy-links">
          {buyLinks.map((link) => (
            <a
              key={link.store}
              href={link.url}
              target="_blank"
              rel="noopener noreferrer"
              className="buy-link-chip"
              style={{ borderColor: link.color, color: link.color }}
            >
              {link.store} ↗
            </a>
          ))}
        </div>

        {/* Action Buttons */}
        <div className="product-card-actions-row">
          <button
            type="button"
            className="card-btn-secondary"
            onClick={handleViewDetails}
            disabled={historyLoading}
          >
            {historyLoading ? "Loading..." : detailsOpen ? "Hide Details" : "View Details"}
          </button>

          <button
            type="button"
            className={`card-btn-primary ${cartAdded ? "added" : ""}`}
            onClick={handleAddToCart}
          >
            {cartAdded ? "✓ Added!" : "Add to Cart"}
          </button>
        </div>

        {/* Expandable Details Drawer */}
        <AnimatePresence>
          {detailsOpen && (
            <motion.div
              className="card-details-drawer"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
            >
              {/* Price Insights */}
              <div className="drawer-section">
                <div className="drawer-header">💰 Price Insights</div>
                <div className="price-insights-grid">
                  <div className="price-insight-item">
                    <span className="insight-label">Current</span>
                    <span className="insight-value current">{formattedPrice}</span>
                  </div>
                  <div className="price-insight-item">
                    <span className="insight-label">Lowest</span>
                    <span className="insight-value low">₹{Number(cheapest).toLocaleString('en-IN')}</span>
                  </div>
                  <div className="price-insight-item">
                    <span className="insight-label">Highest</span>
                    <span className="insight-value high">₹{Number(highest).toLocaleString('en-IN')}</span>
                  </div>
                </div>
              </div>

              {/* Offers & Coupons */}
              <div className="drawer-section">
                <div className="drawer-header">🏷️ Ongoing Offers</div>
                <ul className="offers-list">
                  <li>🏦 10% off with HDFC/ICICI Bank Cards (up to ₹1,500)</li>
                  <li>📱 Exchange your old device for extra ₹2,000-₹5,000 off</li>
                  <li>🎁 No Cost EMI available from ₹{Math.ceil(product.price / 6).toLocaleString('en-IN')}/month</li>
                </ul>
              </div>

              {/* Specs */}
              {product.attributes && Object.keys(product.attributes).length > 0 && (
                <div className="drawer-section">
                  <div className="drawer-header">⚙️ Key Specifications</div>
                  <div className="specs-grid">
                    {Object.entries(product.attributes).map(([key, val]) => (
                      <div key={key} className="spec-row">
                        <span className="spec-key">{key}</span>
                        <span className="spec-val">{String(val)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Price History Timeline */}
              {historyData && historyData.length > 0 && (
                <div className="drawer-section">
                  <div className="drawer-header">📈 Price History</div>
                  <ul className="drawer-list">
                    {historyData.map((entry, i) => (
                      <li key={i}>
                        {new Date(entry.captured_at).toLocaleDateString('en-IN')} — ₹{Number(entry.price).toLocaleString('en-IN')}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {historyError && <p className="drawer-error">⚠️ {historyError}</p>}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
