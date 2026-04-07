from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://taskbot:taskbot@localhost:5432/taskbot")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("GROQ_MODEL", "llama-3.3-70b-versatile")
os.environ.setdefault("GMAIL_MCP_URL", "https://gmail-mcp.local/mcp")
os.environ.setdefault("DRIVE_MCP_URL", "https://drive-mcp.local/mcp")
os.environ.setdefault("CALENDAR_MCP_URL", "https://calendar-mcp.local/mcp")
os.environ.setdefault("BACKEND_API_BASE_URL", "http://127.0.0.1:8000")


def pytest_runtest_setup():
    from app.config import get_settings

    get_settings.cache_clear()
