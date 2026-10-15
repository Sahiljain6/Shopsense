import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const css = await readFile(new URL("../styles/precision.css", import.meta.url), "utf8");

describe("Precision Commerce presentation guardrails", () => {
  it("includes reduced-motion fallbacks for scroll reveals", () => {
    assert.match(css, /prefers-reduced-motion:\s*reduce/);
    assert.match(css, /\.ss-reveal-pending, \.ss-reveal-visible[\s\S]*?opacity: 1 !important/);
  });

  it("keeps the shared interaction transitions on transform and opacity", () => {
    assert.match(css, /transition-property: transform, opacity !important/);
    assert.doesNotMatch(css, /transition:\s*all\b/);
  });

  it("reserves image dimensions and includes mobile layouts", () => {
    assert.match(css, /\.product-card-top-row[\s\S]*?height: 152px/);
    assert.match(css, /@media \(max-width: 560px\)/);
  });
});
