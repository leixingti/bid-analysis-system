from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # App
    APP_NAME: str = "招投标串标围标分析系统"
    APP_VERSION: str = "2.3.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./bid_analysis.db"
    DATABASE_PRIVATE_URL: str = ""

    # Security
    SECRET_KEY: str = "change-me-in-production-use-a-strong-random-key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    ALGORITHM: str = "HS256"

    # Analysis thresholds (defaults, can be overridden per-project)
    SIMILARITY_THRESHOLD: float = 0.20
    TIMESTAMP_DIFF_MINUTES: int = 5
    SENTENCE_SIMILARITY_THRESHOLD: float = 0.4

    # File storage
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 100

    # S3/R2 object storage (optional)
    S3_ENDPOINT: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET: str = "bid-documents"
    S3_REGION: str = "auto"

    model_config = {"env_file": ".env", "extra": "allow"}

    def get_async_database_url(self) -> str:
        url = self.DATABASE_PRIVATE_URL or self.DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url

    @property
    def use_s3(self) -> bool:
        return bool(self.S3_ENDPOINT and self.S3_ACCESS_KEY)


settings = Settings()
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
