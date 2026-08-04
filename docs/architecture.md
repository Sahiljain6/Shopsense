# Architecture Guide

ShopSense follows the required layered architecture: Client Layer, API Gateway, Orchestration Service, LLM Provider, Data & Retrieval Layer, and Observability + CI/CD. The backend isolates configuration, security, models, schemas, API routes, and AI/catalog services. The assistant never invents products; all recommendations are sourced from the product database and retrieved catalog context.
