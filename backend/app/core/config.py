"""
Application configuration.

All configuration is loaded from environment variables (or a local .env file
during development). Nothing here is hard-coded for production use — see
.env.example at the repo root for the full list of variables.
"""

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "SmartCare AI"
    ENV: str = "development"
    DEBUG: bool = True

    # --- Database (MySQL) ---
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "smartcare_ai"
    DB_USER: str = "smartcare"
    DB_PASSWORD: str = "smartcare_dev_pw"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    # --- Auth / JWT ---
    JWT_SECRET_KEY: str = "CHANGE_ME_DEV_ONLY_INSECURE_SECRET"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # --- CORS ---
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000"],
        validation_alias="CORS_ALLOWED_ORIGINS",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_comma_separated(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # --- AI provider ---
    AI_PROVIDER: str = "nvidia"

    # Anthropic (kept for backwards compatibility)
    ANTHROPIC_API_KEY: str = ""

    # NVIDIA NIM / OpenAI-compatible API
    NVIDIA_API_KEY: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

    AI_MODEL: str = "z-ai/glm-5.3"

    # --- ML ---
    ML_MODEL_DIR: str = "app/ml/models"

    # --- Rate limiting ---
    RATE_LIMIT_PER_MINUTE: int = 60

    def validate_production_safety(self) -> None:
        """
        Fail fast rather than silently running insecurely in production.
        Called once at app startup (see app/main.py).
        """
        if self.ENV.lower() != "production":
            return

        errors = []

        if (
            self.JWT_SECRET_KEY == "CHANGE_ME_DEV_ONLY_INSECURE_SECRET"
            or len(self.JWT_SECRET_KEY) < 32
        ):
            errors.append(
                "JWT_SECRET_KEY must be set to a strong, unique secret (32+ chars) "
                "in production."
            )

        if self.DEBUG:
            errors.append("DEBUG must be false in production.")

        if any("localhost" in origin for origin in self.CORS_ORIGINS):
            errors.append(
                "CORS_ORIGINS still includes a localhost origin in production. "
                "Set it to your real frontend origin(s) via the "
                "CORS_ALLOWED_ORIGINS env var."
            )

        if errors:
            raise RuntimeError(
                "Insecure production configuration:\n- "
                + "\n- ".join(errors)
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()