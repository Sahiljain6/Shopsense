import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useCart } from "../hooks/useCart";

export default function Hero({ authed, onLogout, ambientMode = false, onToggleAmbient }) {
  const { cartItems, cartCount, cartTotal, removeFromCart, updateQty, clearCart } = useCart();
  const [cartOpen, setCartOpen] = useState(false);
  const [checkoutStep, setCheckoutStep] = useState("cart"); // "cart" | "checkout" | "success"
  const [orderId, setOrderId] = useState("");

  // Close drawer immediately if user logs out
  useEffect(() => {
    if (!authed) {
      setCartOpen(false);
      setCheckoutStep("cart");
    }
  }, [authed]);

  const total = cartTotal;

  const handleOpenCart = () => {
    setCheckoutStep("cart");
    setCartOpen(true);
  };

  const handleSimulateRazorpay = () => {
    const generatedId = `SS-2026-${Math.floor(100000 + Math.random() * 900000)}`;
    setOrderId(generatedId);
    clearCart();
    setCheckoutStep("success");
  };

  return (
    <>
      <header className="shopsense-navbar fastshot-navbar">
        <div className="navbar-left">
          <div className="navbar-brand">
            <div className="fastshot-nav-brand">
              <svg className="fastshot-brand-mark" width="30" height="30" viewBox="0 0 34 34">
                <circle cx="17" cy="17" r="17" fill="#9C86CE"/>
                <circle cx="17" cy="17" r="8.6" fill="#FFFFFF"/>
                <circle cx="17" cy="17" r="3.7" fill="#151519"/>
              </svg>
              <div className="fastshot-brand-labels">
                <span className="fastshot-brand-title">ShopSense</span>
                <span className="fastshot-brand-sub">Fastshot AI Engine</span>
              </div>
            </div>
          </div>
        </div>

        <nav className="navbar-center-links">
          <span className="nav-feature-pill">⚡ 22 Stacks</span>
          <span className="nav-feature-pill">🎯 Deal Radar</span>
          <span className="nav-feature-pill">💳 Live EMI</span>
        </nav>

        <div className="navbar-right">
          {/* Ambient Video Mode Toggle */}
          <button
            className={`nav-ambient-btn ${ambientMode ? "active" : ""}`}
            type="button"
            onClick={onToggleAmbient}
            title={ambientMode ? "Disable Fastshot Cinematic Ambient Video" : "Enable Fastshot Cinematic Ambient Video"}
            aria-label="Toggle ambient background"
          >
            <span className="ambient-icon">{ambientMode ? "🌄" : "🏔️"}</span>
            <span className="ambient-text">Ambient</span>
          </button>

          {/* Cart is strictly gated on authed */}
          {authed && (
            <button
              className="nav-cart-btn fastshot-cart-pill"
              type="button"
              onClick={handleOpenCart}
              title={`Cart (${cartCount} items)`}
              aria-label="Shopping Cart"
            >
              <span className="cart-icon">🛒</span>
              <span className="cart-label">Cart</span>
              {cartCount > 0 && <span className="cart-badge">{cartCount}</span>}
            </button>
          )}

          {authed && (
            <button className="navbar-logout-btn fastshot-logout-btn" type="button" onClick={onLogout}>
              Log out
            </button>
          )}
        </div>
      </header>

      {/* ── CART DRAWER ── */}
      <AnimatePresence>
        {authed && cartOpen && (
          <>
            <motion.div
              className="cart-overlay"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setCartOpen(false)}
            />
            <motion.div
              className="cart-drawer"
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", damping: 28, stiffness: 300 }}
            >
              <div className="cart-drawer-header">
                <h3>
                  {checkoutStep === "cart" && `Your Cart (${cartCount})`}
                  {checkoutStep === "checkout" && "Demo Checkout"}
                  {checkoutStep === "success" && "Order Confirmed!"}
                </h3>
                <button type="button" onClick={() => setCartOpen(false)} aria-label="Close cart">✕</button>
              </div>

              {/* STEP 1: CART ITEMS VIEW */}
              {checkoutStep === "cart" && (
                cartItems.length === 0 ? (
                  <div className="cart-empty-state">
                    <span className="cart-empty-icon">🛒</span>
                    <p>Your cart is empty</p>
                    <p className="cart-empty-hint">Add products from chat recommendations</p>
                  </div>
                ) : (
                  <>
                    <div className="cart-items-list">
                      {cartItems.map((item) => (
                        <div key={item.id} className="cart-item-row">
                          <div className="cart-item-info">
                            <span className="cart-item-name">{item.name}</span>
                            <span className="cart-item-price">
                              ₹{Number(item.price * item.qty).toLocaleString("en-IN")}
                            </span>
                          </div>
                          <div className="cart-item-controls">
                            <button type="button" onClick={() => updateQty(item.id, -1)}>−</button>
                            <span className="cart-item-qty">{item.qty}</span>
                            <button type="button" onClick={() => updateQty(item.id, 1)}>+</button>
                            <button
                              type="button"
                              className="cart-remove-btn"
                              onClick={() => removeFromCart(item.id)}
                              title="Remove"
                            >
                              🗑️
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>

                    <div className="cart-total-section">
                      <div className="cart-total-row">
                        <span>Subtotal</span>
                        <span className="cart-total-amount">₹{Number(total).toLocaleString("en-IN")}</span>
                      </div>
                      <button
                        type="button"
                        className="cart-checkout-btn"
                        onClick={() => setCheckoutStep("checkout")}
                      >
                        Proceed to Checkout
                      </button>
                      <button
                        type="button"
                        className="cart-clear-btn"
                        onClick={() => { clearCart(); setCartItems([]); }}
                      >
                        Clear Cart
                      </button>
                    </div>
                  </>
                )
              )}

              {/* STEP 2: DEMO CHECKOUT & RAZORPAY PREVIEW */}
              {checkoutStep === "checkout" && (
                <div className="checkout-view-container">
                  <div className="checkout-summary-card">
                    <div className="checkout-badge-pill">⚡ Razorpay Test Mode</div>
                    <p className="checkout-demo-description">
                      This is a live sandbox preview for the ShopSense demo. Transactions are simulated with no real charge.
                    </p>

                    <div className="checkout-breakdown">
                      <div className="checkout-breakdown-row">
                        <span>Items ({cartCount})</span>
                        <span>₹{Number(total).toLocaleString("en-IN")}</span>
                      </div>
                      <div className="checkout-breakdown-row">
                        <span>Express Delivery</span>
                        <span className="checkout-free-tag">FREE</span>
                      </div>
                      <div className="checkout-breakdown-divider" />
                      <div className="checkout-breakdown-row checkout-total-emphasis">
                        <span>Total Due</span>
                        <span className="cart-total-amount">₹{Number(total).toLocaleString("en-IN")}</span>
                      </div>
                    </div>
                  </div>

                  <div className="cart-total-section">
                    <button
                      type="button"
                      className="cart-checkout-btn checkout-pay-btn"
                      onClick={handleSimulateRazorpay}
                    >
                      ⚡ Pay with Razorpay (₹{Number(total).toLocaleString("en-IN")})
                    </button>
                    <button
                      type="button"
                      className="cart-clear-btn"
                      onClick={() => setCheckoutStep("cart")}
                    >
                      ← Back to Cart
                    </button>
                  </div>
                </div>
              )}

              {/* STEP 3: ORDER CONFIRMED SUCCESS VIEW */}
              {checkoutStep === "success" && (
                <div className="checkout-success-view">
                  <div className="checkout-success-icon">🎉</div>
                  <h4>Order Placed Successfully!</h4>
                  <p className="checkout-order-code">
                    Order ID: <code>{orderId}</code>
                  </p>
                  <p className="checkout-success-hint">
                    Your demo order has been verified and registered. The cart has been cleared.
                  </p>

                  <button
                    type="button"
                    className="cart-checkout-btn"
                    onClick={() => {
                      setCartOpen(false);
                      setCheckoutStep("cart");
                    }}
                  >
                    Continue Shopping
                  </button>
                </div>
              )}
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
