import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const home = await readFile(new URL("../components/HomePage.jsx", import.meta.url), "utf8");
const styles = await readFile(new URL("../styles/homepage.css", import.meta.url), "utf8");
const app = await readFile(new URL("../App.jsx", import.meta.url), "utf8");
const header = await readFile(new URL("../components/Hero.jsx", import.meta.url), "utf8");

describe("ShopSense Figma-inspired homepage", () => {
  it("promotes the app's four implemented shopping capabilities", () => {
    for (const feature of ["AI PICKS", "LIVE RETAILER SEARCH", "PRODUCT COMPARISON", "BUDGET + CART"]) {
      assert.ok(home.includes(feature), `Expected homepage feature: ${feature}`);
    }
    assert.doesNotMatch(home, /LIVE PRICE ALERTS|guaranteed lowest price/i);
  });

  it("uses the reversible scroll milestones from the design handoff", () => {
    assert.match(home, /useScroll\(/);
    assert.match(home, /useMotionValueEvent\(/);
    assert.match(home, /\[0\.22, 0\.44, 0\.66, 0\.88\]/);
  });

  it("keeps the chat and sign-in actions connected to existing app handlers", () => {
    assert.match(app, /onEnterChat=\{handleEnterChat\}/);
    assert.match(header, /onClick=\{onEnterChat\}/);
    assert.match(home, /onOpenAuth\("signin"\)/);
  });

  it("includes responsive and reduced-motion fallbacks", () => {
    assert.match(styles, /@media \(max-width: 760px\)/);
    assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
    assert.match(styles, /\.ss-ticket[\s\S]*?opacity: 1 !important/);
  });
});
