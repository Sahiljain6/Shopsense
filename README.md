# ShopSense

**An AI shopping copilot for Indian e-commerce.** ShopSense combines conversational product discovery, catalog-based recommendations, retailer search, and AI-assisted buying decisions in one full-stack web app.

[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=111827)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-6-646CFF?logo=vite&logoColor=white)](https://vite.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

---

## Contents

- [What it does](#what-it-does)
- [Architecture](#architecture)
- [Live product search with SerpApi](#live-product-search-with-serpapi)
- [Run locally](#run-locally)
- [Run with Docker Compose](#run-with-docker-compose)
- [Environment variables](#environment-variables)
- [Production engineering roadmap](#production-engineering-roadmap)
- [Production readiness and hardening plan](#production-readiness-and-hardening-plan)
- [Deployment hardening](#deployment-hardening)
- [Reliability and security operations](#reliability-and-security-operations)
- [API overview](#api-overview)
- [Tests and code quality](#tests-and-code-quality)
- [Repository layout](#repository-layout)
- [Troubleshooting](#troubleshooting)
- [Security and data accuracy](#security-and-data-accuracy)

## What it does

ShopSense is a modular example of how to combine a chat interface, a backend API, product data, and an LLM into a shopping workflow.

| Capability | How it works |
|---|---|
| Conversational shopping | Users describe a product, budget, brand, or use case in natural language. |
| Catalog recommendations | The backend searches and ranks the local product catalog against extracted constraints. |
| Current retailer listings | Optional SerpApi Google Shopping integration fetches structured listings, retailer links, images, prices, ratings, and available old-price fields. |
| Search fallback | If SerpApi is not configured or unavailable, ShopSense can fall back to DuckDuckGo search when the dependency is available. Fallback results may not have structured prices or images. |
| Model-provider flexibility | Supports configured OpenAI-compatible, Gemini, Groq, Hugging Face, and Ollama routes; exact provider selection depends on configured keys and backend precedence. |
| Streaming chat | The backend sends Server-Sent Events (SSE) for response text, product results, live listings, and completion metadata. |
| Product comparison | Resolves catalog products independently for common “X vs Y” comparisons and prepares a structured explanation. |
| Shopping utilities | Includes supporting workflows for currency conversion, delivery PIN-code information, EMI planning, image-based product identification, and saved shopping data. |
| Sign-in and persistence | FastAPI handles authentication and the relational data layer; chat and catalog features use backend models and services. |
| Responsive web interface | React and Vite power the chat, product cards, shopping cart, and supporting screens. |

## Architecture

~~~mermaid
flowchart TD
    Shopper[Shopper] --> UI[React + Vite frontend]
    UI -->|REST / SSE| API[FastAPI API]
    API --> Auth[Auth, validation, rate limits]
    API --> Orchestrator[Shopping AI orchestrator]
    API --> Database[(SQLite or PostgreSQL)]
    Orchestrator --> Catalog[Catalog search and ranking]
    Catalog --> Database
    Orchestrator --> LiveSearch[Live shopping search]
    LiveSearch -->|SERPAPI_API_KEY configured| SerpApi[SerpApi Google Shopping]
    LiveSearch -->|No key or provider failure| DDG[DuckDuckGo fallback]
    Orchestrator --> LLM[Configured LLM provider]
    LLM --> Orchestrator
    Orchestrator --> API
    API -->|JSON / SSE: answer + products + live_deals| UI
~~~

**Request flow**

1. The frontend submits the user's message, recent conversation history, and relevant cart context.
2. FastAPI validates the payload and applies the endpoint's authentication, quota, and rate-limit rules.
3. The shopping orchestrator classifies the request and gathers relevant catalog or external shopping data.
4. For live pricing/deal queries, SerpApi is preferred when configured. Results are normalized into a predictable live_deals schema and cached in memory for 15 minutes.
5. The response returns to the frontend. Live retailer listings have their own cards so product images, listing links, prices, and freshness information can be shown separately from the seeded catalog.

## Live product search with SerpApi

ShopSense uses the [SerpApi Google Shopping API](https://serpapi.com/google-shopping-api) to retrieve shopping listings. The integration lives in **backend/app/services/live_search.py**.

### Configure a key

1. Create an account at [SerpApi](https://serpapi.com/) and copy your API key from its dashboard.
2. Add the key to **backend/.env** for local development or to your backend host's environment variables.
3. Set the market location if you need results for a different Indian city.

~~~dotenv
SERPAPI_API_KEY=your_serpapi_api_key
SERPAPI_LOCATION=Mumbai, Maharashtra, India
~~~

**Keep this key on the backend.** Do not name it VITE_SERPAPI_API_KEY, put it in frontend code, or commit a real key.

### What the integration returns

The normalized live_deals entries can include:

| Field | Meaning |
|---|---|
| title | Product/listing title returned by shopping search |
| price, currency | Parsed listing price and currency |
| old_price, discount_percentage | Previous/listed price and estimated reduction, when provided by the search result |
| source, url | Retailer name and outbound listing link |
| image_url | Product thumbnail URL, when available |
| rating, reviews | Listing rating and review count, when available |
| retrieved_at | Timestamp when ShopSense fetched the search result |
| provider, is_live | Provenance metadata for the result |
| trust_score, is_verified, warning | ShopSense retailer trust metadata; not a guarantee about an individual seller or item |

The backend applies a **15-minute in-process cache** to reduce repeated queries and conserve API quota. The cache is per running process; a restart clears it, and multiple backend instances do not share the same cache.

The integration requests India-focused results (gl=in, English interface, configurable location). Retailer inventory, promotions, shipping fees, image availability, and checkout prices can still change. Old-price and discount fields are shown only when the provider supplies enough data to calculate them.

SerpApi offers a quota-limited plan. Check [current pricing and limits](https://serpapi.com/pricing) before deployment because plans and usage allowances can change.

### How to try it

Once a valid key is configured, sign in to ShopSense and ask a query that clearly requests current retailer data, for example:

> Find the latest prices and deals for Sony wireless headphones in India.

The backend will use live search for pricing/deal queries. If SerpApi is missing or fails, fallback web search may not have product images or structured price values. A listing is a search snapshot—not a promise that a price is still available at checkout.

## Run locally

### Prerequisites

- Python **3.12 or later** (3.12 is the version used for the project badge).
- Node.js **20 or later** and npm.
- A database: SQLite is simplest for local development; PostgreSQL is supported.
- At least one supported LLM provider key for AI-generated answers.
- Optional: a SerpApi key for structured live Google Shopping results.
- Optional: Docker and Docker Compose.

### 1. Clone the repository

~~~bash
git clone https://github.com/Sahiljain6/Shopsense.git
cd Shopsense
~~~

### 2. Configure the backend

Copy the sample environment file:

~~~bash
# macOS / Linux
cp backend/.env.example backend/.env

# Windows PowerShell
Copy-Item backend/.env.example backend/.env
~~~

Edit **backend/.env**. For the easiest local database setup, change DATABASE_URL to SQLite:

~~~dotenv
DATABASE_URL=sqlite:///./shopsense.db
ENVIRONMENT=development
OPENAI_API_KEY=
GEMINI_API_KEY=
GROQ_API_KEY=
OLLAMA_API_KEY=
SERPAPI_API_KEY=
SERPAPI_LOCATION=Mumbai, Maharashtra, India
~~~

Add the key for the model provider you intend to use. You do not need to configure every provider. Keep a strong, private JWT_SECRET for any shared or hosted deployment. The sample values are for local setup only.

Create and activate a virtual environment, then install backend dependencies:

~~~bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.venv/Scripts/Activate.ps1

pip install -r backend/requirements.txt
~~~

Start the API from the repository root so backend/.env can be found:

~~~bash
python -m uvicorn app.main:app --app-dir backend --reload --port 8000
~~~

The API should be available at [http://127.0.0.1:8000](http://127.0.0.1:8000). Interactive Swagger documentation is at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### 3. Configure and start the frontend

In another terminal:

~~~bash
cd frontend
npm install
~~~

Create **frontend/.env.local** with the local backend URL:

~~~dotenv
VITE_API_URL=http://127.0.0.1:8000
~~~

Start Vite:

~~~bash
npm run dev
~~~

Open the local URL printed by Vite (normally [http://localhost:5173](http://localhost:5173)). Register or sign in through the application before using protected chat endpoints.

## Run with Docker Compose

Docker Compose starts PostgreSQL, the backend, and the frontend together.

1. Copy **backend/.env.example** to **backend/.env**.
2. Add your LLM API key and optional SERPAPI_API_KEY.
3. From the repository root run:

~~~bash
docker compose up --build
~~~

Open [http://localhost:3000](http://localhost:3000). Compose configures the backend to connect to the PostgreSQL service and points the frontend at the local API. To stop the services, run **docker compose down**; add **-v** only if you also intend to remove the persisted database volume.

## Environment variables

All secrets belong in backend environment variables or backend/.env, never in client-side source code.

| Variable | Required | Purpose |
|---|---|---|
| OPENAI_API_KEY | One provider required | OpenAI provider credentials |
| GEMINI_API_KEY | Alternative provider | Gemini provider credentials |
| GROQ_API_KEY | Alternative provider | Groq provider credentials |
| OLLAMA_API_KEY | Alternative provider | Ollama Cloud credentials, when used |
| HF_TOKEN or HUGGINGFACE_API_KEY | Alternative provider | Hugging Face inference credentials |
| SERPAPI_API_KEY | Optional | Enables structured Google Shopping results |
| SERPAPI_LOCATION | Optional | Shopping search location; defaults to Mumbai, Maharashtra, India |
| DATABASE_URL | Recommended | SQLAlchemy connection URL; use SQLite locally or PostgreSQL for shared deployments |
| DB_POOL_SIZE | Optional | Base SQLAlchemy pool size for PostgreSQL; defaults to 5 |
| DB_MAX_OVERFLOW | Optional | Temporary connections above the base pool; defaults to 10 |
| DB_POOL_TIMEOUT_SECONDS | Optional | Maximum time to wait for a pooled DB connection; defaults to 30 seconds |
| DB_POOL_RECYCLE_SECONDS | Optional | Recycle interval for pooled DB connections; defaults to 1800 seconds |
| DB_LOCK_TIMEOUT_MS | Optional | Database lock wait limit; defaults to 5000 ms |
| DB_STATEMENT_TIMEOUT_MS | Optional | PostgreSQL statement timeout; defaults to 30000 ms |
| MAX_REQUEST_BODY_BYTES | Optional | Declared HTTP body size cap; defaults to 10 MiB |
| LIVE_SEARCH_CACHE_TTL_SECONDS | Optional | Per-process retailer snapshot TTL; defaults to 900 seconds |
| LIVE_SEARCH_CACHE_MAX_ENTRIES | Optional | Per-process retailer cache cap; defaults to 256 entries |
| AI_PROVIDER_TIMEOUT_SECONDS | Optional | Individual AI provider request budget; defaults to 30 seconds |
| AI_PROVIDER_CHAIN_TIMEOUT_SECONDS | Optional | Total AI provider/model fallback budget; defaults to 75 seconds |
| JWT_SECRET | Required in production | Signing secret for application tokens; use a private random value |
| ENVIRONMENT | Optional | Set to production for production validation |
| CORS_ORIGINS | Deployment-specific | Comma-separated frontend origins allowed by the API |
| ENABLE_MULTI_AGENT | Optional | Enables the LangGraph path when set to true |
| GOOGLE_CLIENT_ID | Optional | Google identity sign-in configuration |
| PINCODE_API_KEY, PINCODE_API_URL | Optional | Configuration for supported PIN-code integration |

Provider selection follows the backend's configured precedence. Configure the provider you intend to use and review **backend/app/core/config.py** and **backend/app/services/ai.py** if you change provider routing.

## API overview

FastAPI's interactive API documentation at **/docs** is the source of truth for the complete schemas and authentication requirements. Common endpoints include:

| Endpoint | Purpose |
|---|---|
| GET /health | Health-check endpoint |
| POST /auth/register, POST /auth/login | Account creation and sign-in |
| GET /auth/me | Current authenticated user |
| GET /products | Search catalog products |
| POST /chat | Non-streaming AI shopping response (includes live_deals when found) |
| POST /chat/stream | SSE chat response; sends answer chunks, products, a live_deals event, and completion metadata |
| POST /fetch-link | Extract product details from a user-supplied product URL |
| POST /identify-image | Identify a product from an uploaded image |
| POST /compare | Compare selected catalog products |
| GET /products/{product_id}/price-history | Read stored price-history snapshots |
| GET /admin/ops/metrics | Admin-only bounded operational metrics, cache stats, and circuit-breaker state |

Chat endpoints use the application's authentication and quota controls. See the response schemas in **backend/app/schemas/api.py** for the ChatResponse and LiveDeal data structures. A language-agnostic API contract is also maintained in [docs/ai_backend_api_v1.json](./docs/ai_backend_api_v1.json).

## Tests and code quality

Run backend tests from the repository root:

~~~bash
python -m pytest -v backend/tests
~~~

Run frontend tests and production build:

~~~bash
cd frontend
npm test
npm run build
npm run lint
~~~

The live search tests mock the SerpApi response; they do not require a paid search call or real API key. For a manual integration test, configure your own key and try a current-price query from the UI.

## Repository layout

~~~text
Shopsense/
├── backend/
│   ├── app/
│   │   ├── api/                 # FastAPI route handlers
│   │   ├── core/                # Configuration, security, quotas, and middleware
│   │   ├── db/                  # Database engine and sessions
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/api.py       # Request and response schemas, including LiveDeal
│   │   └── services/
│   │       ├── ai.py            # AI orchestration and tool calls
│   │       ├── live_search.py   # SerpApi integration, result normalization, cache, fallback
│   │       ├── catalog.py       # Local catalog access
│   │       ├── search.py        # Catalog matching and ranking
│   │       └── agents/          # Optional multi-agent workflow
│   ├── tests/                  # Backend regression tests
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/         # Chat, catalog cards, and live deal cards
│   │   ├── hooks/              # React hooks, including cart state
│   │   ├── tests/               # Frontend unit tests
│   │   ├── utils/               # API formatting and SSE parsing
│   │   └── styles/              # Application styles
│   └── package.json
├── docs/                       # API contract and project documentation
├── docker/                     # Docker build definitions
├── docker-compose.yml
└── README.md
~~~

## Troubleshooting

**I still see catalog data instead of live listings**
- Confirm that SERPAPI_API_KEY is set in the backend environment and that the key has available quota.
- Ask a query containing a clear live-price intent, such as “latest price”, “current deals”, or “today's offers”.
- Check backend logs for the generic SerpApi failure notice. The API key is intentionally not printed in logs.
- Without successful SerpApi results, fallback web search may not have product images or numeric prices.

**The frontend cannot connect to the backend**
- Confirm the API is running and open [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health).
- Verify VITE_API_URL in frontend/.env.local.
- Check that your frontend origin is allowed by CORS_ORIGINS.

**The first response is slow**
- A free hosted backend may be waking from an idle state.
- Live search can add a network request on price/deal queries; repeated matching queries are cached for 15 minutes per backend process.
- The model provider and its rate limits also affect response latency.

## Caching, scaling, and request budgets

See [docs/caching-scaling-and-api-governance.md](./docs/caching-scaling-and-api-governance.md) for live-search cache TTL/key/invalidation rules, the prerequisites for adding backend replicas, why a separate API gateway is currently deferred, and frontend/backend timeout budgets. Cache and AI timeout settings are documented in `backend/.env.example`. The browser's default overall API/stream budget is 105 seconds; callers may set lower per-request budgets, and an explicit user cancellation is not retried.

## Reliability and security operations

See [docs/reliability-security-operations.md](./docs/reliability-security-operations.md) for retry/idempotency rules, jitter and `Retry-After`, circuit breakers, database lock timeouts, request/upload/SSE limits, CORS policy, secret-handling notes, and the admin-only operational metrics endpoint. Webhooks remain intentionally deferred until a trusted event producer and a verified event contract exist.

## Production engineering roadmap

The original 20-part reliability roadmap is tracked in [docs/production-engineering-roadmap.md](./docs/production-engineering-roadmap.md). It covers request idempotency, rate limiting and quota accounting, connection pooling, product query performance, bounded caching, request budgets, retries, circuit breakers, resource limits, CORS, secrets, and observability.

## Production readiness and hardening plan

The expanded [20-part production-readiness hardening plan](./docs/production-readiness-hardening-plan.md) organizes work into three phases:

1. **Security and data boundaries:** database recovery, baseline tests, environment separation, Git-history secret scanning, authorization, input validation, and abuse controls.
2. **Resiliency and architecture:** safe database migrations, external-service failure handling, idempotent retries, graceful degradation, data recovery, focused architecture cleanup, and privacy-safe logging.
3. **Observability and operations:** dependency scanning, CI quality gates, safe deployments, environment isolation, failure-injection tests, monitoring, and rollback procedures.

**Implementation order matters.** Start by verifying whether the configured PostgreSQL database is active, suspended, recoverable, or deleted. Preserve any available backup before attempting schema changes or creating a replacement. A fresh database can be reseeded with the sample catalog, but it cannot recreate deleted user accounts, conversations, wishlists, or orders unless a usable backup exists.

The plan is intended to be implemented in small, reviewed changes. Existing reliability controls should be verified and strengthened rather than rewritten blindly. Keep the current UI, API contracts, authentication, cart behavior, shopping logic, AI-provider precedence, and SSE behavior compatible unless a specific reviewed change requires otherwise. Each implementation step should pass backend tests, frontend tests/build, migration checks where relevant, and security scans before deployment. The plan describes intended work; consult merged code and CI results to determine what is actually implemented and verified.

## Deployment hardening

See [docs/deployment-hardening.md](./docs/deployment-hardening.md) for managed-host guidance, safe reverse-proxy/SSE settings for self-hosted deployments, rate-limit and quota scope, database connection-pool tuning, and product query-performance notes.

## Security and data accuracy

- Never commit .env files, provider keys, passwords, access tokens, or production secrets.
- Configure SERPAPI_API_KEY only on the backend. The frontend receives normalized product listing fields, not the key.
- Treat product descriptions, snippets, and external links as untrusted data. Review seller terms before purchasing.
- A retailer trust badge is an application heuristic, not a guarantee about seller legitimacy, product authenticity, warranty, or refund outcomes.
- Live shopping results are retrieved snapshots. Confirm the listing, final price, shipping, availability, and return conditions on the retailer's checkout page.
- Use a unique production JWT_SECRET, restrict CORS to trusted sites, and keep dependencies updated.

## License

Distributed under the license in [LICENSE](./LICENSE).
