"""Application configuration management."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str
    DATABASE_URL_YOYO: Optional[str] = None
    DATABASE_URL_APP: Optional[str] = None

    # JWT Configuration
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # DigitalOcean Spaces / MinIO
    SPACES_ENDPOINT: str
    SPACES_REGION: str
    SPACES_BUCKET: str
    SPACES_KEY: str
    SPACES_SECRET: str

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001"

    # Email/SMTP Configuration
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_TLS: bool = True
    FROM_EMAIL: str = "noreply@sdigdata.gov.gh"
    FROM_NAME: str = "SDIGdata"

    # Password Reset
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int = 24

    # Environment
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


settings = Settings()


def get_settings() -> Settings:
    return settings
