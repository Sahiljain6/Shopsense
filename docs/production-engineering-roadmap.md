# ShopSense Production Engineering Roadmap — 20 Parts

**Project:** [ShopSense](https://github.com/Sahiljain6/Shopsense) — React + Vite frontend, FastAPI backend, SQLAlchemy storage, AI shopping assistant, and optional SerpApi live retailer search.

**Status:** Part 1 is in its own pull request. Parts 2–5 are implemented together on `feature/parts-02-05-performance` and await CI/review. Parts 6–20 remain planned work.

**Part 2–5 implementation notes:** monthly token usage and active reservations are database-backed and atomic on SQLite/PostgreSQL; the sliding-window request limiter is thread-safe and memory-bounded but remains process-local; managed-host deployments do not get an unnecessary extra reverse proxy; PostgreSQL pool settings and reusable outbound HTTP clients are bounded; product/category queries use eager loading to avoid N+1 category reads. See [docs/deployment-hardening.md](./deployment-hardening.md).

## Implementation guardrails

- Preserve the current shopping experience, page layout, endpoint contracts, cart behavior, product-card schema, provider-selection behavior, and Server-Sent Events (SSE) unless a specific part requires a small, reviewed change.
- Do not change provider preference/fallback semantics or model behavior as an incidental reliability refactor.
- Do not put provider keys, JWT secrets, database credentials, or SerpApi keys in frontend bundles, browser storage, logs, test output, or commits.
- Do not add infrastructure just to check a box. Redis, a separate gateway, an extra reverse proxy, a load balancer, a queue, and a webhook receiver are conditional choices—not default requirements for a small deployment.
- Implement one part per branch/PR where practical. Every part must include failure-path tests and a record of files changed, tests actually run, limitations, and rollback instructions.
- Keep existing UI and product business rules unchanged unless the relevant part explicitly calls for it.

## Part 1 — Idempotency keys

**Goal:** A repeated browser retry or stream-to-REST fallback must not launch the same expensive chat operation twice.

**Implementation**
- Generate one unique key per user-initiated AI chat submission and reuse it only for network retries and the /chat/stream → /chat fallback.
- Scope the key to the authenticated user and bind it to a canonical hash of the semantic request: message, history, cart, model, mode, and conversation ID. Reusing a key with different data returns HTTP 409.
- Persist processing/completed state and the final ChatResponse so an identical retry can replay it. Store receipts for a bounded period; recover stale processing claims after a lease timeout.
- Replay completed results over either REST JSON or the existing SSE event format. A duplicate that is still processing must not invoke the model a second time.
- Preserve backward compatibility: requests without an idempotency key continue to work.

**Acceptance checks**
- Same user + same key + same payload returns one stable response and creates one receipt.
- Same key with a changed payload returns 409; distinct users may use the same key independently.
- An active duplicate is rejected rather than starting another provider call; stale claims can recover.
- Client timeout/retry and stream fallback reuse the same key and cart snapshot.
- Tests cover response replay, key collision, concurrent in-progress use, stale recovery, missing-key compatibility, and server-side key validation.

## Part 2 — Rate limiting and quota accounting

**Goal:** Protect paid model/search services and prevent bursts from exhausting a user's allowance.

**Implementation**
- Audit the existing SlowAPI endpoint limits and the in-memory quota engine; document that process-local token totals do not coordinate between backend replicas.
- Separate unauthenticated/IP limits, authenticated per-user chat limits, expensive live-search limits, file/image workload limits, and provider budget controls.
- Ensure a denied request is blocked before expensive provider calls; ensure cached idempotent replays do not consume a new model-call allowance.
- Use atomic shared storage for global quota state before scaling to multiple instances. For the current deployment, keep a simple well-bounded design.
- Apply provider-side budget alerts/limits where available rather than relying solely on the application.

**Acceptance checks**
- Concurrency tests prove the configured single-store limit cannot be exceeded.
- Rejected requests do not call the LLM/SerpApi.
- Limit messages accurately say whether they are per process or global.

## Part 3 — Reverse proxies

**Goal:** Safely handle HTTPS termination, headers, payload limits, and long-running SSE responses in self-hosted deployments.

**Implementation**
- Document the actual production topology first; Vercel/Render or another managed host may already own TLS and ingress.
- If self-hosting behind a proxy, configure HTTPS, trusted forwarded headers, request-size limits, conservative connection/read timeouts, and SSE-compatible buffering settings.
- Do not trust arbitrary client-supplied X-Forwarded-For, host, or protocol values. Trust only configured proxy hops.
- Avoid logging authorization headers, cookies, API keys, prompts, uploaded files, or raw provider responses.

**Acceptance checks**
- Deployment tests cover HTTPS, forwarded host/protocol, request-size limits, and SSE streaming without buffering.
- If managed ingress already provides these controls, document that and defer the proxy change.

## Part 4 — Connection pooling

**Goal:** Reduce repeated database/network setup cost without sharing unsafe mutable request state.

**Implementation**
- Review SQLAlchemy engine/session lifecycle and the construction/lifecycle of OpenAI-compatible or other provider clients.
- Reuse outbound HTTP connections through supported client lifecycle management where practical; keep connect, read, and total timeouts explicit.
- Bound connection-pool sizes to provider limits and deployment concurrency. Do not share an ORM Session across threads or asynchronous tasks.
- Handle provider-key/endpoint changes safely and close clients during app shutdown where supported.

**Acceptance checks**
- Concurrent chat requests have isolated DB sessions and independent request data.
- Tests verify timeout, base URL, credential selection, cleanup, and exception paths.
- A representative benchmark demonstrates a measurable benefit before keeping additional pooling complexity.

## Part 5 — N+1 queries

**Goal:** Prevent product listings, product cards, category labels, and history views from creating one database query per result.

**Implementation**
- Audit SQLAlchemy relationship access in product serialization (including category names), catalogue searches, comparisons, price history, wishlist, and admin views.
- Use selectinload/joinedload, aggregate queries, or batched lookup only where query tracing confirms repeated round trips.
- Keep result sizes bounded and use indexes based on actual filters/order-by expressions.
- Preserve ownership filters and parameterized ORM queries.

**Acceptance checks**
- Tests with many products assert query counts remain bounded for key endpoints.
- Query plans are reviewed before adding indexes.
- API schemas, sorting, filtering, and product-card contents remain unchanged.

## Part 6 — Caching strategies

**Goal:** Reduce repeated shopping-search work and latency without serving misleadingly stale prices or bypassing model behavior.

**Current area to review:** the live-search integration documents a 15-minute in-process cache; it is cleared on restart and not shared by replicas.

**Implementation**
- Separate cacheable catalog metadata, short-lived retailer search results, static configuration, and non-cacheable user/private data.
- Choose TTLs based on freshness and provider quota. Include market/location, normalized query, provider configuration, and schema version in live-search cache keys.
- Preserve freshness metadata such as retrieved_at; label cached retailer listings as snapshots, not checkout guarantees.
- Do not cache user-specific AI answers or authenticated payloads globally. Do not cache an LLM completion by prompt text alone.
- Consider a shared cache only if metrics show multi-instance duplication or latency makes it worthwhile.

**Acceptance checks**
- Equivalent live-search requests within the TTL can hit cache; changing location/query invalidates the key.
- Expired or provider-failure results do not masquerade as fresh listings.
- Cache hit/miss and provider requests are testable without paid API calls.

## Part 7 — Cache invalidation

**Goal:** Keep cached product/listing data correct after expiry, configuration changes, failed refresh, or a new deployment.

**Implementation**
- For every cache, record key fields, TTL, scope (process or shared), cache owner, and invalidation triggers.
- Invalidate or version entries when query normalization, market location, output schema, or provider behavior changes.
- Distinguish a provider returning no deals from a failed request; do not overwrite good data with malformed results.
- Avoid deleting user history or persistent records when clearing a derived-data cache.

**Acceptance checks**
- Tests cover fresh, expired, invalidated, empty, and failed-search results.
- A refreshed result contains correct freshness metadata.
- Clearing cache cannot delete catalog or account data.

## Part 8 — Load balancing

**Goal:** Add instances only after traffic and resource measurements justify scaling out.

**Implementation**
- Establish thresholds from p95 latency, concurrent SSE sessions, memory/CPU, error rate, database connection pressure, and provider rate limits.
- Before replicas are added, move necessary quotas, idempotency records, and shared cache state from process-local memory to a shared atomic/durable store.
- Confirm SSE/session behavior and sticky-routing requirements for the actual host.
- Aggregate outbound concurrency across replicas so extra instances do not cause model/search throttling or cost spikes.

**Acceptance checks**
- A multi-instance test confirms idempotency and quota state is shared and consistent.
- SSE sessions survive normal proxy behavior; health checks remove unhealthy instances.
- If the deployment is not capacity-limited, defer scaling rather than adding infrastructure without benefit.

## Part 9 — API gateways

**Goal:** Add a separate policy layer only if ShopSense exposes multiple backend services or external API consumers that need central governance.

**Implementation**
- The current FastAPI app already owns REST endpoints, authentication, validation, and rate limiting; do not add a gateway just to route the frontend to the same service.
- If an external API is introduced, define its versioned contract, authentication, allow-listed model/provider IDs, payload limits, quotas, safe error responses, and observability.
- Never let browser clients supply arbitrary upstream API keys or unrestricted provider URLs.
- Avoid duplicate policy layers unless their responsibilities are clearly separated.

**Acceptance checks**
- Contract tests cover authentication, versioning, invalid payloads, quota enforcement, and safe errors.
- A gateway proposal includes deployment cost, rollback, and measurable benefit.

## Part 10 — Timeouts and total request budgets

**Goal:** Ensure a stalled provider or search call cannot keep a request, worker, or SSE response alive indefinitely.

**Implementation**
- Inventory frontend fetch/abort timeouts, the 35-second/65-second retry windows in apiFetch, provider request timeouts, SerpApi request timeouts, DB pool timeouts, and host/proxy SSE limits.
- Define separate connect/read/provider/total-run budgets. Ensure individual retries fit inside an overall deadline.
- Cancel downstream work when the client explicitly aborts where safe; do not interpret a UI disconnect as evidence that an upstream request did not run.
- Return safe timeout errors that can be retried using the same idempotency key.

**Acceptance checks**
- Tests simulate a stalled model and stalled search provider and verify bounded completion.
- Timeout failures are distinguishable from invalid keys, invalid model IDs, quotas, and no-results outcomes.
- Avoid arbitrary reductions of valid response time without a latency baseline.

## Part 11 — Retry policy

**Goal:** Retry transient failures safely without duplicate model calls, repeated mutations, or hidden wait time.

**Implementation**
- Classify connection failures, 429, selected 5xx responses, invalid credentials, malformed requests, and model-not-found separately.
- Keep chat retries on the same idempotency key. Do not blindly retry state-changing endpoints such as order/checkout mutations unless they have their own idempotency or natural uniqueness.
- Avoid stacking frontend, SDK, and server retry loops without a shared attempt and total-time budget.
- Preserve existing AI provider precedence/fallback rules and sanitize user-facing failures.

**Acceptance checks**
- A successful request is not called again because of a client timeout.
- Permanent 400/401/403/configuration failures do not get transient retries.
- Tests count mocked provider calls for retries and fallback paths.

## Part 12 — Exponential backoff with jitter

**Goal:** Prevent synchronized retries from increasing load during provider or database incidents.

**Implementation**
- First verify retry behavior already supplied by the HTTP/LLM SDK and frontend.
- Add capped exponential backoff with jitter only where custom retry control is required; respect Retry-After when available.
- Use provider-specific limits and a total request deadline; do not sleep for long periods inside a database transaction.
- Inject a fake clock/sleeper/random source into tests.

**Acceptance checks**
- Retry delays are bounded and do not exceed the request deadline.
- 429/5xx may retry per policy; permanent errors fail quickly.
- Tests do not require real sleeps or paid API requests.

## Part 13 — Circuit breakers

**Goal:** Stop repeatedly calling a provider or live-search service during a sustained outage.

**Implementation**
- Define closed/open/half-open states and provider-specific failure thresholds, cool-down, and probe limits.
- Count transient upstream failures—not invalid user input, a no-results query, a rejected API key, or a product failing a relevance threshold—as breaker failures.
- Preserve the existing configured LLM fallback path; do not silently change provider-selection semantics.
- Keep breaker state process-local only while appropriate; coordinate it only if deployment scale requires it.

**Acceptance checks**
- Synthetic repeated 5xx failures open the breaker; a successful probe closes it.
- A provider outage does not block unrelated services.
- Error messaging is actionable and never leaks credentials or raw upstream bodies.

## Part 14 — Race conditions

**Goal:** Prevent duplicate writes and inconsistent UI state when users double-click, retry, or start overlapping operations.

**Implementation**
- Extend Part 1's durable idempotency pattern to any future order/checkout/payment or other non-repeatable mutation.
- Review concurrent cart/wishlist writes, token refresh, chat-history persistence, and the interaction between aborted SSE requests and fallback REST requests.
- Use database uniqueness constraints and transactions for persistent invariants; a frontend disabled button alone is not a concurrency guarantee.
- Keep separate SQLAlchemy Sessions per request and avoid shared mutable module-level request data.

**Acceptance checks**
- Simultaneous identical chat submissions call the provider once per key.
- Concurrent wishlist/cart/order operations maintain their invariants.
- Stress tests leave no duplicate logical records or crossed user/session results.

## Part 15 — Deadlocks and database lock contention

**Goal:** Keep PostgreSQL/SQLite write contention bounded and avoid holding locks while waiting on external services.

**Implementation**
- Map transaction boundaries in auth, chat-history persistence, conversation state, catalogue updates, wishlist, and order flows.
- Keep transactions short; never wrap LLM or SerpApi network calls inside a database transaction.
- Standardize lock acquisition order where multiple records must be updated; handle deadlock/serialization retries only when safe and bounded.
- Add controlled errors for lock timeouts and record lock timing without logging user content.

**Acceptance checks**
- Concurrent writes complete or return bounded errors, never hang indefinitely.
- DB sessions are rolled back after exceptions.
- Tests verify retry safety and do not duplicate external provider work after transaction conflicts.

## Part 16 — Memory leaks and bounded resources

**Goal:** Keep long-lived API processes and streaming sessions stable as users, retailer results, and uploaded image workloads grow.

**Implementation**
- Profile repeated chat/stream requests, maximum answer sizes, product arrays, large history payloads, image uploads, and search result normalization.
- Bound SSE work, response bodies, history length, cached listing count, and image memory; close readers, responses, streams, and DB sessions.
- Review in-process dictionaries and per-process caches for size and lifetime.
- For every thread pool/task, define cancellation and cleanup behavior. Avoid storing full prompts or generated responses in metrics.

**Acceptance checks**
- Repeated synthetic workloads do not show steadily rising open connections, tasks, or retained result objects.
- Large input/output paths respect documented limits.
- Cancellation and exception tests verify file and session cleanup.

## Part 17 — Webhooks

**Goal:** Support integrations such as price alerts or order-status notifications only when a concrete event producer and use case exist.

**Implementation**
- Define supported event types, event IDs, producer authentication, delivery guarantees, retries, and retention before exposing a callback endpoint.
- Verify signatures and timestamps, reject replays, validate schemas and payload sizes, and acknowledge quickly before queued work.
- Make processing idempotent and keep event-triggered work from invoking arbitrary provider calls or exposing another user's data.
- Do not add a webhook server merely to complete the list.

**Acceptance checks**
- Tests reject invalid signatures, stale timestamps, duplicate event IDs, malformed events, and oversized payloads.
- Re-delivery has no duplicate side effects.
- If no event producer exists, document this part as deferred.

## Part 18 — CORS

**Goal:** Permit browser requests from the intended ShopSense frontend and no unrelated origins.

**Implementation**
- Verify the deployed frontend origin(s) and the current CORS_ORIGINS setting in backend configuration.
- Allow exact production and necessary development origins, required methods, and headers; avoid broad wildcards for credentialed requests.
- Confirm preflight handling for Authorization and CSRF headers and preserve cookie credentials only where required.
- Remember that CORS is a browser control—not authentication or API authorization.

**Acceptance checks**
- Approved frontend origin works for REST and streaming endpoints.
- An unapproved browser origin does not receive permissive CORS headers.
- Production and local origins are configured separately and documented.

## Part 19 — Secrets management

**Goal:** Protect LLM, SerpApi, JWT, database, and third-party credentials from source control and browser exposure.

**Implementation**
- Keep secrets in backend host environment variables or a secret manager; use ignored local environment files for development and placeholders in examples.
- Ensure Vite-exposed VITE_* variables contain only public configuration such as the API base URL—not provider keys or JWT signing secrets.
- Add automated scanning for tracked secret patterns, review logs/errors and test artifacts, and document rotation/revocation after a leak.
- Use a strong production JWT secret, least-privilege database credentials, and a planned key-rotation process.
- Redact authorization/cookie headers and raw upstream error bodies.

**Acceptance checks**
- Secret scanning passes; test fixtures use obviously fake credentials.
- Tests confirm provider keys are absent from frontend bundles and user-facing errors/logs.
- Missing secrets fail closed with clear operator guidance.

## Part 20 — Observability: structured logs, metrics, and traces

**Goal:** Diagnose slow AI responses, search outages, retries, cache misses, and backend failures without recording private shopping conversations unnecessarily.

**Implementation**
- Propagate a request/correlation ID through REST and SSE, context assembly, provider calls, live search, DB persistence, and idempotency outcomes.
- Track request count, p50/p95 latency, provider error class, retries/fallbacks, cache hit rate, token use where available, quota rejections, SQL timing, active streams, and idempotent replays.
- Use structured logs and safe error categories. Do not log API keys, JWTs, passwords, cookies, full prompts, cart contents, uploaded files, or generated code by default.
- Keep operational telemetry separate from user chat history and product analytics; configure retention and sampling.
- Start with existing logging and hosting metrics before introducing a paid monitoring stack.

**Acceptance checks**
- A failed synthetic chat can be traced end-to-end by request ID.
- Latency/failure metrics are available without recording private message text or secrets.
- Logging failures never break chat delivery.

---

## Suggested implementation order

1. **Part 1 — Idempotency keys** (current feature branch; run CI and review before merge).
2. **Parts 10–13 — Timeouts, retries, backoff, circuit breakers** (provider reliability).
3. **Parts 2, 19, 20 — Quotas, secrets, observability** (cost and operational safety).
4. **Parts 14–16, 4–5 — Race conditions, lock contention, resources, pools, query patterns** (concurrency and data layer).
5. **Parts 6–7 — Caching and invalidation** (freshness and quota control).
6. **Parts 18, 3 — CORS and ingress/proxy behavior** (deployment hardening).
7. **Parts 8–9, 17 — Load balancing, gateways, webhooks** only when traffic or a concrete integration warrants them.

Every part should be reviewed and verified separately. A roadmap item may be explicitly deferred when the current architecture does not need it; it should not be implemented just to add infrastructure.
