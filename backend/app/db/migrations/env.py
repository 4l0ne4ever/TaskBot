from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from app.db.base import Base
from app.models import Conflict, PipelineRun, SourceDocument, SyncState, Task, User

# Same repo-root `.env` as `app.config.Settings` (Alembic does not import Settings — avoid requiring every secret for migrations).
_REPO_ROOT = Path(__file__).resolve().parents[4]
# In Docker, keep compose-provided env vars (DATABASE_URL points to postgres service).
# On host runs, allow repo `.env` to override stale shell exports.
_running_in_docker = Path("/.dockerenv").exists()
load_dotenv(_REPO_ROOT / ".env", override=not _running_in_docker)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    raw = os.getenv(
        "DATABASE_URL",
        config.get_main_option("sqlalchemy.url"),
    )
    # Alembic runs a synchronous engine; asyncpg URLs need a sync driver for migrations.
    if raw.startswith("postgresql+asyncpg://"):
        return "postgresql+psycopg2://" + raw.removeprefix("postgresql+asyncpg://")
    return raw


def run_migrations_offline() -> None:
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section) or {}
    cfg["sqlalchemy.url"] = _get_url()

    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
