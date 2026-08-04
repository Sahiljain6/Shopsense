# Deployment Guide

Render deployment uses the Dockerfiles in `docker/`. Configure environment variables for PostgreSQL, Redis, JWT, OpenAI or Gemini, Pinecone, and Cloudinary. GitHub Actions runs lint, tests, builds, Docker builds, and can call a Render deploy hook.
