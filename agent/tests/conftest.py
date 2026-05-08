from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://taskbot:taskbot@localhost:5432/taskbot")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")

from app.config import Settings  # noqa: E402

os.environ.setdefault("GROQ_MODEL", str(Settings.model_fields["groq_model"].default))
# Keep unit tests on the Groq path unless explicitly opting into Gemini (real API calls).
if os.environ.get("PYTEST_ALLOW_GEMINI", "").strip().lower() not in {"1", "true", "yes"}:
    os.environ["GEMINI_API_KEY"] = ""
    os.environ.pop("GOOGLE_API_KEY", None)
os.environ.setdefault("GMAIL_MCP_URL", "https://gmail-mcp.local/mcp")
os.environ.setdefault("DRIVE_MCP_URL", "https://drive-mcp.local/mcp")
os.environ.setdefault("CALENDAR_MCP_URL", "https://calendar-mcp.local/mcp")
os.environ.setdefault("BACKEND_API_BASE_URL", "http://127.0.0.1:8000")

# Observability isolation (forensic finding 2026-04-18):
# Prior to this guard, unit tests that exercised call_llm() fired
# ``record_llm_call`` which posted synthetic runs (``inputs.model ==
# "primary-model"``) to the production LangSmith project and pushed rows
# into the production Redis list. That polluted dashboards and burned
# LangSmith rate budget. Tests opt in via PYTEST_ENABLE_OBSERVABILITY=1
# when they specifically need to validate observability wiring.
if os.environ.get("PYTEST_ENABLE_OBSERVABILITY", "").strip().lower() not in {"1", "true", "yes"}:
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGSMITH_API_KEY"] = ""


def pytest_runtest_setup():
    from app.config import get_settings

    get_settings.cache_clear()


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_observability_redis(monkeypatch):
    """Replace the Redis client used by observability with an in-memory
    no-op so unit tests never reach a real Redis or add latency waiting
    on a connect timeout. Explicitly opting in via
    ``PYTEST_ENABLE_OBSERVABILITY`` re-enables the real client."""
    if os.environ.get("PYTEST_ENABLE_OBSERVABILITY", "").strip().lower() in {"1", "true", "yes"}:
        yield
        return

    class _NoopRedis:
        def lpush(self, *args, **kwargs):
            return 0

        def ltrim(self, *args, **kwargs):
            return True

        def lrange(self, *args, **kwargs):
            return []

        def llen(self, *args, **kwargs):
            return 0

    from app.services import observability as _obs

    monkeypatch.setattr(_obs, "_redis_client", lambda: _NoopRedis())
    yield
