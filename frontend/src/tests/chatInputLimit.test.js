import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { CHAT_INPUT_MAX_LENGTH } from "../utils/constants.js";

describe("ShopSense chat input limit", () => {
  it("sets a generous 4,000-character budget for detailed shopping prompts", () => {
    assert.equal(CHAT_INPUT_MAX_LENGTH, 4000);
  });
});
