import secrets
from functools import lru_cache
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"

    ollama_api_key: str = ""
    ollama_model: str = "llama3.1:8b"

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    hf_token: str = ""
    huggingface_api_key: str = ""

    scraperapi_key: str = ""
    serpapi_api_key: str = ""
    serpapi_location: str = "Mumbai, Maharashtra, India"
    google_vision_api_key: str = ""
    google_client_id: str = ""

    pincode_api_key: str = ""
    pincode_api_url: str = ""

    database_url: str = "sqlite:///./shopsense.db"
    db_pool_size: int = Field(default=5, ge=1, le=30)
    db_max_overflow: int = Field(default=10, ge=0, le=50)
    db_pool_timeout_seconds: int = Field(default=30, ge=1, le=120)
    db_pool_recycle_seconds: int = Field(default=1800, ge=60, le=86400)
    db_lock_timeout_ms: int = Field(default=5000, ge=100, le=120000)
    db_statement_timeout_ms: int = Field(default=30000, ge=1000, le=300000)

    # Live retailer search snapshots are process-local and deliberately bounded.
    live_search_cache_ttl_seconds: int = Field(default=900, ge=1, le=86400)
    live_search_cache_max_entries: int = Field(default=256, ge=16, le=5000)

    # Upstream AI attempts and their ordered model fallback chain have explicit budgets.
    ai_provider_timeout_seconds: int = Field(default=30, ge=5, le=120)
    ai_provider_chain_timeout_seconds: int = Field(default=75, ge=10, le=240)

    jwt_secret: str = ""
    pinecone_api_key: str = ""

    enable_multi_agent: bool = False
    environment: str = "development"

    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 24
    refresh_token_days: int = 7

    cors_origins: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "https://shopsense-theta.vercel.app,"
        "https://shopsense.vercel.app,"
        "https://shopsense-4444.vercel.app,"
        "https://shopsense-4444-git-main-sahil-jain-s-projects.vercel.app,"
        "https://shopsense-4444-m4xke85sl-sahil-jain-s-projects.vercel.app,"
        "https://shopsense-nv1k3jgjm-sahil-jain-s-projects.vercel.app,"
        "https://shopsense-gmeelq7ml-sahil-jain-s-projects.vercel.app"
    )

    cors_origin_regex: str = r"^https://shopsense.*\.vercel\.app$"

    @property
    def cors_origins_list(self) -> list[str]:
        # Never allow wildcard '*' with credentials
        return [
            o.strip()
            for o in self.cors_origins.split(",")
            if o.strip() and o.strip() != "*"
        ]

    @model_validator(mode="after")
    def validate_jwt_secret(self) -> "Settings":
        env = (self.environment or "").lower()
        dummy = "shopsense-hackathon-secure-secret-key-2026-production"
        if env == "production":
            if not self.jwt_secret or self.jwt_secret == dummy:
                raise RuntimeError("CRITICAL SECURITY ERROR: JWT_SECRET environment variable must be set in production.")
        elif not self.jwt_secret:
            self.jwt_secret = secrets.token_urlsafe(32)
        return self

    model_config = SettingsConfigDict(
        env_file="backend/.env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
