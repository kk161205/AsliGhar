from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    serpapi_key: str = ""
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    public_base_url: str = "http://localhost:8000"
    image_ttl_minutes: int = 15
    scan_cache_ttl_seconds: int = 600
    database_url: str = "sqlite+aiosqlite:///./aslighar.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
