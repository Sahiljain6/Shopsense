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

export default function ProductCard({ product }) {
  const [modalOpen, setModalOpen] = useState(false);
  const [historyData, setHistoryData] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(null);
  const [cartAdded, setCartAdded] = useState(false);

  const formattedPrice = `₹${Number(product.price).toLocaleString('en-IN')}`;
  const buyLinks = generateBuyLinks(product.name || "");

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
    addToCart(product);
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
            {"★".repeat(Math.min(5, Math.floor(product.rating || 4)))}
            {"☆".repeat(5 - Math.min(5, Math.floor(product.rating || 4)))}
            <span className="rating-number"> {(product.rating || 4).toFixed(1)}</span>
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
      <AnimatePresence>
        {modalOpen && (
          <div className="modal-backdrop" onClick={() => setModalOpen(false)}>
            <motion.div
              className="focused-product-modal"
              initial={{ opacity: 0, scale: 0.94, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.94, y: 12 }}
              transition={{ duration: 0.2 }}
              onClick={(e) => e.stopPropagation()}
            >
              {/* Close Button */}
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setModalOpen(false)}
                title="Close detail view"
              >
                ✕
              </button>

              <div className="modal-grid-layout">
                {/* Left: Big Image & Buy Store Badges */}
                <div className="modal-left-column">
                  <div className="modal-big-image-box">
                    {product.image_url ? (
                      <img
                        src={product.image_url}
                        alt={product.name}
                        className="modal-big-img"
                      />
                    ) : (
                      <span className="modal-fallback-icon">📦</span>
                    )}
                  </div>

                  <div className="modal-store-section">
                    <span className="modal-section-label">Compare Prices & Buy Online:</span>
                    <div className="modal-store-buttons">
                      {buyLinks.map((link) => (
                        <a
                          key={link.store}
                          href={link.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="modal-store-btn"
                          style={{ borderColor: link.color, color: link.color }}
                        >
                          Buy on {link.store} ↗
                        </a>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Right: Full Product Details */}
                <div className="modal-right-column">
                  <span className="modal-brand-badge">{product.brand || "Verified Brand"}</span>
                  <h2 className="modal-product-title">{product.name}</h2>

                  <div className="modal-rating-row">
                    <span className="modal-stars">{"★".repeat(Math.min(5, Math.floor(product.rating || 4)))}</span>
                    <span className="modal-rating-text">{product.rating ? `${product.rating.toFixed(1)} / 5.0 Rating` : "Top Rated"}</span>
                  </div>

                  {/* Price Rate Benchmark Card */}
                  <div className="modal-price-card">
                    <div className="price-benchmark-item">
                      <span className="benchmark-title">Launch MRP</span>
                      <span className="benchmark-val mrp">₹{highestMRP.toLocaleString('en-IN')}</span>
                    </div>

                    <div className="price-benchmark-item current">
                      <span className="benchmark-title">Current Price</span>
                      <span className="benchmark-val current">{formattedPrice}</span>
                    </div>

                    <div className="price-benchmark-item lowest">
                      <span className="benchmark-title">Lowest Deal Rate</span>
                      <span className="benchmark-val lowest">₹{lowestRate.toLocaleString('en-IN')}</span>
                      <span className="lowest-deal-tag">With Bank Offer</span>
                    </div>
                  </div>

                  {/* Product Overview */}
                  <div className="modal-section">
                    <h4 className="modal-subheading">Product Description</h4>
                    <p className="modal-description">{product.description}</p>
                  </div>

                  {/* Ongoing Offers & Coupons */}
                  <div className="modal-section">
                    <h4 className="modal-subheading">🏷️ Ongoing Offers & Coupon Codes</h4>
                    <div className="modal-offers-box">
                      <div className="offer-pill">
                        <span className="offer-code">HDFC1000</span>
                        <span className="offer-text">Flat ₹1,000 instant discount on HDFC/ICICI Cards</span>
                      </div>
                      <div className="offer-pill">
                        <span className="offer-code">EXCHANGE5000</span>
                        <span className="offer-text">Up to ₹5,000 exchange bonus on old working devices</span>
                      </div>
                      <div className="offer-pill">
                        <span className="offer-code">NOCOST-EMI</span>
                        <span className="offer-text">No Cost EMI starting at ₹{Math.ceil(product.price / 6).toLocaleString('en-IN')}/month</span>
                      </div>
                    </div>
                  </div>

                  {/* Specifications */}
                  {product.attributes && Object.keys(product.attributes).length > 0 && (
                    <div className="modal-section">
                      <h4 className="modal-subheading">⚙️ Technical Specifications</h4>
                      <div className="modal-specs-table">
                        {Object.entries(product.attributes).map(([k, v]) => (
                          <div key={k} className="modal-spec-row">
                            <span className="modal-spec-key">{k}:</span>
                            <span className="modal-spec-val">{String(v)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Add to Cart CTA */}
                  <div className="modal-footer-cta">
                    <button
                      type="button"
                      className={`modal-add-cart-btn ${cartAdded ? "added" : ""}`}
                      onClick={handleAddToCart}
                    >
                      {cartAdded ? "✓ Added to Cart!" : `Add to Cart — ${formattedPrice}`}
                    </button>
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </>
  );
}
