import { useState, useEffect } from "react";
import { useCart } from "../hooks/useCart";
import CartDrawer from "./CartDrawer";

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
      <CartDrawer
        isOpen={Boolean(authed && cartOpen)}
        onClose={() => setCartOpen(false)}
        checkoutStep={checkoutStep}
        setCheckoutStep={setCheckoutStep}
        cartItems={cartItems}
        cartCount={cartCount}
        cartTotal={cartTotal}
        updateQty={updateQty}
        removeFromCart={removeFromCart}
        clearCart={clearCart}
        orderId={orderId}
        onSimulateRazorpay={handleSimulateRazorpay}
      />
    </>
  );
}
