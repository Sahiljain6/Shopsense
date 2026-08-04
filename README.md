# ShopSense – AI Powered Conversational Shopping Assistant

Production-ready monorepo for a conversational shopping assistant with a Next.js frontend, FastAPI backend, PostgreSQL, Redis, Pinecone-ready RAG services, Docker Compose, CI/CD, and observability.

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001

## Architecture

Client Layer → API Gateway → Orchestration Service → LLM Provider (OpenAI GPT-5.5 or Gemini) → Data & Retrieval Layer → Observability + CI/CD.

See `docs/architecture.md`, `docs/api.md`, `docs/installation.md`, `docs/deployment.md`, and `docs/developer-guide.md`.
