from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    serpapi_key: str = ""
    groq_api_key: str = ""
    # Groq's model lineup isn't guaranteed stable — re-check against a live
    # models.list() call before relying on either name (see docs/progress.md:
    # the originally planned llama-3.3-70b-versatile / llama-3.1-8b-instant
    # pair 404'd entirely on this account).
    groq_model: str = "openai/gpt-oss-120b"
    groq_fallback_model: str = "openai/gpt-oss-20b"
    public_base_url: str = "http://localhost:8000"
    image_ttl_minutes: int = 15
    scan_cache_ttl_seconds: int = 600
    serpapi_lens_timeout_seconds: float = 12.0
    # Neon (serverless Postgres). No default on purpose — a connection string
    # carries credentials, so it comes from .env only, same as the API keys
    # above. Expected form: postgresql+asyncpg://<user>:<password>@<host>/<db>?ssl=require
    database_url: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
