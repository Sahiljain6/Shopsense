import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require(join(process.env.RUNNER_TEMP, "shopsense-audit/node_modules/playwright"));

const API_URL = (process.env.SHOPSENSE_API_URL || "https://shopsense-api-pb2g.onrender.com").replace(/\/$/, "");
const candidates = (process.env.SHOPSENSE_FRONTEND_CANDIDATES ||
  "https://shopsense-4444.vercel.app,https://shopsense.vercel.app,https://shopsense-gmeelq7ml-sahil-jain-s-projects.vercel.app,https://shopsense-4444-l2msp2txf-sahil-jain-s-projects.vercel.app")
  .split(",").map((x) => x.trim()).filter(Boolean);
const ARTIFACT_DIR = process.env.AUDIT_ARTIFACT_DIR || "artifacts/live-site-audit";
const results = [];
const browserIssues = { consoleErrors: [], pageErrors: [], firstPartyBadResponses: [], requestFailures: [] };
let frontendUrl = null;

function record(name, status, details, severity = "medium") {
  const item = { name, status, severity, details };
  results.push(item);
  const prefix = status === "PASS" ? "PASS" : status === "FAIL" ? "FAIL" : status === "WARN" ? "WARN" : "INFO";
  console.log(`[${prefix}] ${name}: ${typeof details === "string" ? details : JSON.stringify(details)}`);
}

async function fetchWithTimeout(url, init = {}, timeoutMs = 25000) {
  const started = Date.now();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { ...init, signal: controller.signal, redirect: "follow" });
    const body = await response.text();
    return {
      response,
      body,
      elapsedMs: Date.now() - started,
      headers: Object.fromEntries(response.headers.entries()),
    };
  } catch (error) {
    return { error: `${error.name}: ${error.message}`, elapsedMs: Date.now() - started };
  } finally {
    clearTimeout(timer);
  }
}

async function fetchJson(path, init) {
  const out = await fetchWithTimeout(`${API_URL}${path}`, init);
  if (out.error) return { ...out, json: null };
  let json = null;
  try { json = JSON.parse(out.body); } catch {}
  return { ...out, json };
}

await mkdir(ARTIFACT_DIR, { recursive: true });

