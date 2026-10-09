import { useEffect, useId, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import UiIcon from "./UiIcon";

export default function CartDrawer({
  isOpen,
  onClose,
  checkoutStep,
  setCheckoutStep,
  cartItems,
  cartCount,
  cartTotal,
  updateQty,
  removeFromCart,
  clearCart,
  orderId,
  onSimulateRazorpay,
}) {
  const drawerRef = useRef(null);
  const closeButtonRef = useRef(null);
  const onCloseRef = useRef(onClose);
  const titleId = useId();

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!isOpen) return undefined;

    const previouslyFocused = document.activeElement;
    const body = document.body;
    const root = document.documentElement;
    const previousBodyOverflow = body.style.overflow;
    const previousRootOverflow = root.style.overflow;
    const focusableSelector =
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

    body.style.overflow = "hidden";
    root.style.overflow = "hidden";
    closeButtonRef.current?.focus({ preventScroll: true });

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current?.();
        return;
      }
      if (event.key !== "Tab") return;

      const drawer = drawerRef.current;
      if (!drawer) return;
      const focusable = Array.from(drawer.querySelectorAll(focusableSelector))
        .filter((element) => element.getClientRects().length > 0);

      if (!focusable.length) {
        event.preventDefault();
        drawer.focus();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const focusOutside = !drawer.contains(document.activeElement);
      if (event.shiftKey && (document.activeElement === first || focusOutside)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || focusOutside)) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      body.style.overflow = previousBodyOverflow;
      root.style.overflow = previousRootOverflow;
      if (previouslyFocused?.isConnected) {
        previouslyFocused.focus({ preventScroll: true });
      }
    };
  }, [isOpen]);

  return (
    <AnimatePresence>
      {isOpen && (
      <>
      <motion.div
        key="cart-overlay"
        className="cart-overlay"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      />
      <motion.div
        key="cart-drawer"
        ref={drawerRef}
        className="cart-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        initial={{ x: "100%" }}
        animate={{ x: 0 }}
        exit={{ x: "100%" }}
        transition={{ type: "spring", damping: 28, stiffness: 300 }}
      >
        <div className="cart-drawer-header">
          <h3 id={titleId}>
            {checkoutStep === "cart" && `Your Cart (${cartCount})`}
            {checkoutStep === "checkout" && "Demo Checkout"}
            {checkoutStep === "success" && "Order Confirmed!"}
          </h3>
          <button ref={closeButtonRef} type="button" onClick={onClose} aria-label="Close cart">
            <UiIcon name="x" size={18} />
          </button>
        </div>

        {/* STEP 1: CART ITEMS VIEW */}
        {checkoutStep === "cart" &&
          (cartItems.length === 0 ? (
            <div className="cart-empty-state">
              <span className="cart-empty-icon"><UiIcon name="shopping-cart" size={42} strokeWidth={1.5} /></span>
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
                      <button type="button" onClick={() => updateQty(item.id, -1)} aria-label={`Decrease quantity of ${item.name}`}>
                        −
                      </button>
                      <span className="cart-item-qty">{item.qty}</span>
                      <button type="button" onClick={() => updateQty(item.id, 1)} aria-label={`Increase quantity of ${item.name}`}>
                        +
                      </button>
                      <button
                        type="button"
                        className="cart-remove-btn"
                        onClick={() => removeFromCart(item.id)}
                        title="Remove"
                        aria-label={`Remove ${item.name} from cart`}
                      >
                        <UiIcon name="trash" size={15} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              <div className="cart-total-section">
                <div className="cart-total-row">
                  <span>Subtotal</span>
                  <span className="cart-total-amount">
                    ₹{Number(cartTotal).toLocaleString("en-IN")}
                  </span>
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
                  onClick={clearCart}
                >
                  Clear Cart
                </button>
              </div>
            </>
          ))}

        {/* STEP 2: DEMO CHECKOUT & RAZORPAY PREVIEW */}
        {checkoutStep === "checkout" && (
          <div className="checkout-view-container">
            <div className="checkout-summary-card">
              <div className="checkout-badge-pill"><UiIcon name="zap" size={13} /> Razorpay Test Mode</div>
              <p className="checkout-demo-description">
                This is a live sandbox preview for the ShopSense demo. Transactions are simulated with no real charge.
              </p>

              <div className="checkout-breakdown">
                <div className="checkout-breakdown-row">
                  <span>Items ({cartCount})</span>
                  <span>₹{Number(cartTotal).toLocaleString("en-IN")}</span>
                </div>
                <div className="checkout-breakdown-row">
                  <span>Express Delivery</span>
                  <span className="checkout-free-tag">FREE</span>
                </div>
                <div className="checkout-breakdown-divider" />
                <div className="checkout-breakdown-row checkout-total-emphasis">
                  <span>Total Due</span>
                  <span className="cart-total-amount">
                    ₹{Number(cartTotal).toLocaleString("en-IN")}
                  </span>
                </div>
              </div>
            </div>

            <div className="cart-total-section">
              <button
                type="button"
                className="cart-checkout-btn checkout-pay-btn"
                onClick={onSimulateRazorpay}
              >
                <UiIcon name="zap" size={15} /> Pay with Razorpay (₹{Number(cartTotal).toLocaleString("en-IN")})
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
            <div className="checkout-success-icon"><UiIcon name="check-circle" size={48} strokeWidth={1.5} /></div>
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
              onClick={onClose}
            >
              Continue Shopping
            </button>
          </div>
        )}
      </motion.div>
      </>
      )}
    </AnimatePresence>
  );
}
