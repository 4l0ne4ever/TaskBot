from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT_ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    database_url: str
    redis_url_override: str | None = Field(
        default=None,
        validation_alias=AliasChoices("REDIS_URL"),
    )
    redis_host: str = Field(default="127.0.0.1", validation_alias=AliasChoices("REDIS_HOST"))
    redis_port: int = Field(
        default=6379,
        validation_alias=AliasChoices("REDIS_PUBLISH_PORT", "REDIS_PORT"),
    )
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
    frontend_url: str = "http://localhost:3000"
    internal_observability_token: str | None = None
    task_v2_read_enabled: bool = True

    @computed_field  # type: ignore[prop-decorator]
    @property
    def redis_url(self) -> str:
        o = (self.redis_url_override or "").strip()
        if o:
            return o
        host = (self.redis_host or "127.0.0.1").strip()
        return f"redis://{host}:{int(self.redis_port)}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
