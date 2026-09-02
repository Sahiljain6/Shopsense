import { useState, useEffect } from "react";
import { useCart } from "../hooks/useCart";
import CartDrawer from "./CartDrawer";
import HeaderBrandMark from "./HeaderBrandMark";
import FeaturePillBadges from "./FeaturePillBadges";
import UserProfileMenu from "./UserProfileMenu";

export default function Hero({ authed, onLogout, ambientMode = false, onToggleAmbient, onOpenAuth }) {
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
            <HeaderBrandMark size={30} />
          </div>
        </div>

        <FeaturePillBadges />

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

          {!authed && onOpenAuth && (
            <div className="navbar-auth-actions">
              <button
                className="nav-signin-btn"
                type="button"
                onClick={() => onOpenAuth("signin")}
              >
                Sign In
              </button>
              <button
                className="nav-signup-btn fastshot-cta-btn"
                type="button"
                onClick={() => onOpenAuth("signup")}
              >
                <span>Sign Up</span>
              </button>
            </div>
          )}

          <UserProfileMenu authed={authed} onLogout={onLogout} />
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
