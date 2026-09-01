import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { friendlyError, ApiError } from "../api.js";

describe("Frontend API Error Mapping Unit Tests", () => {
  it("maps connection wake-up error status 0 cleanly", () => {
    const err = new ApiError(0, "Failed to fetch");
    const msg = friendlyError(err);
    assert.match(msg, /Connection notice/);
    assert.match(msg, /waking up/);
  });

  it("maps timeout error status 408 cleanly", () => {
    const err = new ApiError(408, "Gateway timeout");
    const msg = friendlyError(err);
    assert.match(msg, /Server wake-up notice/);
  });

  it("maps validation error 400 cleanly", () => {
    const err = new ApiError(400, "Query cannot be empty");
    const msg = friendlyError(err);
    assert.equal(msg, "Validation error: Query cannot be empty");
  });

  it("maps unauthorized error 401 cleanly", () => {
    const err = new ApiError(401, "Token expired");
    const msg = friendlyError(err);
    assert.equal(msg, "Authentication error: Token expired");
  });

  it("maps forbidden error 403 cleanly", () => {
    const err = new ApiError(403, "Access denied");
    const msg = friendlyError(err);
    assert.equal(msg, "Authorization error: Access denied");
  });

  it("maps endpoint not found 404 cleanly", () => {
    const err = new ApiError(404, "Route not found");
    const msg = friendlyError(err);
    assert.equal(msg, "Endpoint not found: Route not found");
  });

  it("maps server 500 error cleanly", () => {
    const err = new ApiError(500, "Internal error");
    const msg = friendlyError(err);
    assert.equal(msg, "Server error (500): Internal error");
  });

  it("gracefully formats generic standard JS Error", () => {
    const err = new Error("Network unplugged");
    assert.equal(friendlyError(err), "Network unplugged");
  });

  it("gracefully handles unknown non-Error types", () => {
    assert.equal(friendlyError("Unknown text"), "Something went wrong. Please try again.");
    assert.equal(friendlyError(null), "Something went wrong. Please try again.");
  });
});
