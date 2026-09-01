import { motion, AnimatePresence } from "framer-motion";

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
  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        className="cart-overlay"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
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
          <button type="button" onClick={onClose} aria-label="Close cart">
            ✕
          </button>
        </div>

        {/* STEP 1: CART ITEMS VIEW */}
        {checkoutStep === "cart" &&
          (cartItems.length === 0 ? (
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
                      <button type="button" onClick={() => updateQty(item.id, -1)}>
                        −
                      </button>
                      <span className="cart-item-qty">{item.qty}</span>
                      <button type="button" onClick={() => updateQty(item.id, 1)}>
                        +
                      </button>
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
              <div className="checkout-badge-pill">⚡ Razorpay Test Mode</div>
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
                ⚡ Pay with Razorpay (₹{Number(cartTotal).toLocaleString("en-IN")})
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
              onClick={onClose}
            >
              Continue Shopping
            </button>
          </div>
        )}
      </motion.div>
    </AnimatePresence>
  );
}