// Resolve the canonical deployment from known ShopSense Vercel aliases without treating a stale preview as the only target.
for (const candidate of candidates) {
  const probe = await fetchWithTimeout(candidate, {}, 20000);
  const contentType = probe.headers?.["content-type"] || "";
  const looksLikeApp = !probe.error && probe.response.status >= 200 && probe.response.status < 400 &&
    contentType.toLowerCase().includes("text/html") && /<div[^>]+id=["']root["']/.test(probe.body);
  record(`Frontend alias probe: ${candidate}`, looksLikeApp ? "PASS" : "WARN",
    probe.error || { status: probe.response?.status, contentType, elapsedMs: probe.elapsedMs, hasReactRoot: /<div[^>]+id=["']root["']/.test(probe.body || "") },
    "low");
  if (looksLikeApp) {
    frontendUrl = new URL(probe.response.url || candidate).origin;
    break;
  }
}
record("Frontend deployment reachable", frontendUrl ? "PASS" : "FAIL",
  frontendUrl || "None of the known Vercel aliases returned a usable React/Vite HTML shell.", "critical");

// API liveness + response metadata.
const health = await fetchJson("/health");
const healthOk = !health.error && health.response.status === 200 && health.json?.status === "ok";
record("API /health", healthOk ? "PASS" : "FAIL",
  health.error || { status: health.response?.status, body: health.json ?? health.body.slice(0, 300), elapsedMs: health.elapsedMs },
  "critical");
if (!health.error) {
  const requiredHeaders = [
    ["strict-transport-security", "HSTS"],
    ["x-content-type-options", "X-Content-Type-Options"],
    ["x-frame-options", "X-Frame-Options"],
    ["referrer-policy", "Referrer-Policy"],
    ["content-security-policy", "Content-Security-Policy"],
  ];
  const missing = requiredHeaders.filter(([key]) => !health.headers[key]).map(([, label]) => label);
  record("API security headers", missing.length === 0 ? "PASS" : "WARN",
    { present: requiredHeaders.filter(([key]) => health.headers[key]).map(([, label]) => label), missing }, "medium");
  record("API request ID", health.headers["x-request-id"] ? "PASS" : "WARN",
    health.headers["x-request-id"] || "X-Request-ID header missing", "medium");
  if (health.elapsedMs > 15000) record("API cold/warm response latency", "WARN", `${health.elapsedMs}ms for /health`, "medium");
  else record("API /health response latency", "PASS", `${health.elapsedMs}ms`, "low");
}

// OpenAPI is informational because some deployments intentionally disable docs.
const schema = await fetchJson("/openapi.json");
record("OpenAPI schema endpoint", !schema.error && schema.response.status === 200 && schema.json?.paths ? "PASS" : "WARN",
  schema.error || { status: schema.response?.status, paths: schema.json?.paths ? Object.keys(schema.json.paths).length : 0 },
  "low");

// Read-only catalog request is the key database-backed smoke check.
const catalog = await fetchJson("/products?limit=3");
const catalogOk = !catalog.error && catalog.response.status === 200 && Array.isArray(catalog.json);
record("Catalog database/API smoke test", catalogOk ? "PASS" : "FAIL",
  catalog.error || {
    status: catalog.response?.status,
    itemsReturned: Array.isArray(catalog.json) ? catalog.json.length : null,
    contentType: catalog.headers?.["content-type"],
    errorBody: catalogOk ? undefined : catalog.body.slice(0, 400),
    elapsedMs: catalog.elapsedMs,
  }, "critical");

// Low-impact injection-shaped search inputs: assert the endpoint does not 5xx or switch to HTML.
for (const [label, query] of [
  ["SQL-injection-shaped search input", "' OR 1=1--"],
  ["XSS-shaped search input", "<script>alert(1)</script>"],
]) {
  const test = await fetchJson(`/products?q=${encodeURIComponent(query)}&limit=3`);
  const contentType = test.headers?.["content-type"] || "";
  const edgeBlocked = !test.error && test.response.status === 403 &&
    contentType.toLowerCase().includes("text/html") && /<title>\\s*Blocked\\s*<\\/title>/i.test(test.body);
  const ok = !test.error && test.response.status < 500 && contentType.toLowerCase().includes("application/json");
  if (edgeBlocked) {
    record(label, "WARN",
      { status: 403, result: "The hosting edge returned its generic Blocked page for this injection-shaped request; this is not evidence of an application injection flaw and does not prove the route's SQL safety either." },
      "medium");
  } else {
    record(label, ok ? "PASS" : "FAIL",
      test.error || { status: test.response?.status, contentType, bodySample: ok ? undefined : test.body.slice(0, 300) },
      "high");
  }
}

// Security checks must not use a token and must not mutate state.
for (const [path, label] of [
  ["/auth/me", "Anonymous access to /auth/me"],
  ["/admin/ops/metrics", "Anonymous access to admin metrics"],
]) {
  const out = await fetchJson(path);
  const blocked = !out.error && [401, 403].includes(out.response.status);
  record(label, blocked ? "PASS" : "FAIL",
    out.error || { status: out.response.status, bodySample: blocked ? undefined : out.body.slice(0, 300) },
    "critical");
}

// CORS preflight from the actual frontend origin. This is read-only and does not submit a chat message.
if (frontendUrl) {
  const cors = await fetchWithTimeout(`${API_URL}/chat`, {
    method: "OPTIONS",
    headers: {
      Origin: frontendUrl,
      "Access-Control-Request-Method": "POST",
      "Access-Control-Request-Headers": "authorization,content-type,idempotency-key",
    },
  });
  const allowOrigin = cors.headers?.["access-control-allow-origin"];
  const corsOk = !cors.error && cors.response.status >= 200 && cors.response.status < 300 &&
    (allowOrigin === frontendUrl || allowOrigin === "*");
  record("Frontend-to-API CORS preflight", corsOk ? "PASS" : "FAIL",
    cors.error || { status: cors.response.status, origin: frontendUrl, allowOrigin,
      allowMethods: cors.headers?.["access-control-allow-methods"],
      allowHeaders: cors.headers?.["access-control-allow-headers"] },
    "critical");
}

// Run a real browser check without signing in, submitting data, or purchasing.
if (frontendUrl) {
  let browser;
  try {
    browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      reducedMotion: "reduce",
      serviceWorkers: "block",
    });
    await context.addInitScript(() => {
      try { localStorage.clear(); sessionStorage.clear(); } catch {}
    });
    const page = await context.newPage();
    page.on("console", (message) => {
      if (message.type() === "error") browserIssues.consoleErrors.push(message.text().slice(0, 400));
    });
    page.on("pageerror", (error) => browserIssues.pageErrors.push(String(error).slice(0, 500)));
    page.on("requestfailed", (request) => {
      const url = request.url();
      if (url.startsWith(frontendUrl) || url.startsWith(API_URL)) {
        browserIssues.requestFailures.push({ url: url.slice(0, 250), failure: request.failure()?.errorText || "unknown" });
      }
    });
    page.on("response", (response) => {
      const url = response.url();
      if (response.status() >= 400 && (url.startsWith(frontendUrl) || url.startsWith(API_URL))) {
        browserIssues.firstPartyBadResponses.push({ status: response.status(), url: url.slice(0, 250) });
      }
    });

    const navigationStarted = Date.now();
    const response = await page.goto(frontendUrl, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.locator("#root").waitFor({ state: "attached", timeout: 10000 });
    await page.waitForTimeout(1500);
    const pageState = await page.evaluate(() => ({
      title: document.title,
      rootChildCount: document.querySelector("#root")?.childElementCount ?? 0,
      bodyTextLength: (document.body?.innerText || "").trim().length,
      hasSignIn: [...document.querySelectorAll("button")].some((button) => button.innerText.trim() === "Sign In"),
      hasSignUp: [...document.querySelectorAll("button")].some((button) => button.innerText.trim() === "Sign Up"),
      scriptCount: document.scripts.length,
      stylesheetCount: document.querySelectorAll('link[rel="stylesheet"]').length,
      domContentLoadedMs: Math.round(performance.getEntriesByType("navigation")[0]?.domContentLoadedEventEnd || 0),
    }));
    const browserPageOk = response?.status() >= 200 && response.status() < 400 &&
      pageState.rootChildCount > 0 && pageState.bodyTextLength > 50;
    record("Browser page renders (desktop)", browserPageOk ? "PASS" : "FAIL",
      { status: response?.status(), pageState, elapsedMs: Date.now() - navigationStarted }, "critical");
    await page.screenshot({ path: join(ARTIFACT_DIR, "shopsense-desktop.png"), fullPage: true });

    // Open and close sign-in UI without entering or submitting credentials.
    let signinOk = false;
    try {
      const signinButton = page.getByRole("button", { name: "Sign In", exact: true });
      await signinButton.click({ timeout: 5000 });
      const dialog = page.getByRole("dialog");
      await dialog.waitFor({ state: "visible", timeout: 5000 });
      const emailCount = await dialog.locator('input[type="email"]').count();
      const passwordCount = await dialog.locator('input[type="password"]').count();
      signinOk = emailCount >= 1 && passwordCount >= 1;
      record("Sign-in dialog opens with credential fields", signinOk ? "PASS" : "FAIL",
        { emailInputs: emailCount, passwordInputs: passwordCount }, "high");
      await page.keyboard.press("Escape");
      await dialog.waitFor({ state: "detached", timeout: 5000 });
      record("Sign-in dialog closes via Escape", "PASS", "Dialog closed without submitting credentials.", "low");
    } catch (error) {
      record("Sign-in UI interaction", "FAIL", String(error).slice(0, 500), "high");
    }

    // Open sign-up UI but do not create an account.
    try {
      const signupButton = page.getByRole("button", { name: "Sign Up", exact: true });
      await signupButton.click({ timeout: 5000 });
      const dialog = page.getByRole("dialog");
      await dialog.waitFor({ state: "visible", timeout: 5000 });
      const signupText = (await dialog.innerText()).toLowerCase();
      const showsRegistration = signupText.includes("create account") || signupText.includes("sign up") ||
        signupText.includes("full name") || await dialog.locator('input[type="text"]').count() > 0;
      record("Sign-up dialog opens", showsRegistration ? "PASS" : "WARN",
        { hasRegistrationFieldsOrText: showsRegistration }, "medium");
      await page.keyboard.press("Escape");
      await dialog.waitFor({ state: "detached", timeout: 5000 });
    } catch (error) {
      record("Sign-up UI interaction", "FAIL", String(error).slice(0, 500), "high");
    }

    // Mobile viewport and overflow sanity test.
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(300);
    const mobileState = await page.evaluate(() => ({
      viewportWidth: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
      rootChildCount: document.querySelector("#root")?.childElementCount ?? 0,
    }));
    const mobileOk = !mobileState.horizontalOverflow && mobileState.rootChildCount > 0;
    record("Mobile viewport layout", mobileOk ? "PASS" : "WARN", mobileState, "medium");
    await page.screenshot({ path: join(ARTIFACT_DIR, "shopsense-mobile.png"), fullPage: true });

    record("Browser JavaScript exceptions", browserIssues.pageErrors.length === 0 ? "PASS" : "FAIL",
      browserIssues.pageErrors, "high");
    record("Browser console errors", browserIssues.consoleErrors.length === 0 ? "PASS" : "WARN",
      browserIssues.consoleErrors.slice(0, 15), "medium");
    record("Browser first-party network issues", browserIssues.firstPartyBadResponses.length === 0 &&
      browserIssues.requestFailures.length === 0 ? "PASS" : "WARN",
      { badResponses: browserIssues.firstPartyBadResponses.slice(0, 15),
        requestFailures: browserIssues.requestFailures.slice(0, 15) }, "medium");

    await context.close();
  } catch (error) {
    record("Browser simulator execution", "FAIL", String(error).slice(0, 800), "critical");
  } finally {
    if (browser) await browser.close();
  }
} else {
  record("Browser simulator execution", "WARN", "Skipped because no frontend deployment could be resolved.", "high");
}

const summary = {
  audit: "ShopSense non-destructive live website smoke audit",
  timestamp: new Date().toISOString(),
  frontendUrl,
  apiUrl: API_URL,
  execution: "GitHub Actions runner + headless Chromium / Playwright",
  safety: "No login, registration, cart mutation, order, purchase, or destructive database operation was performed.",
  counts: {
    passed: results.filter((r) => r.status === "PASS").length,
    failed: results.filter((r) => r.status === "FAIL").length,
    warnings: results.filter((r) => r.status === "WARN").length,
    info: results.filter((r) => r.status === "INFO").length,
  },
  results,
  browserIssues,
};
await writeFile(join(ARTIFACT_DIR, "audit-report.json"), JSON.stringify(summary, null, 2));
console.log("\n=== SHOP SENSE AUDIT SUMMARY ===");
console.log(JSON.stringify(summary.counts, null, 2));
console.log(`Report written to ${join(ARTIFACT_DIR, "audit-report.json")}`);
if (summary.counts.failed > 0) process.exitCode = 1;
