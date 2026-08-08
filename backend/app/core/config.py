from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = ""
    database_url: str = "sqlite:///./shopsense.db"
    jwt_secret: str = "change-me-to-something-long-and-random"
    pinecone_api_key: str = ""
    enable_multi_agent: bool = False
    environment: str = "development"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 24

    model_config = SettingsConfigDict(env_file="backend/.env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
