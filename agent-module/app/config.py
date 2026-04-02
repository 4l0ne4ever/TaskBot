from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT_ENV_FILE), env_file_encoding="utf-8")

    database_url: str
    redis_url: str
    gemini_api_key: str
    gmail_mcp_url: str
    drive_mcp_url: str
    backend_api_base_url: str
    sync_gmail_interval_minutes: int = 15
    sync_drive_interval_minutes: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
