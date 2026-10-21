# ShopSense Deployment Hardening

This runbook covers the operational choices introduced alongside production engineering Parts 2–5. It does not require changing the storefront layout, shopping rules, model-provider precedence, or public response schemas.

## Current deployment: managed frontend and backend

When the frontend and backend are hosted on managed platforms such as Vercel and Render, those platforms already provide their own public ingress/TLS termination and reverse-proxy layer. Do not add Nginx or another proxy solely to duplicate managed platform behavior.

Verify the actual configured domains and service settings before changing production. In particular:

- Keep the backend URL in the frontend's public `VITE_API_URL` setting; keep model, SerpApi, database, and JWT credentials in backend-only environment variables.
- Keep the backend's `CORS_ORIGINS` restricted to the actual frontend origins. CORS does not replace authentication or resource authorization.
- Do not parse arbitrary `X-Forwarded-For`, `Forwarded`, `X-Real-IP`, or host headers in application code. If rate limiting needs the original client address, only use forwarding information that the hosting provider sanitizes and documents.
- Do not configure Uvicorn to trust forwarded headers from all possible peers (`--forwarded-allow-ips=*`) unless the network boundary itself guarantees that only trusted proxies can connect directly.
- Confirm that platform request and response timeouts allow the current AI response pattern. A client disconnect does not guarantee that a synchronous provider call in a worker thread was cancelled.

## Server-Sent Events (SSE)

The `POST /chat/stream` endpoint sends Server-Sent Events. Its responses include `Cache-Control: no-cache, no-transform` and `X-Accel-Buffering: no`.

For a self-hosted reverse proxy, configure the SSE route to disable response buffering and caching, preserve the `text/event-stream` response, and set read/send timeouts that reflect measured provider latency. Example Nginx settings (illustrative; adapt service names and timeouts to the real deployment):

```nginx
location /chat/stream {
    proxy_pass http://shopsense_backend;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    proxy_buffering off;
    proxy_cache off;
    proxy_connect_timeout 5s;
    proxy_read_timeout 180s;
    proxy_send_timeout 180s;
}
```

Only configure trusted forwarded-header processing when the proxy is the only permitted network peer (or the trusted proxy addresses are explicitly defined). Keep URL validation and SSRF checks in the backend; proxy headers are not an authorization mechanism.

## Rate limits and quotas

- Authenticated middleware rate-limit keys use the verified user ID; requests without verified identity use the host-derived client address.
- The current in-process request-rate window is thread-safe and bounded in memory, but it is still **per application process**. When running multiple backend replicas, a shared atomic limiter (for example, Redis) is required for a truly global requests-per-minute limit.
- Monthly AI token accounting uses database-backed atomic reservations. SQLite and PostgreSQL are supported by the current upsert implementation; concurrent requests reserve estimated capacity before provider work and reconcile the reservation with consumed-token estimates afterward.
- Reservation leases expire after 15 minutes so a worker crash does not permanently hold quota. Provider usage is estimated from available response text lengths rather than billed-token counters when provider usage metadata is unavailable.

## Connection pooling

PostgreSQL uses configurable SQLAlchemy pool settings. The defaults are deliberately bounded:

| Setting | Default | Purpose |
|---|---:|---|
| `DB_POOL_SIZE` | `5` | Persistent connections per process |
| `DB_MAX_OVERFLOW` | `10` | Short burst allowance beyond the base pool |
| `DB_POOL_TIMEOUT_SECONDS` | `30` | Maximum wait for a pooled connection |
| `DB_POOL_RECYCLE_SECONDS` | `1800` | Recycle long-lived connections |

Tune these values from observed worker concurrency, database connection limits, and timeout metrics. Remember that total potential connections scale approximately with the number of backend processes/replicas. SQLite retains its dialect defaults.

Repeated outbound utility and live-search calls use shared HTTPX clients with bounded keep-alive pools. Request-specific timeout values, authentication headers, and query parameters remain per-request. SSRF-sensitive redirect validation intentionally continues to use its own short-lived client so each redirect can be revalidated.

## Product query performance

Product serialization reads the product category name. Catalog queries now eager-load category relationships in a bounded select-in query rather than issuing one lazy SELECT per result. Query-count tests guard empty-query search, filtered catalog search, and batch product lookup. Add new eager-load options only when a response actually reads those relationships; avoid loading reviews or other collections unnecessarily.

## Deployment checklist

1. Run the backend pytest suite, frontend unit tests, and production build.
2. Confirm the database tables are created/upgraded on the target database before sending traffic. Back up the database first for production schema changes.
3. Confirm the runtime has the expected `DATABASE_URL`, pool settings, `JWT_SECRET`, provider keys, and `CORS_ORIGINS`.
4. Test a live-price query, a non-live catalog query, authenticated rate limiting, quota rejection, and stream interruption/retry.
5. In a self-hosted environment, verify SSE buffering, HTTPS termination, host validation at ingress, payload limits, and forwarded-header trust.
6. Before scaling horizontally, replace the process-local request-rate window with shared atomic storage and check aggregate database and provider connection limits.
