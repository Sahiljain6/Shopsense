# Developer Guide

Backend uses FastAPI, SQLAlchemy, Alembic, dependency injection, repository-style services, and Pydantic validation. Frontend uses Next.js 15, React 19, strict TypeScript, TailwindCSS, and reusable components. Keep prompts in `backend/app/services/prompts.py` rather than hardcoding them in route handlers.
