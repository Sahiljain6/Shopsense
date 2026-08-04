from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite+pysqlite:///./shopsense.db"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "dev-secret"
    jwt_algorithm: str = "HS256"
    openai_api_key: str = ""
    openai_model: str = "gpt-5.5"
    embedding_model: str = "text-embedding-3-small"
    gemini_api_key: str = ""
    pinecone_api_key: str = ""
    pinecone_index: str = "shopsense-products"
    cors_origins: str = "http://localhost:3000"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
