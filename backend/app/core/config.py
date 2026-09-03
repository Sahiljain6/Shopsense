import secrets
from functools import lru_cache
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    ollama_api_key: str = ""
    ollama_model: str = "llama3.1:8b"

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    hf_token: str = ""
    huggingface_api_key: str = ""

    scraperapi_key: str = ""
    google_vision_api_key: str = ""
    google_client_id: str = ""

    database_url: str = "sqlite:///./shopsense.db"

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
            self.jwt_secret = "shopsense-development-jwt-secret-key-2026-fixed"
        return self

    model_config = SettingsConfigDict(
        env_file="backend/.env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
