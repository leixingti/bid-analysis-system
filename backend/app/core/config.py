from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # App
    APP_NAME: str = "招投标串标围标分析系统"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False

    # Database — Railway auto-injects DATABASE_URL for PostgreSQL
    # Railway format: postgresql://user:pass@host:port/dbname
    # We need async driver: postgresql+asyncpg://...
    DATABASE_URL: str = "sqlite+aiosqlite:///./bid_analysis.db"
    DATABASE_PRIVATE_URL: str = ""  # Railway private networking URL

    # Security
    SECRET_KEY: str = "change-me-in-production-use-a-strong-random-key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"

    # Analysis thresholds
    SIMILARITY_THRESHOLD: float = 0.20
    TIMESTAMP_DIFF_MINUTES: int = 5

    # File storage
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 100

    model_config = {"env_file": ".env", "extra": "allow"}

    def get_async_database_url(self) -> str:
        """Convert DATABASE_URL to async-compatible format for Railway PostgreSQL."""
        # Prefer private URL for Railway internal networking
        url = self.DATABASE_PRIVATE_URL or self.DATABASE_URL

        # Railway provides: postgresql://user:pass@host:port/db
        # SQLAlchemy async needs: postgresql+asyncpg://user:pass@host:port/db
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url


settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
