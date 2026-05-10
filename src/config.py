"""Centralized configuration for environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_file = Path(__file__).parent.parent / ".env"
load_dotenv(env_file)


class Config:
    """Application configuration from environment variables."""

    # JWT & Authentication
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_DAYS: int = 365

    # GitHub OAuth
    GITHUB_CLIENT_ID: str = os.getenv("GITHUB_CLIENT_ID", "")
    GITHUB_CLIENT_SECRET: str = os.getenv("GITHUB_CLIENT_SECRET", "")
    GITHUB_REDIRECT_URI: str = os.getenv(
        "GITHUB_REDIRECT_URI", "http://localhost:8000/auth/github/callback"
    )

    # API Settings
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    API_RELOAD: bool = os.getenv("API_RELOAD", "true").lower() == "true"

    # CORS
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:4200"
    ).split(",")

    @classmethod
    def validate(cls) -> None:
        """Validate required configuration."""
        if not cls.GITHUB_CLIENT_ID:
            raise ValueError("GITHUB_CLIENT_ID environment variable is not set")
        if not cls.GITHUB_CLIENT_SECRET:
            raise ValueError("GITHUB_CLIENT_SECRET environment variable is not set")

    @classmethod
    def is_production(cls) -> bool:
        """Check if running in production."""
        return os.getenv("ENVIRONMENT", "development").lower() == "production"


config = Config()
