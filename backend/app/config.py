"""
SecureStego — Application Configuration

Settings loaded from environment variables / .env file via pydantic-settings.
All secrets (JWT key, DB credentials, etc.) must come from env — never hardcoded.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings — all configurable via environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "SecureStego"
    debug: bool = False

    # --- Database (Postgres) ---
    # For local dev/testing, defaults to SQLite. In production/docker, set to Postgres URL.
    database_url: str = "sqlite+aiosqlite:///./securestego.db"
    # Synchronous URL variant for Alembic migrations
    database_url_sync: str = "sqlite:///./securestego.db"

    @field_validator("database_url", mode="before")
    @classmethod
    def fix_postgres_url(cls, v: str) -> str:
        """Render injects DATABASE_URL as 'postgresql://...' but asyncpg
        requires 'postgresql+asyncpg://...'. Auto-convert so no manual
        editing is needed after Render deployment."""
        if isinstance(v, str) and v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    # --- JWT ---
    jwt_secret_key: str = "CHANGE-ME-IN-PRODUCTION-use-a-real-secret"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # --- Redis (rate limiting) ---
    redis_url: str = "redis://localhost:6379/0"
    # Set to False to disable Redis-based rate limiting (for testing without Redis)
    rate_limit_enabled: bool = False

    # --- Rate limit thresholds ---
    rate_limit_encode_per_minute: int = 20
    rate_limit_decode_per_minute: int = 5

    # --- Storage ---
    # Phase 2: local filesystem. Phase 3: S3/MinIO.
    storage_backend: str = "local"  # "local" | "s3"
    storage_local_dir: str = "./storage"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_name: str = "securestego"

    # --- MongoDB (audit trail) ---
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db_name: str = "securestego_audit"
    mongo_enabled: bool = False  # Disabled until Phase 3

    # --- Server-side private key encryption ---
    # Master key for encrypting user private keys at rest (Rule 5.5).
    # In production, this should be a strong random key from env/secrets manager.
    # Trade-off documented: server holds this key, so it's not zero-knowledge.
    # The more secure alternative (client-side key management) is noted in code.
    private_key_master_secret: str = "CHANGE-ME-server-side-master-key"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — reads .env once."""
    return Settings()
