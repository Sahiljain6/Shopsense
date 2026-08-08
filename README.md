# ShopSense

**Live demo:** <https://shopsense.vercel.app>

First request may take up to 50 seconds if the backend has been idle (free-tier hosting) — please wait for the response rather than refreshing.

ShopSense is a full-stack AI shopping assistant with a FastAPI backend, Next.js frontend, grounded catalog recommendations, prompt modifiers, JWT auth, guardrails, and an optional LangGraph multi-agent pipeline.

Authentication is required to use chat: open the live demo, choose **Register** to create an account, or log in with an existing email and password before sending prompts.

## Setup

1. Copy `backend/.env.example` to `backend/.env` and paste a real `OPENAI_API_KEY`.
2. Run `docker-compose up --build`.
3. Seed demo products with `docker-compose exec backend python scripts/seed.py`.
4. Open <http://localhost:3000/chat>.

Try: `recommend a budget phone under 15000`, then `compare it with a Samsung under 20000`.

Set `ENABLE_MULTI_AGENT=true` in `backend/.env` and restart to test the LangGraph path. It falls back to the single-call path on graph errors.
