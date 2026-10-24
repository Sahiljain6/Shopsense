# ShopSense Reliability & Security Operations — Parts 11–20

This guide documents the application-level protections added for roadmap Parts 11–16 and 18–20, plus the deliberate deferral for Part 17. It does not claim multi-instance guarantees from process-local state and does not add paid infrastructure.

## Part 11 — Retry policy

- Browser `apiFetch` retries GET/HEAD/OPTIONS by default for selected network, timeout, and transient server errors.
- A mutation is not automatically retried unless its JSON body contains the backend-supported `idempotency_key` field. Header-only keys are deliberately not treated as safe because non-chat mutation endpoints do not yet enforce them. ShopSense chat retries reuse the same request key, matching the backend's durable chat receipt.
- AI model fallback continues only for transient upstream errors and explicit model-not-found cases. Permanent authentication/authorization and malformed-request failures stop the fallback loop instead of sending the same invalid request to every candidate model.
- OpenAI-compatible clients have SDK retries disabled so the application's bounded model fallback is not multiplied by hidden SDK retry loops.
- Retry logic is not a guarantee that an upstream service did no work after a client timeout; use idempotency for state-changing calls.

## Part 12 — Backoff and Retry-After

The browser uses capped exponential backoff with jitter for retryable network/server responses and respects numeric or HTTP-date `Retry-After` values within the overall request deadline. Backend model fallback uses capped jitter and respects `Retry-After` when the provider SDK exposes it. Backoff remains short because it shares the provider-chain deadline; no database transaction is held while waiting.

## Part 13 — Circuit breakers

The backend has thread-safe, process-local circuit breakers for the configured AI provider and SerpApi Google Shopping. Five transient upstream failures open a breaker for a 30-second cool-down; one half-open probe is permitted after cool-down. Success closes the breaker. Permanent 4xx/configuration failures do not count as an outage. SerpApi falls back to DuckDuckGo when the breaker is open.

**Scope limitation:** breaker state is per process. A multi-replica deployment will have independent breaker state unless a shared coordination layer is added. The system does not silently switch the configured AI provider when its breaker opens; this preserves provider selection/fallback semantics.

## Part 14 — Race conditions

- Chat REST and SSE share the existing database-backed user/key/idempotency receipt.
- Wishlist now has a database uniqueness invariant on `(user_id, product_id)`, with startup cleanup of historical duplicates before index creation. A duplicate request is treated as success only if the row exists after rollback.
- Database uniqueness, not a frontend disabled button, is the enforcement layer for the wishlist invariant.

The repository currently has no payment/checkout mutation API. If non-repeatable order/payment APIs are introduced, give each mutation its own persistent idempotency key and uniqueness/transaction rules before enabling automatic retries.

## Part 15 — Deadlocks and DB contention

- SQLAlchemy pool checkout already has an explicit timeout.
- PostgreSQL connections receive a configurable lock timeout and statement timeout on connection creation; SQLite receives a bounded connection/busy timeout.
- Defaults: `DB_LOCK_TIMEOUT_MS=5000` and `DB_STATEMENT_TIMEOUT_MS=30000`.
- DB session dependency rolls back on unhandled request exceptions and closes the session at the end of the request.

These limits bound waiting; they do not replace query-plan review or safe transaction boundaries. Keep network/provider work outside database transactions and validate timeout values against the host/database tier.

## Part 16 — Bounded resources

| Resource | Default limit |
|---|---:|
| Declared HTTP request body | 10 MiB (`MAX_REQUEST_BODY_BYTES`) |
| Product image upload | 8 MiB |
| Chat message text | 4,000 characters |
| History entries in one chat payload | 20 |
| Cart entries in one chat payload | 50 |
| Individual buffered SSE event | 256 KiB |
| Accumulated SSE answer text | 1,000,000 characters |
| Live-search cache | 256 entries per process |
| Live-search cache TTL | 900 seconds per process |

