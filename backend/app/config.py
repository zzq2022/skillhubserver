"""Application configuration via Pydantic Settings.

Reads from environment variables and optional `.env` file.
See design.md section 7 and `.env.example` for the full variable list.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Prefer CWD .env, then backend/.env, then repo-root .env (when started from backend/).
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _BACKEND_DIR.parent
_ENV_FILES = (
    Path(".env"),
    _BACKEND_DIR / ".env",
    _REPO_ROOT / ".env",
)


class Settings(BaseSettings):
    """Runtime configuration for skillhubserver."""

    # ---- Server ----
    HOST: str = "0.0.0.0"
    PORT: int = 3000

    # ---- Database ----
    DATABASE_TYPE: Literal["sqlite", "postgresql"] = "sqlite"
    DATABASE_URL: str = "sqlite:///./data/db/skillhubserver.db"

    # ---- Data root (skills workspace, media, sqlite file) ----
    DATA_ROOT: str = "./data"

    # ---- Session ----
    SESSION_MAX_AGE: int = 604_800  # 7 days (seconds)
    SESSION_IDLE_TIMEOUT: int = 1_800  # 30 minutes (seconds)
    SESSION_COOKIE_NAME: str = "session_id"

    # ---- Secret (required in production; used for CSRF signing) ----
    SECRET_KEY: str = Field(min_length=1)

    # ---- Media ----
    MAX_UPLOAD_SIZE: int = 5_242_880  # 5 MB

    # ---- Logging ----
    LOG_LEVEL: str = "info"

    model_config = SettingsConfigDict(
        env_file=tuple(str(p) for p in _ENV_FILES),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    @field_validator("DATABASE_TYPE", mode="before")
    @classmethod
    def normalize_database_type(cls, value: object) -> object:
        if isinstance(value, str):
            return value.lower().strip()
        return value

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        if isinstance(value, str):
            return value.lower().strip()
        return value

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_TYPE == "sqlite"

    @property
    def is_postgresql(self) -> bool:
        return self.DATABASE_TYPE == "postgresql"


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance (reads env once per process)."""
    return Settings()  # type: ignore[call-arg]


def clear_settings_cache() -> None:
    """Drop the cached Settings (useful in tests that mutate env)."""
    get_settings.cache_clear()
