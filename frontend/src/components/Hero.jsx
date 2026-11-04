import { useState, useEffect } from "react";
import { useCart } from "../hooks/useCart";
import CartDrawer from "./CartDrawer";
import HeaderBrandMark from "./HeaderBrandMark";
import UserProfileMenu from "./UserProfileMenu";
import UiIcon from "./UiIcon";
import { apiFetch, friendlyError } from "../api.js";

export default function Hero({ authed, onLogout, onOpenAuth, onEnterChat }) {
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

  const [paymentLoading, setPaymentLoading] = useState(false);
  const [paymentError, setPaymentError] = useState("");

  // Close drawer immediately if user logs out.
  useEffect(() => {
    if (!authed) {
      setCartOpen(false);
      setCheckoutStep("cart");
    }
  }, [authed]);

  // The redirect query is only a hint. Confirm final status with the authenticated API.
  useEffect(() => {
    if (!authed || typeof window === "undefined") return undefined;

    const returnUrl = new URL(window.location.href);
    const paymentResult = returnUrl.searchParams.get("payment");
    const rawOrderId = returnUrl.searchParams.get("order_id");
    if (!["success", "failed"].includes(paymentResult) || !rawOrderId) return undefined;

    const parsedOrderId = Number(rawOrderId);
    if (!Number.isSafeInteger(parsedOrderId) || parsedOrderId <= 0) return undefined;

    let active = true;
    const clearPaymentReturnQuery = () => {
      returnUrl.searchParams.delete("payment");
      returnUrl.searchParams.delete("order_id");
      window.history.replaceState({}, "", returnUrl.pathname + returnUrl.search + returnUrl.hash);
    };

    apiFetch("/payments/orders/" + parsedOrderId, {
      method: "GET",
      retries: 0,
      timeoutMs: 10000,
      totalTimeoutMs: 15000,
    }).then((order) => {
      if (!active) return;
      setOrderId(String(order.id));
      setCartOpen(true);

      if (paymentResult === "success" && order.status === "paid" && order.payment_status === "paid") {
        clearCart();
        setCheckoutStep("success");
        setPaymentError("");
      } else {
        setCheckoutStep("checkout");
        setPaymentError("ShopSense did not confirm a successful payment. Your cart has been kept; you can retry checkout.");
      }
      clearPaymentReturnQuery();
    }).catch(() => {
      if (!active) return;
      setOrderId(String(parsedOrderId));
      setCartOpen(true);
      setCheckoutStep("checkout");
      setPaymentError("ShopSense could not verify the order status yet. Your cart has been kept; refresh the order status before retrying.");
      clearPaymentReturnQuery();
    });

    return () => {
      active = false;
    };
  }, [authed, clearCart]);

  const handleOpenCart = () => {
    setPaymentError("");
    setCheckoutStep("cart");
    setCartOpen(true);
  };

  const handleStartParbadPayment = async () => {
    if (paymentLoading || cartItems.length === 0) return;
    setPaymentError("");
    setPaymentLoading(true);

    try {
      const checkout = await apiFetch("/payments/checkout", {
        method: "POST",
        body: JSON.stringify({
          items: cartItems.map((item) => ({
            product_id: Number(item.id),
            quantity: Number(item.qty || 1),
          })),
        }),
        retries: 0,
        timeoutMs: 15000,
        totalTimeoutMs: 20000,
      });

      if (!checkout || typeof checkout.payment_url !== "string") {
        throw new Error("ShopSense did not return a valid payment link.");
      }

      const paymentUrl = new URL(checkout.payment_url, window.location.origin);
      if (!["http:", "https:"].includes(paymentUrl.protocol)) {
        throw new Error("ShopSense returned an unsupported payment URL.");
      }
      window.location.assign(paymentUrl.href);
    } catch (error) {
      setPaymentError(friendlyError(error));
    } finally {
      setPaymentLoading(false);
    }
  };

  return (
    <>
      <header className="shopsense-navbar fastshot-navbar">
        <div className="navbar-left">
          <div className="navbar-brand">
            <HeaderBrandMark size={32} />
          </div>
        </div>

        <nav className="navbar-center-links ss-header-links" aria-label="Main navigation">
          <button className="ss-header-link" type="button" onClick={onEnterChat}>
            Explore
          </button>
          <a className="ss-header-link" href="#shopsense-benefits">
            Compare
          </a>
          <a className="ss-header-link" href="#shopsense-how-it-works">
            How it works
          </a>
        </nav>

        <div className="navbar-right">
          {/* Cart is strictly gated on authed */}
          {authed && (
            <button
              className="nav-cart-btn fastshot-cart-pill"
              type="button"
              onClick={handleOpenCart}
              title={`Cart (${cartCount} items)`}
              aria-label="Shopping Cart"
            >
              <span className="cart-icon"><UiIcon name="shopping-cart" size={17} /></span>
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
        onStartParbadPayment={handleStartParbadPayment}
        paymentLoading={paymentLoading}
        paymentError={paymentError}
      />
    </>
  );
}
