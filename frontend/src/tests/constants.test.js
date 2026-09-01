import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  CART_QUERIES,
  GREETING_QUERIES,
  URL_PATTERN,
  POPULAR_PROMPTS,
  QUICK_ACTIONS,
  AI_ENGINES,
} from "../utils/constants.js";

describe("System Constants & Schemas Unit Tests", () => {
  it("defines standard cart opening intent phrases", () => {
    assert.ok(Array.isArray(CART_QUERIES));
    assert.ok(CART_QUERIES.includes("cart"));
    assert.ok(CART_QUERIES.includes("view cart"));
    assert.ok(CART_QUERIES.includes("show my cart"));
  });

  it("defines standard greeting greetings phrases", () => {
    assert.ok(Array.isArray(GREETING_QUERIES));
    assert.ok(GREETING_QUERIES.includes("hi"));
    assert.ok(GREETING_QUERIES.includes("hello"));
    assert.ok(GREETING_QUERIES.includes("namaste"));
  });

  it("validates valid http and https URLs using URL_PATTERN", () => {
    assert.ok(URL_PATTERN.test("https://www.amazon.in/dp/B0CHX1W1XY"));
    assert.ok(URL_PATTERN.test("http://flipkart.com/item"));
    assert.ok(!URL_PATTERN.test("ftp://server.local"));
    assert.ok(!URL_PATTERN.test("best deals on laptops"));
  });

  it("ensures POPULAR_PROMPTS array satisfies the chip card schema", () => {
    assert.equal(POPULAR_PROMPTS.length, 4);
    for (const prompt of POPULAR_PROMPTS) {
      assert.ok(typeof prompt.icon === "string" && prompt.icon.length > 0);
      assert.ok(typeof prompt.title === "string" && prompt.title.length > 0);
      assert.ok(typeof prompt.query === "string" && prompt.query.length > 0);
    }
  });

  it("ensures QUICK_ACTIONS array satisfies toolbar chip schema", () => {
    assert.equal(QUICK_ACTIONS.length, 4);
    for (const action of QUICK_ACTIONS) {
      assert.ok(typeof action.icon === "string");
      assert.ok(typeof action.label === "string");
      assert.ok(typeof action.query === "string");
    }
  });

  it("ensures AI_ENGINES contains Sonnet 4.5, Gemini Flash, and Deal Specialist", () => {
    assert.equal(AI_ENGINES.length, 3);
    const engineIds = AI_ENGINES.map((e) => e.id);
    assert.deepEqual(engineIds, ["Sonnet 4.5", "Gemini Flash", "Deal Specialist"]);
    for (const engine of AI_ENGINES) {
      assert.ok(engine.desc);
      assert.ok(engine.badge);
    }
  });
});
