import { useState, useEffect, useCallback } from "react";

const CART_KEY = "shopsense_cart";

export function getCartFromStorage() {
  try {
    return JSON.parse(localStorage.getItem(CART_KEY) || "[]");
  } catch {
    return [];
  }
}

export function saveCartToStorage(cart) {
  localStorage.setItem(CART_KEY, JSON.stringify(cart));
  window.dispatchEvent(new Event("cart-updated"));
}

export function addToCartStorage(product) {
  const current = getCartFromStorage();
  const existing = current.find((item) => item.id === product.id);
  let updated;
  if (existing) {
    updated = current.map((item) =>
      item.id === product.id ? { ...item, qty: (item.qty || 1) + 1 } : item
    );
  } else {
    updated = [
      ...current,
      {
        id: product.id,
        name: product.name,
        price: product.price,
        currency: product.currency || "₹",
        image_url: product.image_url,
        qty: 1,
      },
    ];
  }
  saveCartToStorage(updated);
  return updated;
}

export function useCart() {
  const [cartItems, setCartItems] = useState(getCartFromStorage());

  const refreshCart = useCallback(() => {
    setCartItems(getCartFromStorage());
  }, []);

  useEffect(() => {
    window.addEventListener("cart-updated", refreshCart);
    window.addEventListener("storage", refreshCart);
    return () => {
      window.removeEventListener("cart-updated", refreshCart);
      window.removeEventListener("storage", refreshCart);
    };
  }, [refreshCart]);

  const addToCart = useCallback((product) => {
    const current = getCartFromStorage();
    const existing = current.find((item) => item.id === product.id);
    let updated;
    if (existing) {
      updated = current.map((item) =>
        item.id === product.id ? { ...item, qty: (item.qty || 1) + 1 } : item
      );
    } else {
      updated = [
        ...current,
        {
          id: product.id,
          name: product.name,
          price: product.price,
          currency: product.currency || "₹",
          image_url: product.image_url,
          qty: 1,
        },
      ];
    }
    saveCartToStorage(updated);
    setCartItems(updated);
  }, []);

  const removeFromCart = useCallback((productId) => {
    const current = getCartFromStorage();
    const updated = current.filter((item) => item.id !== productId);
    saveCartToStorage(updated);
    setCartItems(updated);
  }, []);

  const updateQty = useCallback((productId, delta) => {
    const current = getCartFromStorage();
    const item = current.find((i) => i.id === productId);
    if (!item) return;
    const newQty = Math.max(1, (item.qty || 1) + delta);
    const updated = current.map((i) =>
      i.id === productId ? { ...i, qty: newQty } : i
    );
    saveCartToStorage(updated);
    setCartItems(updated);
  }, []);

  const clearCart = useCallback(() => {
    saveCartToStorage([]);
    setCartItems([]);
  }, []);

  const cartCount = cartItems.reduce((sum, item) => sum + (item.qty || 1), 0);
  const cartTotal = cartItems.reduce(
    (sum, item) => sum + (item.price || 0) * (item.qty || 1),
    0
  );

  return {
    cartItems,
    cartCount,
    cartTotal,
    addToCart,
    removeFromCart,
    updateQty,
    clearCart,
  };
}
