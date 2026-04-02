from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT_ENV_FILE), env_file_encoding="utf-8")

    database_url: str
    redis_url: str
    jwt_secret: str
    encryption_key: str
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str
    aws_s3_bucket: str
    pipeline_queue_name: str = "pipeline:jobs"
    sync_gmail_interval_minutes: int = 15
    sync_drive_interval_minutes: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
