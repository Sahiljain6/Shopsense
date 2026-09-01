import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

import Logo from "./Logo";

const CART_KEY = "shopsense_cart";

function getCart() {
  try {
    return JSON.parse(localStorage.getItem(CART_KEY) || "[]");
  } catch {
    return [];
  }
}

function removeFromCart(productId) {
  const cart = getCart().filter((item) => item.id !== productId);
  localStorage.setItem(CART_KEY, JSON.stringify(cart));
  window.dispatchEvent(new Event("cart-updated"));
  return cart;
}

function updateQty(productId, delta) {
  const cart = getCart();
  const item = cart.find((i) => i.id === productId);
  if (item) {
    item.qty = Math.max(1, item.qty + delta);
  }
  localStorage.setItem(CART_KEY, JSON.stringify(cart));
  window.dispatchEvent(new Event("cart-updated"));
  return cart;
}

function clearCart() {
  localStorage.setItem(CART_KEY, "[]");
  window.dispatchEvent(new Event("cart-updated"));
}

function getCartCount() {
  return getCart().reduce((sum, item) => sum + (item.qty || 1), 0);
}

export default function Hero({ authed, onLogout, ambientMode = false, onToggleAmbient }) {
  const [cartCount, setCartCount] = useState(getCartCount());
  const [cartOpen, setCartOpen] = useState(false);
  const [cartItems, setCartItems] = useState(getCart());
  const [checkoutStep, setCheckoutStep] = useState("cart"); // "cart" | "checkout" | "success"
  const [orderId, setOrderId] = useState("");

  useEffect(() => {
    const handler = () => {
      setCartCount(getCartCount());
      setCartItems(getCart());
    };
    window.addEventListener("cart-updated", handler);
    window.addEventListener("storage", handler);
    return () => {
      window.removeEventListener("cart-updated", handler);
      window.removeEventListener("storage", handler);
    };
  }, []);

  // Close drawer immediately if user logs out
  useEffect(() => {
    if (!authed) {
      setCartOpen(false);
      setCheckoutStep("cart");
    }
  }, [authed]);

  const total = cartItems.reduce(
    (sum, item) => sum + (item.price || 0) * (item.qty || 1),
    0
  );

  const handleOpenCart = () => {
    setCartItems(getCart());
    setCheckoutStep("cart");
    setCartOpen(true);
  };

  const handleSimulateRazorpay = () => {
    const generatedId = `SS-2026-${Math.floor(100000 + Math.random() * 900000)}`;
    setOrderId(generatedId);
    clearCart();
    setCartItems([]);
    setCheckoutStep("success");
  };

  return (
    <>
      <header className="shopsense-navbar">
        <div className="navbar-left">
          <div className="navbar-brand">
            <Logo size={36} showWordmark={true} textColor="#ffffff" />
          </div>
        </div>

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
              className="nav-cart-btn"
              type="button"
              onClick={handleOpenCart}
              title={`Cart (${cartCount} items)`}
              aria-label="Shopping Cart"
            >
              <span className="cart-icon">🛒</span>
              {cartCount > 0 && <span className="cart-badge">{cartCount}</span>}
            </button>
          )}

          {authed && (
            <button className="navbar-logout-btn" type="button" onClick={onLogout}>
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
