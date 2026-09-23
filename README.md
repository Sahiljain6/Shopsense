# ShopSense 🛍️

> **AI Shopping Copilot for India** — grounded catalog search, live retailer comparison, and cart-aware recommendations powered by Gemini / Groq / OpenAI.

[![Live Demo](https://img.shields.io/badge/demo-live-brightgreen)](shopsense-theta.vercel.app)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://react.dev/)

---

## ✨ What It Does

ShopSense is a full-stack AI shopping assistant purpose-built for Indian e-commerce workflows:

| Feature | Details |
|---|---|
| **Fastshot Glassmorphic UI** | Full-viewport cinematic ambient stage with background video toggle, floating glass composer dock, and quick actions toolbar |
| **Multi-Agent Persona Switcher** | Dynamic runtime engine selection (`Sonnet 4.5` for deep comparisons, `Gemini Flash` for live web prices, `Deal Specialist` for logistics and visual inspection) |
| **Grounded catalog search** | Vector-like ranked search across 40+ curated products; budget + category filters applied before the LLM sees results |
| **Live web search** | Fetches real-time retailer pages (Amazon IN, Flipkart, Croma) and surfaces benchmark deal pricing snippets |
| **Comparison engine** | `"X vs Y"` queries pre-check and resolve both products independently, then hand a structured diff to the AI |
| **Financing & EMI Planner** | Month-by-month reducing-balance amortization schedules, No-Cost EMI eligibility check, and Razorpay IFSC validation |
| **Pincode Delivery Estimator** | Indian postal PIN validation with metro express vs regional delivery turnaround SLAs |
| **Cart-aware context** | Previous turns + cart contents are injected into every request so follow-ups work naturally |
| **Lamp login UI** | Interactive pull-cord desk-lamp animation; card reveals only when the cord is pulled |
| **Razorpay checkout** | Add to cart, review totals, and simulate Razorpay sandbox payments |

> **Cold-start notice:** The first request after the backend has been idle can take up to 60 s on the free Render tier. Please wait — do not refresh.

---

## 🏗️ Architecture

![ShopSense System Architecture](docs/architecture.png)

<details>
<summary>📐 View Interactive Mermaid Flowchart</summary>

```mermaid
flowchart TD
    shopper(["Shopper"])
    google_id(["Google Identity"])

    subgraph ShoppingInterface["Shopping interface"]
        app_shell["App shell<br/><code>[App.jsx]</code>"]
        chat_panel["Chat panel<br/><code>[ChatPanel.jsx]</code>"]
        auth_ui["Auth UI<br/><code>[AuthModal.jsx]</code>"]
        cart_drawer["Cart interface<br/><code>[CartDrawer.jsx]</code>"]
        product_card["Product cards<br/><code>[ProductCard.jsx]</code>"]
        api_client["API client<br/><code>[api.js]</code>"]
    end

    razorpay(["Razorpay sandbox"])

    subgraph ApiIdentity["API and identity"]
        rest_routes["REST routes<br/><code>[routes.py]</code>"]
        token_security["Token security<br/><code>[security.py]</code>"]
    end

    subgraph ShoppingIntelligence["Shopping intelligence"]
        ai_orch["AI orchestrator<br/><code>[ai.py]</code>"]
        scraper["Link inspection<br/><code>[scraper.py]</code>"]
        finance["Finance planner<br/><code>[finance.py]</code>"]
        logistics["Delivery estimator<br/><code>[logistics.py]</code>"]
        vision["Visual inspection<br/><code>[vision.py]</code>"]
        catalog_ranking["Catalog ranking<br/><code>[search.py]</code>"]
        live_search["Live retailer search<br/><code>[live_search.py]</code>"]
        agent_graph["Agent graph<br/><code>[graph.py]</code>"]
    end

    subgraph CatalogState["Catalog and state"]
        cart_state["Browser cart state<br/><code>[useCart.js]</code>"]
        catalog_svc["Catalog service<br/><code>[catalog.py]</code>"]
        db_models["Product and user models<br/><code>[entities.py]</code>"]
        db_session["Database sessions<br/><code>[session.py]</code>"]
    end

    relational_db[("Relational database")]
    ai_providers(["AI providers"])
    retailer_sources(["Retailer search sources"])

    %% User & Auth flows
    shopper -->|uses| app_shell
    google_id -->|supplies identity| app_shell
    app_shell -->|renders| chat_panel
    app_shell -->|opens| auth_ui
    auth_ui -->|authenticates| api_client
    chat_panel -->|submits chat| product_card
    chat_panel -.-> api_client
    product_card -->|adds products| cart_drawer
    product_card -.->|optional checkout| razorpay
    cart_drawer -->|updates| cart_state
    api_client -->|REST requests| rest_routes

    %% Backend Routing
    rest_routes -->|verifies tokens| token_security
    rest_routes -->|searches products| catalog_svc
    rest_routes -->|reads and writes| db_session
    rest_routes -->|dispatches chat| ai_orch
    rest_routes -->|inspects links| scraper
    rest_routes -->|provides planning| finance
    rest_routes -->|estimates delivery| logistics
    rest_routes -->|handles images| vision

    %% Intelligence & Agents
    ai_orch -->|grounds results| catalog_ranking
    ai_orch -->|searches retailers| live_search
    ai_orch -->|optional graph| agent_graph
    ai_orch -->|requests generation| ai_providers
    catalog_ranking -->|reads catalog| db_session
    live_search -->|queries prices| retailer_sources

    %% Data layer
    catalog_svc -->|queries through| db_session
    db_models -->|maps records| relational_db
    db_session -->|connects| relational_db
```

</details>

---

## 🚀 Quick Start (Local)

### Prerequisites
- Docker & Docker Compose **or** Python 3.12 + Node 20 + Postgres 15
- A `GEMINI_API_KEY` (free at [Google AI Studio](https://aistudio.google.com)) **or** `OPENAI_API_KEY`

### With Docker Compose

```bash
git clone https://github.com/Sahiljain6/Shopsense.git
cd Shopsense

# 1. Copy and fill in secrets
cp backend/.env.example backend/.env
#    → Paste your GEMINI_API_KEY (and optionally OPENAI_API_KEY)

# 2. Build and run
docker-compose up --build

# 3. Open the app
open http://localhost:3000
```

### Without Docker

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # edit with your API keys
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev    # → http://localhost:5173
```

---

## ⚙️ Environment Variables

| Variable | Required | Default | Notes |
|---|---|---|---|
| `GEMINI_API_KEY` | ✅ recommended | — | Primary AI provider |
| `OPENAI_API_KEY` | optional | — | Fallback AI provider |
| `GROQ_API_KEY` | optional | — | Fast Llama-3 fallback |
| `DATABASE_URL` | ✅ | SQLite (dev) | `postgresql+psycopg://...` in prod |
| `JWT_SECRET` | ✅ | *(insecure default)* | Change before deploying |
| `CORS_ORIGINS` | ✅ | `http://localhost:3000` | Comma-separated allowed origins |
| `ENABLE_MULTI_AGENT` | optional | `false` | Set `true` to enable LangGraph pipeline |
| `RAZORPAY_KEY_ID` | optional | — | For Razorpay checkout |
| `RAZORPAY_KEY_SECRET` | optional | — | For Razorpay checkout |

---

## 🧪 Running Tests

```bash
cd backend
python -m pytest -v
# Expected: 31 passed
```

The test suite covers: catalog search regression, multi-agent fallback, history-aware Gemini calls, CORS restrictions, rate limiting, Alembic migration idempotency, and orphaned-revision self-healing.

---

## 📂 Project Structure

```
Shopsense/
├── backend/
│   ├── alembic/                 # Database migrations
│   ├── app/
│   │   ├── api/routes.py        # FastAPI routes (/auth, /chat, /cart, /wishlist)
│   │   ├── core/config.py       # Pydantic Settings
│   │   ├── db/session.py        # SQLAlchemy engine + session
│   │   ├── models/entities.py   # ORM models (User, Product, Review, …)
│   │   ├── services/
│   │   │   ├── ai.py            # AIOrchestrator — main inference + tool calling
│   │   │   ├── search.py        # Catalog search (SQL, vector-like ranking)
│   │   │   ├── live_search.py   # DuckDuckGo / Serper grounding
│   │   │   └── agents/          # LangGraph nodes + graph definition
│   │   └── main.py              # FastAPI app, CORS, rate limiting, startup seed
│   ├── tests/                   # 31 pytest tests
│   ├── entrypoint.sh            # Container start (alembic upgrade → uvicorn)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── AuthCard.jsx     # Lamp login page with pull-cord toggle
│   │   │   ├── ChatPanel.jsx    # Chat UI + retry logic for cold starts
│   │   │   ├── Hero.jsx         # Navbar + cart drawer
│   │   │   ├── Logo.jsx         # ShopSense brand mark component
│   │   │   └── ProductCard.jsx  # Expandable product card with Razorpay
│   │   ├── api.js               # API client with cold-start retry
│   │   └── index.css            # Dark-mode design system
│   └── index.html
├── docker/
│   └── backend.Dockerfile
├── docs/
│   └── screenshots/             # Drop real app screenshots here
├── render.yaml                  # Render deployment config
└── docker-compose.yml
```

---

## 🖼️ Screenshots

> Screenshots are in [`docs/screenshots/`](docs/screenshots/) — see [`SCREENSHOTS.md`](docs/screenshots/SCREENSHOTS.md) for the expected file names.

---

## 🛠️ Key Engineering Decisions

- **Single search pipeline**: All `/chat` requests flow through one ranked SQL catalog search with budget + category filters. There is no second "raw" pipeline that could return unrelated products.
- **Alembic self-healing**: `env.py` detects orphaned revision IDs in the `alembic_version` table and resets to the last known-good baseline before running `upgrade head`, preventing crash loops on stale deployments.
- **Conversation history in Gemini**: The Gemini provider path explicitly builds a `contents[]` array from `history` before appending the current turn, matching the OpenAI/HF paths.
- **Seed versioning**: `SEED_VERSION` integer in `main.py`; Postgres is only re-seeded when the deployed version exceeds the stored version, preventing silent data overwrites on restart.
- **Cold-start UX**: Frontend detects a failed first attempt and shows *"Waking up the server…"* before retrying — no hard error surfaced for a single timeout.

---

## 🤝 Contributing

Issues and PRs are welcome. For larger changes, please open an issue first.

---

## 📄 License

MIT © 2026 Sahil Jain
