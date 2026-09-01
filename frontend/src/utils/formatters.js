export function formatINR(amount) {
  const num = Number(amount) || 0;
  return `₹${num.toLocaleString("en-IN")}`;
}

export function formatRatingStars(rating, max = 5) {
  const score = Math.max(0, Math.min(max, Math.floor(rating || 4)));
  return {
    filled: "★".repeat(score),
    empty: "☆".repeat(max - score),
    score: (rating || 4).toFixed(1),
  };
}

export function truncateText(text, maxLen = 100) {
  if (!text || text.length <= maxLen) return text || "";
  return text.slice(0, maxLen).trim() + "…";
}

export function generateBuyLinks(productName) {
  const q = encodeURIComponent(productName || "");
  return [
    { store: "Amazon India", url: `https://www.amazon.in/s?k=${q}`, color: "#ff9900" },
    { store: "Flipkart", url: `https://www.flipkart.com/search?q=${q}`, color: "#2874f0" },
    { store: "Croma", url: `https://www.croma.com/searchB?q=${q}`, color: "#0f7d1c" },
  ];
}

export function formatDiscountPercentage(mrp, currentPrice) {
  const m = Number(mrp) || 0;
  const c = Number(currentPrice) || 0;
  if (m <= 0 || c <= 0 || m <= c) return 0;
  return Math.round(((m - c) / m) * 100);
}