The ASGI request-body guard rejects requests with a declared `Content-Length` over the configured limit before body parsing. The image endpoint independently reads at most the limit plus one byte and rejects larger files. Clients that use chunked bodies without Content-Length should still be constrained by ingress/platform body limits. The SSE reader is cancelled/released during completion, error, timeout, and caller cancellation.

The limits are guardrails rather than recommendations to maximize payload size; adjust only after representative memory and request-volume testing.

## Part 17 — Webhooks (deferred)

**No webhook endpoint was added.** ShopSense currently has no trusted event producer or documented outbound event contract that requires a callback. Exposing an unauthenticated callback merely to check off a roadmap item would expand attack surface without a real use case.

Before implementing webhooks, specify a producer, supported event types, signed requests or equivalent service authentication, timestamp/replay protections, stable event IDs, strict schema/body limits, idempotent handling, delivery retry policy, retention, and tests for invalid signatures, stale/replayed events, oversized payloads, and duplicate delivery.

## Part 18 — CORS

- Production origins remain in the exact `CORS_ORIGINS` allow-list.
- The optional Vercel preview regex is restricted to ShopSense slugs under the expected `sahil-jain-s-projects.vercel.app` team suffix instead of matching every domain that starts with `shopsense`.
- Allowed methods and browser headers are explicit.
- CORS middleware is placed outside request authentication/body-limit middleware so error responses can still include the right CORS headers for approved origins.

CORS is not authentication/authorization. If the Vercel team/project slug changes, update `CORS_ORIGIN_REGEX` or use the explicit origin list after verifying the new deployment origin.

## Part 19 — Secrets

- When no JWT secret is configured in development, a cryptographically random per-process secret is generated. Tokens are therefore not expected to survive a restart in this local-only configuration.
- Production refuses an empty or known placeholder JWT secret. Configure `JWT_SECRET` with a secret generated by your hosting provider/secret manager.
- `.env.example` contains placeholders, not deployable credentials. Provider and SerpApi keys belong in backend environment settings, never `VITE_*` frontend variables.
- AI provider logs now record provider/model/status/error type rather than request text, raw upstream bodies, or exception messages that might contain credential-bearing URLs.
- The repository's Gitleaks workflow remains the automated secret scan.

If a real key has ever been committed or logged, rotate/revoke it at the provider; removing it from the latest commit alone does not invalidate the leaked key.

## Part 20 — Observability

Every HTTP request gets a server-generated `X-Request-ID` response header. The ID is not copied from arbitrary client values into logs. Logs record method, route template (not query strings or raw unmatched paths), status, duration, and error type only. The middleware measures the full response body, including SSE duration.

Authenticated admins can read `GET /admin/ops/metrics`, which returns bounded, process-local aggregates:
- Request count and server-error count by HTTP route template.
- Recent-sample p50/p95 duration (up to 256 samples per route) and 4xx/5xx counts.
- Live-search cache hit/miss/expiry/eviction state.
- SerpApi and AI provider circuit-breaker state.

The metrics endpoint never includes prompts, cookies, authorization headers, provider keys, raw URLs or request bodies. The aggregation is in-process and resets on restart; it is not a global dashboard across replicas. Begin with these logs/metrics and host-native logs before adding an external monitoring product.

## Verify and rollback

Run the test suites from the repository root:

~~~bash
python -m pytest -v backend/tests
cd frontend
npm test
npm run build
~~~

CI has not been considered passed until those tests finish successfully on the final PR head. These connector-driven file updates could not run the repository's commands in this environment, so treat the tests as pending review rather than a verified pass.

For rollback, revert this feature PR rather than hand-editing the live database. The new wishlist unique index is a safe data-integrity constraint; existing duplicate wishlist rows are deduplicated during startup before index creation. If a deployment cannot create the index due to unexpected data/schema drift, check the generic startup notice and database migration state before reverting. Keep the size/timeout settings unless your provider tier requires different measured values.
