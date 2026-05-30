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
    encryption_key: str
    groq_api_key: str
    groq_model: str = "openai/gpt-oss-120b"
    groq_fallback_model: str = "llama-3.3-70b-versatile"
    cerebras_api_key: str | None = None
    cerebras_model: str = "gpt-oss-120b"
    cerebras_base_url: str = "https://api.cerebras.ai/v1"
    gemini_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    )
    gemini_model: str = "gemini-2.5-flash"
    gemini_http_timeout_seconds: float = 120.0
    # When set, caps google-genai HTTP retries (SDK default is up to 5 attempts on 408/429/5xx).
    # Unset = SDK default. Use 1 while diagnosing stable ~300s latency (avoids N × read timeout).
    gemini_http_retry_attempts: int | None = None
    # Queue-consumer worker: background Gemini ping after start (non-blocking) when API key is set.
    gemini_warmup_on_worker_start: bool = True
    # APScheduler: optional interval (minutes) for keepalive pings; unset = disabled.
    gemini_keepalive_interval_minutes: int | None = None
    # Gemini 2.5 Flash: 0 turns off thinking (lower latency); -1 = dynamic budget (API default when unset).
    gemini_thinking_budget: int = 0
    gmail_mcp_url: str
    drive_mcp_url: str
    calendar_mcp_url: str
    backend_api_base_url: str
    google_client_id: str
    google_client_secret: str
    pipeline_queue_name: str = "pipeline:jobs"
    sync_gmail_interval_minutes: int = 15
    sync_drive_interval_minutes: int = 30
    # Weekly Brief (Phase 8.3): cron schedule for the manager digest. Disabled
    # by default — set weekly_brief_enabled=true to turn on the scheduled send.
    # day_of_week/hour follow APScheduler cron semantics (mon=Monday, UTC).
    weekly_brief_enabled: bool = False
    weekly_brief_day_of_week: str = "mon"
    weekly_brief_hour: int = 7
    # Daily Digest (Round 9, 2026-05-30): end-of-day self-sent summary of the
    # day's task activity. Enabled by default per the locked-scope override.
    # 11 UTC = 18:00 ICT (the dogfood user's local timezone). Same self-send
    # model as the Weekly Brief — uses the user's own gmail.send scope.
    daily_digest_enabled: bool = True
    daily_digest_hour: int = 11
    langsmith_api_key: str | None = None
    langsmith_tracing: bool = True
    langsmith_project: str = "taskExtractor"
    langsmith_api_url: str = "https://api.smith.langchain.com"
    langsmith_ingest_timeout_seconds: float = 5.0
    langsmith_ingest_max_retries: int = 3
    langsmith_ingest_retry_backoff_base_seconds: float = 1.0
    groq_input_cost_per_million_tokens: float = 0.0
    groq_output_cost_per_million_tokens: float = 0.0
    max_tasks_per_document: int = 8
    extraction_max_retries: int = 3
    strict_work_max_gmail_messages_per_sync: int = 20
    strict_work_max_drive_files_per_sync: int = 20
    balanced_max_gmail_messages_per_sync: int = 30
    balanced_max_drive_files_per_sync: int = 30
    broad_max_gmail_messages_per_sync: int = 80
    broad_max_drive_files_per_sync: int = 60
    llm_per_document_cooldown_seconds: float = 0.6
    llm_pressure_window_size: int = 30
    llm_rate_limit_error_threshold: float = 0.25
    llm_pressure_max_documents_per_job: int = 2
    llm_pressure_requeue_delay_seconds: float = 45.0
    llm_pressure_requeue_max_retries: int = 3
    extract_merge_jaccard_threshold: float = 0.75
    task_reuse_similarity_threshold: float = 0.85
    conflict_title_similarity_threshold: float = 0.7
    # Phase 2.2 — multi-source (cross-platform) conflict detection thresholds.
    # Decoupled from the intra-batch threshold above because cross-document
    # false positives are more visible to the user (two unrelated docs would
    # be flagged together). Defaults can be overridden via policies.yaml.
    multi_source_title_similarity_threshold: float = 0.85
    multi_source_conflict_lookback_days: int = 30
    max_conflict_checks_per_task: int = 5
    confidence_abstain_threshold: float = 0.55
    confidence_uncertain_threshold: float = 0.76
    pipeline_policy_version: str = "v1"
    mcp_auth_revoke_streak_threshold: int = 3
    mcp_auth_revoke_disable_ttl_seconds: int = 24 * 3600
    calibration_artifact_path: str | None = None
    llm_extract_max_tokens: int = 1536
    llm_retry_truncate_chars: int = 16000
    llm_retry_truncate_factor: float = 0.7

    redis_observability_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("REDIS_OBSERVABILITY_ENABLED"),
    )
    redis_socket_connect_timeout_seconds: float = Field(
        default=2.0,
        validation_alias=AliasChoices("REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS"),
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def redis_url(self) -> str:
        """Effective Redis URL: ``REDIS_URL`` if set, else ``redis://{REDIS_HOST}:{REDIS_PUBLISH_PORT}``."""
        o = (self.redis_url_override or "").strip()
        if o:
            return o
        host = (self.redis_host or "127.0.0.1").strip()
        return f"redis://{host}:{int(self.redis_port)}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
