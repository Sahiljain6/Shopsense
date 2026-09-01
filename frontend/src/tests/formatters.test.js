import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { formatINR, formatRatingStars, truncateText, generateBuyLinks, formatDiscountPercentage } from "../utils/formatters.js";

describe("Currency & String Formatters Unit Tests", () => {
  describe("formatINR", () => {
    it("formats thousands in Indian numbering system", () => {
      assert.equal(formatINR(1000), "₹1,000");
      assert.equal(formatINR(74999), "₹74,999");
    });

    it("formats lakhs and crores in Indian comma separation", () => {
      assert.equal(formatINR(150000), "₹1,50,000");
      assert.equal(formatINR(10000000), "₹1,00,00,000");
    });

    it("handles zero and non-numeric inputs gracefully", () => {
      assert.equal(formatINR(0), "₹0");
      assert.equal(formatINR(""), "₹0");
      assert.equal(formatINR(null), "₹0");
      assert.equal(formatINR(undefined), "₹0");
      assert.equal(formatINR("invalid"), "₹0");
    });

    it("parses string numbers correctly", () => {
      assert.equal(formatINR("4999"), "₹4,999");
    });
  });

  describe("formatRatingStars", () => {
    it("generates correct filled and empty stars for rating 4", () => {
      const result = formatRatingStars(4);
      assert.equal(result.filled, "★★★★");
      assert.equal(result.empty, "☆");
      assert.equal(result.score, "4.0");
    });

    it("floors fractional ratings for star representation but preserves precision in score", () => {
      const result = formatRatingStars(4.7);
      assert.equal(result.filled, "★★★★");
      assert.equal(result.empty, "☆");
      assert.equal(result.score, "4.7");
    });

    it("clamps negative and high ratings between 0 and max", () => {
      const low = formatRatingStars(-2);
      assert.equal(low.filled, "");
      assert.equal(low.empty, "☆☆☆☆☆");

      const high = formatRatingStars(10);
      assert.equal(high.filled, "★★★★★");
      assert.equal(high.empty, "");
    });

    it("defaults to 4 stars when rating is missing", () => {
      const def = formatRatingStars(null);
      assert.equal(def.filled, "★★★★");
      assert.equal(def.empty, "☆");
      assert.equal(def.score, "4.0");
    });
  });

  describe("truncateText", () => {
    it("returns unmodified text when below maxLen", () => {
      assert.equal(truncateText("Hello World", 20), "Hello World");
    });

    it("truncates and appends ellipsis when exceeding maxLen", () => {
      const truncated = truncateText("Sony WH-1000XM5 Wireless Industry Leading Noise Canceling Headphones", 20);
      assert.equal(truncated, "Sony WH-1000XM5 Wire…");
    });

    it("safely handles null and empty text", () => {
      assert.equal(truncateText(null), "");
      assert.equal(truncateText(""), "");
    });
  });

  describe("generateBuyLinks", () => {
    it("produces 3 major Indian e-commerce portal links", () => {
      const links = generateBuyLinks("iPhone 15 Pro");
      assert.equal(links.length, 3);
      assert.equal(links[0].store, "Amazon India");
      assert.equal(links[1].store, "Flipkart");
      assert.equal(links[2].store, "Croma");
    });

    it("properly URI encodes the product query in search URLs", () => {
      const links = generateBuyLinks("MacBook Air M2 & 16GB");
      assert.match(links[0].url, /MacBook%20Air%20M2%20%26%2016GB/);
      assert.match(links[1].url, /MacBook%20Air%20M2%20%26%2016GB/);
    });

    it("handles empty product name without throwing", () => {
      const links = generateBuyLinks("");
      assert.equal(links.length, 3);
      assert.equal(links[0].url, "https://www.amazon.in/s?k=");
    });
  });

  describe("formatDiscountPercentage", () => {
    it("computes accurate discount percentage between launch MRP and deal price", () => {
      assert.equal(formatDiscountPercentage(100000, 75000), 25);
      assert.equal(formatDiscountPercentage(2000, 1500), 25);
      assert.equal(formatDiscountPercentage(10000, 6667), 33);
    });

    it("returns 0 when deal price is equal to or higher than launch price", () => {
      assert.equal(formatDiscountPercentage(5000, 5000), 0);
      assert.equal(formatDiscountPercentage(5000, 6000), 0);
    });

    it("handles zero or invalid prices safely", () => {
      assert.equal(formatDiscountPercentage(0, 500), 0);
      assert.equal(formatDiscountPercentage(500, 0), 0);
      assert.equal(formatDiscountPercentage(null, undefined), 0);
    });
  });
});
