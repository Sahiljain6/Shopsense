# ShopSense Production-Readiness Hardening Plan — 20 Parts

**Repository:** [Sahiljain6/Shopsense](https://github.com/Sahiljain6/Shopsense)  
**Application:** React + Vite frontend, FastAPI backend, SQLAlchemy database layer, AI provider integrations, optional SerpApi live-shopping search  
**Purpose:** Move from prototype-style assumptions to predictable, secure, observable operation without changing the storefront or disrupting working shopping features.

> **Safety rule:** This document is a plan, not permission to perform destructive database actions. Do not drop, recreate, stamp, or overwrite a database until its status and recovery options have been checked. Do not deploy an application-code change to production until its tests pass and its rollback is documented.

## Existing baseline to preserve

Repository review shows that ShopSense already has a substantial amount of reliability work: chat idempotency, rate limits and database-backed quota reservations, bounded SQLAlchemy/HTTPX pools, product-query eager loading, retailer caching/invalidation, request budgets, retries/backoff, circuit breakers, resource caps, CORS controls, production JWT-secret validation, request IDs and admin-only process-local metrics. These controls must be **verified and improved where needed, not blindly rewritten**. The codebase also already uses FastAPI/Pydantic request models and SQLAlchemy rather than Supabase.

Known operational issue to address first: a recent deployment log shows PostgreSQL DNS resolution failing for the configured database hostname and Alembic stopping the service. The cause may be a stale/wrong URL, a suspended database, or a deleted database. Confirm the provider state before changing code or creating a replacement.

For this app, enforce row ownership in the FastAPI/service/query layer. PostgreSQL Row-Level Security (RLS) can be evaluated as a separate defense-in-depth option, but do not enable it blindly: policies must work with the app's database role, migrations, local SQLite tests, seeding, and admin flows.

## Implementation protocol — do not skip

1. Work from a fresh branch based on the latest `main`; do not experiment directly on the production branch.
2. Keep each part to a focused PR, or group only closely related parts with independent commits and tests.
3. Record baseline behavior before code edits: frontend tests/build, backend tests, API smoke tests, and representative shopping prompts.
4. Do not change the UI layout, public API response shapes, provider precedence, product ranking, cart behavior, authentication flow, or SSE event contract unless a part specifically requires it.
5. Prefer additive, backward-compatible changes. For schema changes, use an expand → migrate/backfill → verify → contract sequence; never remove a column/table in the same release that stops using it.
6. A red test, failed build, failed migration check, unexpected schema diff, secret-scan finding, or unexplained production metric regression is a stop signal. Fix it before proceeding.
7. Never print secrets, database URLs, tokens, raw prompts, uploaded content, or entire request bodies in PR logs or application logs.
8. Do not claim tests passed unless a successful run is visible for the exact commit/PR head. A Vercel deployment check is not a substitute for backend tests.
9. Use a staging/test database for migration and failure-path testing. Never use production data as test fixtures.
10. Each merged part must include: scope, files changed, tests actually run, known limitations, deploy steps, rollback steps, and evidence of a healthy smoke test.

## Phase 1 — Security, recovery and data boundaries

### Part 1 — Recover and stabilize the database connection first (P0)
**Goal:** Restore a known, safe backend database state before any security refactor.

- Inspect the PostgreSQL service in Render and determine whether it is active, suspended, recoverable, or deleted. Check provider restore/backup options before creating a replacement.
- If the old database is accessible, take and verify an export/backup before migrations. Never publish the connection URL or credentials in logs, screenshots, issues, or this repository.
- Check the backend service's `DATABASE_URL` value and compare its hostname with the provider's current connection details. Do not reuse a hostname copied from an old or deleted service.
- If data cannot be recovered and the user accepts a fresh college-demo database, create a new database and update the backend environment variable. Confirm the expected dialect/driver, database region, and private/internal connectivity.
- Ensure production does not silently switch to ephemeral SQLite when PostgreSQL configuration is missing or broken. Keep the SQLite default for local development/tests only.
- Run the existing migration/startup process on the intended database and verify health, seeded sample products, sign-in, catalog search, and one AI request.

**Acceptance gate:** database host resolves; migrations finish; backend reaches ready state; catalog endpoints work; logs contain no credentials. If the old database is deleted, explicitly record that user accounts/history may not be recoverable without a backup.  
**Rollback:** restore the prior environment value only if that database still exists and is known-good. Do not delete either database during diagnosis.

### Part 2 — Capture a baseline and a recoverable release point (P0)
**Goal:** Know what works before changing it.

- Record current Git commit, deployment revision, frontend/backend URLs, environment names (not values), API routes, migration head, and current CI status.
- Run backend pytest, frontend tests, frontend production build, and current secret/dependency scans. Save summaries without exposing private environment data.
- Define critical smoke scenarios: anonymous home/catalog, sign-in, one catalog-grounded query, one comparison, one live-deal query, conversation history, wishlist/cart interactions, and SSE cancellation/retry.
- Add or update a concise rollback/runbook entry with the last known-good commit and deployment procedure.

**Acceptance gate:** failures are classified as pre-existing or newly introduced; no work proceeds with an unexplained baseline failure.  
**Rollback:** no runtime change; this part is documentation and evidence only.

### Part 3 — Separate local, staging and production configuration (P0)
**Goal:** Prevent a local default or test credential from being used in production.

- Define the allowed configuration for development, CI/test, staging and production. Keep provider/API keys, JWT secret and database URLs in environment-specific secret stores.
- Require a real PostgreSQL `DATABASE_URL` in production; fail with a sanitized, actionable startup error if it is absent or malformed. Do not transparently use a local file database in production.
- Preserve local SQLite support for offline development and fast tests.
- Validate required production settings at startup, including `ENVIRONMENT`, `JWT_SECRET`, CORS origins, database driver and provider configuration as applicable.
- Document exactly which variables are public frontend configuration (for example the API base URL) and which are backend-only secrets.

**Acceptance gate:** tests prove production configuration rejects missing/place-holder secrets and an absent/wrong database URL without printing its value; development and CI continue to start as designed.  
**Rollback:** revert configuration validation only if it blocks a documented valid deployment, and retain the failure tests.

### Part 4 — Audit hardcoded secrets and Git history (P0)
**Goal:** Detect secrets even if they are no longer present in the current tree.

- Audit tracked files, history, branches and CI logs for provider keys, database URLs, JWT secrets, OAuth client secrets, tokens and private certificates.
- Retain the existing secret-scanning workflow; add a controlled TruffleHog Git-history scan or equivalent if it is not already covered. Run it with a least-privilege token and avoid printing secret values in shared logs.
- Verify `.env`, `backend/.env`, frontend local environment files, generated databases, build outputs and credential files are ignored. Commit only sanitized `.env.example` placeholders.
- For every confirmed exposure, revoke/rotate the credential at its provider first, update the environment store, and then consider history cleanup. Rewriting history is a coordinated operation and does not replace rotation.
- Keep provider credentials server-side; never place them in `VITE_*` variables or browser storage.

**Acceptance gate:** current-tree scan and history scan have documented results; all confirmed exposed credentials are rotated; normal CI includes secret scanning.  
**Rollback:** do not revert a credential rotation. If history rewriting is required, coordinate collaborator clones and preserve a secure audit note without the secret itself.

### Part 5 — Audit authorization and prevent cross-user access (P0)
**Goal:** Authentication must not allow one user to read or alter another user's data.

- Inventory every user-owned resource and endpoint: conversations/messages/summaries, chat history, wishlist, orders, usage/quota, uploads, and admin operations.
- Enforce ownership in the service/database query itself (for example, lookup by both resource ID and authenticated user ID), not only by hiding buttons in React.
- Return consistent 404/403 responses without revealing whether another user's resource exists. Ensure admin endpoints require an explicit admin authorization dependency.
- Review raw SQL and administrative queries for missing tenant/user filters. Use parameterized SQLAlchemy/text bindings rather than string interpolation for values.
- Add a two-user authorization matrix to the tests. Consider PostgreSQL RLS only after explicit policy design and tests with the exact production database role; preserve SQLite test behavior until proven equivalent.

**Acceptance gate:** user A cannot read, edit, delete or infer user B's records across every tested route; unauthenticated calls and non-admin admin calls are rejected.  
**Rollback:** revert only the faulty endpoint change, not the authorization check; disable a newly added RLS policy only through a documented migration rollback if it blocks legitimate service access.

### Part 6 — Validate all API inputs and output boundaries (P0)
**Goal:** Client-side validation is usability support, not a security boundary.

- Inventory API request bodies, query parameters, path IDs, pagination/sort fields, image/upload inputs, OAuth callback data and webhook-like callbacks (if introduced).
- Use strict Pydantic models with length/range limits, enums, allowed fields, file-size/type checks and clear rejection behavior. Reject unexpected fields where that improves safety without breaking documented clients.
- Confirm SQL uses ORM expressions or bound parameters; test injection-shaped inputs against search and filter endpoints.
- Keep React rendering escaped by default. Audit `dangerouslySetInnerHTML`, Markdown rendering, URLs, SVG/data URLs, and user-provided product/review text; add sanitization only where untrusted HTML is intentionally supported.
- Ensure malformed requests return stable 4xx responses and cannot crash workers or expose traceback details.

**Acceptance gate:** boundary tests cover empty, oversized, malformed, Unicode, injection-shaped and XSS-shaped inputs; no public endpoint relies solely on frontend checks.  
**Rollback:** keep stricter validation behind a compatibility check if existing valid clients are affected; do not remove server-side limits.

### Part 7 — Verify rate limiting, quotas and authentication abuse controls (P1)
**Goal:** Prevent brute force, scraping and uncontrolled spending on AI/search providers.

- Verify current rate limiting for sign-in/sign-up, chat REST/SSE, live retailer search, image uploads, account recovery and other expensive routes.
- Ensure the limiter runs before expensive AI or retailer provider calls, uses authenticated user identity when verified, and uses only trustworthy client-IP information from the managed host.
- Verify that quota reservations are atomic and released/finalized on success, timeout, cancellation and exceptions; idempotent chat replays must not launch another paid model call.
- Document process-local versus shared/global limits. Do not add Redis solely for appearances; require it only if traffic scales beyond the current single-process guarantees.
- Add alerting/limits at provider dashboards where available.

**Acceptance gate:** concurrent tests prove limits and quotas; denied traffic makes no provider call; retry/replay does not double-charge the application's quota.  
**Rollback:** revert limit tuning if legitimate traffic is blocked, while retaining baseline protection and tests.

## Phase 2 — Resiliency and architecture

### Part 8 — Make migrations explicit, tested and reversible (P0)
**Goal:** A database outage or incompatible schema must not lead to silent data loss or an endless crash loop.

- Separate schema migration execution from normal serving where the hosting setup permits; otherwise ensure startup migration behavior is explicit, bounded and observable.
- Test Alembic migrations on a fresh PostgreSQL database and a copy of the expected prior schema; keep SQLite tests for supported local workflows.
- Adopt expand/backfill/verify/contract migrations; avoid drop/recreate shortcuts and avoid automatically stamping an unknown revision as current without schema verification.
- Take a backup/snapshot before production schema changes when provider capabilities allow; record migration head before/after and define the rollback/recovery path.
- Test missing DNS, refused connection, invalid credentials, locked schema and failed migration behavior.

**Acceptance gate:** migration errors stop traffic safely with sanitized diagnostics; fresh database and upgrade-from-current-schema tests pass; failed migration instructions are documented.  
**Rollback:** use a forward-fix or tested rollback migration. Do not manually edit Alembic revision tables to suppress an error.

### Part 9 — Bound external integrations and standardize failures (P1)
**Goal:** AI providers, SerpApi, Google sign-in and utility APIs may fail without taking down unrelated features.

- Inventory outbound HTTP/SDK calls and confirm explicit connect/read/total timeouts, response-size caps and safe redirect handling.
- Reuse the current bounded clients and circuit breakers; avoid stacking hidden SDK retries on top of application retries.
- Normalize provider errors into internal categories; log safe metadata (provider, status, error type, request ID) but not raw credentials, prompts, or upstream response bodies.
- Keep fallback order and provider-selection semantics unchanged unless separately approved.
- Verify SSRF controls for user-influenced URLs and uploads; never fetch arbitrary schemes/hosts.

**Acceptance gate:** tests simulate timeout, DNS error, 429, 5xx, invalid JSON and authentication failure; unrelated catalog endpoints remain available where their dependencies do not require the failed service.  
**Rollback:** revert only the change that causes an incompatible provider behavior; keep explicit timeouts.

### Part 10 — Make retry/idempotency behavior safe across mutations (P1)
**Goal:** Retrying a request must not repeat a non-repeatable action.

- Preserve the existing persisted chat idempotency receipt and stream-to-REST retry behavior.
- Inventory all state-changing APIs. Mark each operation safe to retry, idempotent with a stable key, or never automatically retryable.
- Retry only transient errors and methods/operations proven safe; respect `Retry-After`, the overall request deadline and user cancellation.
- Do not hold database locks/transactions while waiting for AI/provider calls or backoff.
- Add concurrency tests for duplicate chat submissions, wishlist races and any future checkout/payment/order mutation.

**Acceptance gate:** one logical chat submission cannot create duplicate model work from a retry; unkeyed unsafe mutations are not automatically replayed.  
**Rollback:** disable the new retry path rather than weakening idempotency or replay safety.

### Part 11 — Add graceful degradation and clear client errors (P1)
**Goal:** A dependency failure should produce a bounded, understandable response instead of a blank screen or misleading answer.

- Define behavior when PostgreSQL is unavailable, an AI provider is down, SerpApi returns no listings, a utility API times out, or an SSE connection is interrupted.
- Use a sanitized error envelope and request ID; keep stack traces and private provider details in protected server logs only.
- Never invent current prices, discounts, ratings or availability when live search fails. Label static catalog data and live listings distinctly.
- Keep dependency-specific features unavailable when necessary, but preserve independent pages and endpoints where feasible.
- Test React loading, empty, timeout, retry, cancellation and error states without redesigning the existing interface.

**Acceptance gate:** fault-injection tests produce deliberate status codes/messages; no blank/unhandled frontend state; no fabricated live-deal claims.  
**Rollback:** revert UI/error-envelope changes if the existing API contract is broken; preserve honest failure behavior.

### Part 12 — Protect persistence, seed data and recovery (P0)
**Goal:** Distinguish recoverable demo catalog data from non-reconstructable user data.

- Document which data is seeded from code and which data is created by users. Sample products may be recreated; accounts, conversations, wishlists and orders cannot be reconstructed from seed data.
- Make seeding idempotent, versioned and safe for an empty database; test repeated startup and partial failure.
- Choose a database tier/backup method that matches the data's value. If managed backups are unavailable, document a scheduled export and its secure storage/retention.
- Perform a restore drill into a separate database and verify counts/schema plus representative reads before claiming the backup works.
- Keep personally identifiable data out of fixtures, demo accounts and logs.

**Acceptance gate:** a written recovery procedure is demonstrated on a non-production copy; restore duration/data-loss window are recorded; seeding does not duplicate catalog rows.  
**Rollback:** restore to a separate instance and cut over only after verification; never overwrite the source database during recovery tests.

### Part 13 — Reduce unsafe coupling without a full rewrite (P1)
**Goal:** Improve reviewability while preserving behavior.

- Map API routes → validation schemas → services/orchestration → data access → response schemas.
- Move only clearly mixed responsibilities into existing module patterns; avoid mass renaming or broad package restructures.
- Keep public API schemas, frontend class hooks, routing, cart state, authentication and AI provider precedence stable.
- Introduce dependency injection or repository boundaries only where they improve tests and ownership enforcement; avoid abstractions that add indirection without benefit.
- Use focused characterization/regression tests before moving logic.

**Acceptance gate:** API response snapshots and existing tests remain stable; each refactor has a narrow diff and a measured reason.  
**Rollback:** revert the isolated refactor PR; do not combine it with schema and UI redesigns.

### Part 14 — Make logs structured, private and actionable (P0)
**Goal:** Diagnose incidents without logging sensitive user content.

- Use consistent structured fields: timestamp, severity, environment, request ID, route template, status, duration, safe error category and service/provider name.
- Audit every `print`, exception handler and provider error path. In particular, remove raw request-body logging from validation errors; do not log `exc.body`, full query strings, cookies, authorization headers, API keys or full database URLs.
- Preserve server-side stack traces in protected logs where useful, while returning sanitized client responses.
- Prevent log injection by normalizing control characters and avoid high-cardinality labels such as raw user IDs, prompts and URL query values.
- Define log retention/access and a minimal incident triage guide.

**Acceptance gate:** tests assert that known secret/prompt/body sentinels never appear in captured logs; request IDs connect the client error to safe server diagnostics.  
**Rollback:** do not restore sensitive payload logging; revert only formatting changes if log ingestion breaks.

## Phase 3 — Observability, delivery and operations

### Part 15 — Automate dependency and supply-chain review (P1)
**Goal:** Detect vulnerable or unmaintained dependencies before deployment.

- Run Python and npm dependency audit tooling in CI; use an appropriate scanner for known vulnerabilities and optionally generate an SBOM for releases.
- Pin dependencies/lockfiles and review changes rather than blindly applying `npm audit fix --force` or broad major upgrades.
- Group upgrades into focused PRs; review runtime compatibility and license/security advisories.
- Add dependency scanning to pull requests and a scheduled workflow, with a documented path for accepted risks and urgent fixes.

**Acceptance gate:** scanners run reproducibly; findings are triaged with severity/owner; breaking dependency changes have tests.  
**Rollback:** revert a risky dependency update, not the scanner; document any temporary security exception and expiry.

### Part 16 — Establish CI quality gates that block unsafe merges (P0)
**Goal:** Every relevant change is tested before it can be merged or deployed.

- Verify workflow triggers for pull requests and pushes to active feature branches. Avoid a workflow configuration that accidentally skips stacked PRs.
- Run backend tests, frontend tests, production build, lint/type checks where configured, migration checks against PostgreSQL, secret scans and dependency scans.
- Add regression tests for newly fixed bugs and ensure tests use fake/mock external AI/search APIs rather than paid live calls.
- Configure required status checks and protect `main` against accidental direct pushes where repository settings permit.
- Treat the exact final PR head as the validation unit; record tests that could not run.

**Acceptance gate:** a deliberately failing test blocks a green CI status; all required jobs pass for the commit under review.  
**Rollback:** revert the application change if CI cannot pass; don't disable a failing required check just to merge.

### Part 17 — Make deployment safe and repeatable (P1)
**Goal:** Keep failed or unnecessary deployments away from the production demo.

- Define the production branch and which Vercel/Render services auto-deploy from it. Use previews/staging for feature branches and never rely on a preview build to prove backend tests passed.
- Deploy only a commit whose required CI jobs passed; verify hosting/deployment quotas before repeated manual redeploys.
- Record the expected frontend/backend commit pairing, health endpoint result and migration version.
- Apply configuration changes through hosting environment settings, not source commits. Redact environment output during incident sharing.
- Do not introduce a proxy, gateway, load balancer, Redis or queue unless current topology and measurements require it.

**Acceptance gate:** a tested staging deploy passes smoke checks before production; the production URL and deployed commit are recorded.  
**Rollback:** use host-supported rollback to the last known-good application version and restore the previous compatible environment configuration.

### Part 18 — Enforce environment boundaries, CORS and security headers (P1)
**Goal:** Prevent previews and local tools from accidentally reaching or trusting production resources.

- Maintain separate local/test/staging/production credentials and databases; never copy production user records into test.
- Audit exact production CORS origins and the constrained preview-origin regex; CORS is not authorization.
- Confirm HTTPS and managed ingress behavior, trusted forwarded headers, host handling, CSP, HSTS, frame restrictions and content-type protections.
- Ensure development-only diagnostics and permissive CORS do not activate in production.
- Test preflight and error responses from approved and unapproved origins without exposing credentials.

**Acceptance gate:** approved origins work; unapproved origins are blocked; browser security headers and frontend auth behavior remain functional.  
**Rollback:** revert only the faulty origin/header adjustment and retain the prior allow-list; never switch production to wildcard credentialed CORS.

### Part 19 — Add targeted integration and fault-injection tests (P1)
**Goal:** Test realistic failure modes, not only the happy path.

- Add a small automated smoke suite for health/readiness, login, catalog browsing, intent-specific chat, comparison, live deal lookup, SSE cancellation and saved-data access.
- Simulate database DNS/connectivity failure, migration failure, provider timeout/rate limit, malformed provider output, oversized input, concurrent requests and user A attempting to access user B's records.
- Test frontend behavior on 401/403/404/409/429/5xx, timeout, offline state and malformed SSE events.
- Track baseline latency/error rate for representative queries; use the same test set after a release.
- Keep destructive or load-heavy tests against isolated staging only.

**Acceptance gate:** all essential tests pass on a fresh environment and a staging deployment; each injected failure has an expected result and bounded resource usage.  
**Rollback:** halt release if critical smoke tests fail; do not “fix” a test by weakening a safety invariant.

### Part 20 — Release, monitor and prove recoverability (P0 final gate)
**Goal:** Release only when the system has a clear health signal and recovery path.

- Prepare a release checklist: CI green, migration verified, environment variables verified without exposing values, secret/dependency scan reviewed, backup/restore status recorded, and smoke tests passing.
- Deploy in a controlled window; verify backend health, frontend requests, authentication, product catalog, AI responses, SSE completion and error rate.
- Watch request ID logs, latency/error counts, database connection failures, provider circuit breakers, rate-limit events and hosting deployment status.
- Define objective rollback triggers (for example, failed health checks, repeated migration/startup failure, elevated 5xx, broken sign-in or broken chat). Roll back rather than applying emergency unreviewed edits to production.
- Run a recovery rehearsal after major database changes and keep the runbook current.

**Acceptance gate:** no known critical security finding, tests green for the release commit, smoke tests green, and a usable rollback/recovery procedure. Production readiness is an ongoing control, not a promise of zero failures.

## Execution order and batching

Use these batches only after each prior batch passes its acceptance gate:

| Batch | Parts | Main purpose |
|---|---|---|
| A | 1–2 | Stabilize database, protect recovery options, capture a clean baseline |
| B | 3–7 | Environment separation, secret history, authorization, input validation, abuse controls |
| C | 8–12 | Migration safety, dependency failures, idempotency, graceful degradation, backups/seed recovery |
| D | 13–16 | Targeted architecture cleanup, privacy-safe logs, dependency scanning, CI gates |
| E | 17–20 | Deployment controls, environment/network boundaries, fault tests, release and rollback |

## Definition of done

- No code change is made directly on `main` or directly against the live database during development.
- Backend tests, frontend tests/build, migration checks, secret scanning and dependency checks pass on the final reviewed commit.
- Cross-user access tests, malformed input tests, external-service failure tests and startup/database-failure tests pass.
- No secrets or raw user content appear in logs or CI output.
- Existing layout, API contracts, authentication, cart behavior, response pipeline and provider precedence remain compatible unless a reviewed part explicitly requires a change.
- Database recovery is documented and rehearsed; sample seed data is distinguished from user-generated data.
- Every part's PR states what changed, what was actually tested, limitations, deploy steps and rollback steps.

**Important limitation:** this plan reduces risk but cannot guarantee that a cloud platform, database or external AI provider will never fail. The goal is to make failures bounded, observable, recoverable and safe for users.
