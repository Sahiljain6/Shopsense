import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

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

export default function Hero({ authed, onLogout }) {
  const [cartCount, setCartCount] = useState(getCartCount());
  const [cartOpen, setCartOpen] = useState(false);
  const [cartItems, setCartItems] = useState(getCart());

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

  const total = cartItems.reduce(
    (sum, item) => sum + (item.price || 0) * (item.qty || 1),
    0
  );

  return (
    <>
      <header className="shopsense-navbar">
        <div className="navbar-left">
          <div className="navbar-brand">
            <div className="brand-icon-box">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <path d="M4 7H20L18.5 17H5.5L4 7Z" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M9 7V5C9 3.89543 9.89543 3 11 3H13C14.1046 3 15 3.89543 15 5V7" stroke="#fff" strokeWidth="2.2" strokeLinecap="round"/>
              </svg>
            </div>
            <span className="brand-text">ShopSense</span>
          </div>
        </div>

        <div className="navbar-right">
          <button
            className="nav-cart-btn"
            type="button"
            onClick={() => { setCartItems(getCart()); setCartOpen((p) => !p); }}
            title={`Cart (${cartCount} items)`}
          >
            <span className="cart-icon">🛒</span>
            {cartCount > 0 && <span className="cart-badge">{cartCount}</span>}
          </button>

          {authed && (
            <button className="navbar-logout-btn" type="button" onClick={onLogout}>
              Log out
            </button>
          )}
        </div>
      </header>

      {/* ── CART DRAWER ── */}
      <AnimatePresence>
        {cartOpen && (
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
                <h3>Your Cart ({cartCount})</h3>
                <button type="button" onClick={() => setCartOpen(false)}>✕</button>
              </div>

              {cartItems.length === 0 ? (
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
                      onClick={() => alert(`Checkout total: ₹${Number(total).toLocaleString("en-IN")}\n\nThis is a demo — no payment will be processed.`)}
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
              )}
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
