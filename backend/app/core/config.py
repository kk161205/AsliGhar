from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    serpapi_key: str = ""
    groq_api_key: str = ""
    # Groq's model lineup isn't guaranteed stable — re-check against a live
    # models.list() call before relying on either name (the originally planned
    # llama-3.3-70b-versatile / llama-3.1-8b-instant pair 404'd entirely on
    # this account).
    groq_model: str = "openai/gpt-oss-120b"
    groq_fallback_model: str = "openai/gpt-oss-20b"
    public_base_url: str = "http://localhost:8000"
    image_ttl_minutes: int = 15
    scan_cache_ttl_seconds: int = 600
    # Rents for a locality don't move within a day, and re-asking gives a
    # noticeably different median each time — a long TTL keeps repeat scans of
    # the same place consistent (in-memory, so it resets on restart).
    price_cache_ttl_seconds: int = 60 * 60 * 24
    serpapi_lens_timeout_seconds: float = 12.0
    # Input reviewer: an LLM that turns messy address text into structured
    # fields for building search queries. Deliberately not the summarizer's
    # model, so their mistakes are less likely to coincide. If it's off, slow
    # or wrong the scan falls back to the plain city-level queries.
    supervisor_enabled: bool = True
    supervisor_model: str = "qwen/qwen3.8-27b"
    supervisor_timeout_seconds: float = 4.0
    # Neon (serverless Postgres). No default on purpose — a connection string
    # carries credentials, so it comes from .env only, same as the API keys
    # above. Expected form: postgresql+asyncpg://<user>:<password>@<host>/<db>?ssl=require
    database_url: str = ""
    # Signs session JWTs — a credential, no default, .env only (same reasoning
    # as database_url above). auth_deps.get_current_user fails closed (401)
    # if this is empty rather than falling back to a guessable value.
    jwt_secret: str = ""
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days
    # False in local dev (plain http). Set true in production, which serves
    # over https — a cookie marked Secure is never sent over plain http at
    # all, so this must track the actual deployment protocol.
    cookie_secure: bool = False
    # "lax" is right whenever the browser reaches the API through the same
    # origin as the frontend (Vite's /api proxy locally, a host-level rewrite
    # in production). Only if the browser calls the API cross-site directly
    # does this need "none" (and cookie_secure=true, since SameSite=None
    # requires Secure).
    cookie_samesite: str = "lax"
    # Comma-separated. The browser only ever reaches the API same-origin in
    # both dev (Vite's /api proxy) and prod (Vercel's rewrite to Render), so
    # this normally never matters — it's a fallback for anything that talks
    # to the API directly, e.g. a local variant (127.0.0.1 vs localhost) or a
    # future deployment topology that does need real cross-origin requests.
    cors_allowed_origins: str = "http://localhost:5173"

    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
