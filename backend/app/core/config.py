from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    ollama_api_key: str = ""
    ollama_model: str = "llama3.1:8b"

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    scraperapi_key: str = ""
    google_vision_api_key: str = ""

    database_url: str = "sqlite:///./shopsense.db"

    jwt_secret: str = "change-me-to-something-long-and-random"
    pinecone_api_key: str = ""

    enable_multi_agent: bool = False
    environment: str = "development"

    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 24

    cors_origins: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "https://shopsense-gmeelq7ml-sahil-jain-s-projects.vercel.app"
    )

    cors_origin_regex: str = r"https://.*\.vercel\.app"

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            o.strip()
            for o in self.cors_origins.split(",")
            if o.strip()
        ]

    model_config = SettingsConfigDict(
        env_file="backend/.env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
