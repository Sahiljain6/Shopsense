# ShopSense Caching, Scaling, and API Governance

This runbook covers roadmap Parts 6–9. It intentionally avoids adding Redis, a load balancer, or a separate API gateway until measurements or new integration requirements justify that operational cost.

## Part 6 — Live-search caching

ShopSense caches normalized retailer-search snapshots in each backend process. The cache is deliberately not shared across users or used for model-generated answers.

- Default time to live (TTL): 900 seconds / 15 minutes.
- Default capacity: 256 entries per process.
- Configuration: `LIVE_SEARCH_CACHE_TTL_SECONDS` (1–86400) and `LIVE_SEARCH_CACHE_MAX_ENTRIES` (16–5000).
- A cache hit returns a copy of the cached dictionaries. It does not rewrite `retrieved_at`; the UI should treat the retailer result as a snapshot, not a checkout price guarantee.
- Cache keys are hashed and include schema version, provider, a one-way fingerprint of provider configuration, market/language, normalized location/query, and result limit. No raw API key or query is exposed in diagnostics.
- Cache state and metrics are process-local. Restarting a process clears them; one replica cannot see another replica's entries.

Only a successful SerpApi response (including a valid no-result response) is cached. If SerpApi fails, a DuckDuckGo fallback is returned without being saved as a successful SerpApi result. Without SerpApi, non-empty DuckDuckGo results may be cached; empty results are not cached because the fallback function does not currently expose a reliable success/failure status.

### Part 7 — Invalidation and correctness

Entries expire based on a monotonic clock and are removed during cache access. When capacity is reached, the oldest entry is evicted. The cache schema version should be incremented whenever query normalization, the result shape, market/language defaults, or freshness semantics change. Provider-key rotation causes a cache miss because its fingerprint changes.

`clear_live_search_cache()` clears only derived retailer-search snapshots; it never deletes product catalog rows, account data, chat history, quotas, or idempotency records. `live_search_cache_stats()` returns non-sensitive local counters only (hits, misses, expirations, evictions, entry count, configured capacity and TTL). It is intended for internal diagnostics/tests and is not a public API route.

Do not globally cache authenticated payloads or AI answers by prompt text. If metrics later show cache duplication across replicas, evaluate a shared cache with explicit TTL, key versioning, outage behavior, and cost/latency measurements before adopting one.

## Part 8 — Load-balancing and scale-out gate

There is not yet a production traffic/latency baseline that justifies adding another load balancer to the managed frontend/backend deployment. Use the platform's native ingress and scaling controls first; do not insert a self-managed proxy or sticky sessions as a checklist item.

Before adding backend replicas, verify all of the following:

1. **Shared durable state:** replicas point to the same PostgreSQL database. Quota accounting and chat idempotency must remain database-backed. The request sliding-window limiter added in the previous roadmap PR is thread-safe but process-local; move it to a shared atomic store before treating per-user/per-IP limits as global.
2. **Cache expectations:** the retailer cache is process-local and bounded. This affects hit rate and provider spend, not correctness; introduce a shared cache only if measurements show meaningful duplicate work.
3. **SSE behavior:** confirm the host's stream idle timeout, cancellation propagation, connection limits and any proxy buffering. Do not assume sticky routing is required unless a feature stores session state in process memory.
4. **Aggregate upstream budgets:** account for total concurrency across all replicas so additional instances cannot multiply LLM/SerpApi traffic beyond provider limits.
5. **Health and rollback:** use the platform's health-check and rollback mechanisms, and validate one replica/worker at a time before increasing capacity.

### Suggested measurements before scaling

Capture p50/p95 and error rate separately for catalog endpoints, chat first-token/total time, SerpApi requests, active SSE connections, process memory/CPU, SQLAlchemy pool wait/checkout, and provider 429/5xx responses. Start with a short representative load test; compare against a quiet baseline and a production-like database. Thresholds are deployment-specific—do not treat a universal CPU or latency number as proof that a second replica will help.

**Current decision:** defer new load-balancing infrastructure. The main current scale-out blocker is making the request rate limiter shared, then testing host-specific SSE limits and aggregate provider budgets.

## Part 9 — API gateway decision

The existing FastAPI application is the API policy boundary for authentication, request validation, user scopes, quota reservations and rate limiting. A separate gateway forwarding every request to this one API would duplicate policy and add another hop without a demonstrated benefit, so it is intentionally deferred.

If ShopSense later exposes a public API to third-party clients or separates backend services, create a gateway proposal that names the exact responsibility it adds (for example, API-key issuance, centralized quotas, version routing, request-size enforcement, or tenant analytics). Before launch, require:

- A documented versioned contract (for example, `/v1`) and compatibility/deprecation policy.
- Authentication and server-side authorization on every protected operation; allow-listed provider/model IDs and no arbitrary upstream URL or browser-supplied provider key.
- Per-consumer quotas, safe errors, request-size/time limits, redacted logs, and auditability.
- Contract/security tests, cost estimate, rollback plan and measurable latency/operations benefit.

CORS is not authentication, and a gateway does not replace FastAPI's authorization checks. Keep secrets in backend environment settings/secret management; frontend `VITE_*` variables must contain public configuration only.

## Part 10 — Request time budgets

- The browser API helper has a 105-second overall deadline by default. The existing 35-second first-attempt and 65-second wake-up windows remain available, but each attempt is clipped to the remaining overall budget and the retry pause cannot extend it.
- Endpoint callers can override `timeoutMs` (per attempt) and `totalTimeoutMs` (whole operation). Caller-provided `AbortSignal` is forwarded; an explicit user/UI abort is not retried automatically.
- The backend AI provider chain has a configurable 75-second default total budget; OpenAI/Groq requests use a 30-second default request timeout with SDK-level automatic retries disabled, and model fallback stops when the remaining chain budget is exhausted. The existing provider priority and model fallback order are preserved.
- SerpApi calls already use a 9-second request timeout. The database pool uses an explicit checkout timeout, and other outbound integrations retain their provider-specific timeout values.
- Timeout failures are not a guarantee that the upstream provider did no work. Browser retries of chat operations must keep the original idempotency key.

Related settings (backend environment variables):

| Variable | Default | Allowed range |
|---|---:|---:|
| `LIVE_SEARCH_CACHE_TTL_SECONDS` | `900` | 1–86400 |
| `LIVE_SEARCH_CACHE_MAX_ENTRIES` | `256` | 16–5000 |
| `AI_PROVIDER_TIMEOUT_SECONDS` | `30` | 5–120 |
| `AI_PROVIDER_CHAIN_TIMEOUT_SECONDS` | `75` | 10–240 |

These budgets are guardrails, not an SLA. Validate them against actual host request limits and representative chat latency before changing production settings.
