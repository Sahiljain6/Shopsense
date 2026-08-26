import { useState, useEffect } from "react";

const CART_KEY = "shopsense_cart";

function getCartCount() {
  try {
    const cart = JSON.parse(localStorage.getItem(CART_KEY) || "[]");
    return cart.reduce((sum, item) => sum + (item.qty || 1), 0);
  } catch {
    return 0;
  }
}

export default function Hero({ authed, onLogout }) {
  const [cartCount, setCartCount] = useState(getCartCount());

  useEffect(() => {
    const handler = () => setCartCount(getCartCount());
    window.addEventListener("cart-updated", handler);
    window.addEventListener("storage", handler);
    return () => {
      window.removeEventListener("cart-updated", handler);
      window.removeEventListener("storage", handler);
    };
  }, []);

  return (
    <header className="shopsense-navbar">
      <div className="navbar-left">
        <div className="navbar-brand">
          <div className="brand-icon-box">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M4 7H20L18.5 17H5.5L4 7Z" stroke="#ffffff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M9 7V5C9 3.89543 9.89543 3 11 3H13C14.1046 3 15 3.89543 15 5V7" stroke="#ffffff" strokeWidth="2.2" strokeLinecap="round"/>
            </svg>
          </div>
          <span className="brand-text">ShopSense</span>
        </div>
      </div>

      <div className="navbar-right">
        <div className="nav-cart-box" title={`Cart (${cartCount} items)`}>
          <span className="cart-icon">🛒</span>
          <span className="cart-badge">{cartCount}</span>
        </div>

        {authed && (
          <button
            className="navbar-logout-btn"
            type="button"
            onClick={onLogout}
            title="Log out"
          >
            Log out
          </button>
        )}
      </div>
    </header>
  );
}
