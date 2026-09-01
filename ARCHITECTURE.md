# ShopSense Architecture & Design Blueprint

## 1. System Overview
ShopSense is an AI-powered conversational e-commerce comparison shopping engine tailored for the Indian market. It features a Fastshot-inspired glassmorphic interface and a collaborative multi-agent backend orchestrator capable of real-time price intelligence, specification comparison, and financing breakdowns.

```mermaid
graph TD
    User([User Browser]) -->|HTTPS / WSS| Frontend[Vite + React 18 SPA]
    Frontend -->|Fastshot Composer| API[FastAPI Orchestrator]
    API --> Router[Agent Router & Classifier]
    Router --> SearchAgent[Catalog & Live Search]
    Router --> VisualAgent[Visual Inspector & Photo Matching]
    Router --> DealAgent[Deal Specialist & Price History]
    Router --> FinanceAgent[EMI & Bank Offers Calculator]
    Router --> LogisticsAgent[Pincode Delivery Estimator]
    SearchAgent --> DB[(PostgreSQL / SQLite)]
    DealAgent --> DB
```

## 2. Frontend Architecture
- **Framework**: React 18 + Vite SPA with modern hooks and pure component isolation.
- **Visual Design**: Fastshot cinematic styling with ambient background video, subtle backdrop blurs (`backdrop-filter: blur(16px)`), and radial glow lighting.
- **Component Decomposition**:
  - `HeaderBrandMark`: Brand icon and responsive title display.
  - `FeaturePillBadges`: Navigation highlight badges.
  - `ComposerInput`: Glassmorphic dock with model dropdown and action cluster.
  - `ModelDropdown`: Dynamic AI engine selector ("Sonnet 4.5", "Gemini Flash", "Deal Specialist").
  - `QuickActionsToolbar`: Predefined action chips (Deals, Compare, EMI, Pincode).
  - `WelcomePromptGrid`: Empty-state conversational prompts.
  - `ProductCard` & `ProductDetailModal`: Indian e-commerce benchmark pricing and buy links.
  - `CartDrawer`: Unified drawer with simulated Razorpay sandbox payment.
- **Modular Stylesheet Hierarchy (`frontend/src/styles/`)**:
  - `variables.css`: Design tokens, colors, borders, typography reset.
  - `ambient.css`: Cinematic stage, overlays, and video container.
  - `navbar.css`: Navigation bar, action pill badges, and user menu.
  - `composer.css`: Dock, chips, prompt input, engine dropdown, and send action.
  - `products.css`: Product cards, detail modals, and deal tags.
  - `cart.css`: Cart drawer, item rows, and checkout simulator.
  - `auth.css`: Split-view authentication, interactive pull-cord desk lamp.
  - `chat.css`: Messages stream, user/assistant bubbles, and typing dots.
  - `markdown.css`: Responsive comparison tables and code formatting.
  - `responsive.css`: Mobile breakpoints and viewport constraints.

## 3. Backend & Multi-Agent Orchestration
- **Runtime**: FastAPI with async route handlers and Pydantic v2 schemas.
- **Agent Roles**:
  - **Router Agent**: Analyzes user intent, checks for conversational queries, and dispatches to specialized tools.
  - **Visual Inspector Agent**: Uses Gemini multimodal capabilities to inspect photos, identify products, and detect spec discrepancies.
  - **Deal Specialist Agent**: Compares launch MRP vs current live price and analyzes promotional bank discounts.
  - **Finance Agent**: Computes reducing-balance EMI schedules, No-Cost EMI eligibility, and IFSC lookups.
  - **Logistics Agent**: Validates Indian PIN codes via Postal API with metro express turnaround estimates.

## 4. Quality & Testing Infrastructure
- **Frontend**: Node.js test runner (`node --test`) validating formatting utilities, API error mappings, and schema constants.
- **Backend**: Comprehensive Pytest suite covering authentication, injection defense, agent routing, and finance/logistics calculations (80+ passing tests).
