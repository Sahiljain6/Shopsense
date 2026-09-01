import { motion, AnimatePresence } from "framer-motion";

export default function ProductDetailModal({
  isOpen,
  onClose,
  product,
  buyLinks,
  highestMRP,
  lowestRate,
  formattedPrice,
  cartAdded,
  onAddToCart,
}) {
  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="modal-backdrop" onClick={onClose}>
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
            onClick={onClose}
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
                <span className="modal-stars">
                  {"★".repeat(Math.min(5, Math.floor(product.rating || 4)))}
                </span>
                <span className="modal-rating-text">
                  {product.rating ? `${product.rating.toFixed(1)} / 5.0 Rating` : "Top Rated"}
                </span>
              </div>

              {/* Price Rate Benchmark Card */}
              <div className="modal-price-card">
                <div className="price-benchmark-item">
                  <span className="benchmark-title">Launch MRP</span>
                  <span className="benchmark-val mrp">₹{highestMRP.toLocaleString("en-IN")}</span>
                </div>

                <div className="price-benchmark-item current">
                  <span className="benchmark-title">Current Price</span>
                  <span className="benchmark-val current">{formattedPrice}</span>
                </div>

                <div className="price-benchmark-item lowest">
                  <span className="benchmark-title">Lowest Deal Rate</span>
                  <span className="benchmark-val lowest">₹{lowestRate.toLocaleString("en-IN")}</span>
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
                    <span className="offer-text">
                      No Cost EMI starting at ₹{Math.ceil(product.price / 6).toLocaleString("en-IN")}/month
                    </span>
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
                  onClick={onAddToCart}
                >
                  {cartAdded ? "✓ Added to Cart!" : `Add to Cart — ${formattedPrice}`}
                </button>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
