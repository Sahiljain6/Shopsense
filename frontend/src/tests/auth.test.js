import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { getToken, setToken, clearToken, ApiError, friendlyError } from "../api.js";

describe("Auth Lifecycle & State Unit Tests", () => {
  const store = new Map();

  beforeEach(() => {
    store.clear();
    globalThis.localStorage = {
      getItem: (k) => store.get(k) ?? null,
      setItem: (k, v) => store.set(k, String(v)),
      removeItem: (k) => store.delete(k),
      clear: () => store.clear(),
    };
  });

  it("returns null when no token is present in storage", () => {
    assert.equal(getToken(), null);
  });

  it("persists and retrieves access token accurately", () => {
    setToken("mock_jwt_access_token_xyz");
    assert.equal(getToken(), "mock_jwt_access_token_xyz");
  });

  it("clears access token on logout", () => {
    setToken("mock_jwt_access_token_xyz");
    clearToken();
    assert.equal(getToken(), null);
  });

  it("correctly identifies ApiError instance and status", () => {
    const err = new ApiError(401, "Invalid email or password");
    assert.ok(err instanceof Error);
    assert.ok(err instanceof ApiError);
    assert.equal(err.status, 401);
    assert.equal(err.message, "Invalid email or password");
  });

  it("formats auth error message using friendlyError", () => {
    const err = new ApiError(401, "Could not validate credentials");
    const formatted = friendlyError(err);
    assert.ok(formatted.includes("Authentication error"));
    assert.ok(formatted.includes("Could not validate credentials"));
  });
});
