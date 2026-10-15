import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  formatProductAttributeLabel,
  formatProductAttributeValue,
} from "../utils/productAttributes.js";

describe("Product detail attribute formatting", () => {
  it("humanizes specification keys", () => {
    assert.equal(formatProductAttributeLabel("ram_storage"), "Ram Storage");
    assert.equal(formatProductAttributeLabel("os-version"), "Os Version");
  });

  it("formats nested store prices instead of rendering [object Object]", () => {
    assert.equal(
      formatProductAttributeValue({ amazon_india: 64999, flipkart: 65999 }),
      "Amazon India: 64999 · Flipkart: 65999",
    );
  });

  it("formats arrays, booleans and missing values", () => {
    assert.equal(formatProductAttributeValue(["AMOLED", "120Hz"]), "AMOLED, 120Hz");
    assert.equal(formatProductAttributeValue(true), "Yes");
    assert.equal(formatProductAttributeValue(null), "Not specified");
    assert.equal(formatProductAttributeValue({}), "Not specified");
  });
});
