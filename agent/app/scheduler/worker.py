import asyncio
import logging

from app.config import get_settings
from app.scheduler.jobs import start_scheduler
from app.scheduler.queue_consumer import consume_pipeline_jobs

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# Silence the LangChain SDK's auto-tracing failure spam: when the LangSmith
# free-tier monthly quota is hit, the SDK retries forever and dumps a long
# multiline warning per LLM call. The retries don't block the pipeline, but
# the noise drowns out real errors and adds disk pressure. Errors still log
# at ERROR level if anything truly broken happens.
logging.getLogger("langsmith.client").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)
_settings = get_settings()


def _schedule_gemini_warmup_background() -> None:
    """Fire-and-forget TLS/session warmup so pipeline jobs after it share a hot HTTP connection."""
    if not _settings.gemini_warmup_on_worker_start:
        return
    key = _settings.gemini_api_key
    if not key or not str(key).strip():
        return

    async def _warm() -> None:
        from app.pipeline.llm import warmup_gemini_connection

        try:
            await asyncio.to_thread(warmup_gemini_connection)
        except Exception:
            logger.exception("gemini warmup task failed")

    asyncio.get_running_loop().create_task(_warm())


async def _run() -> None:
    start_scheduler()
    _schedule_gemini_warmup_background()
    await consume_pipeline_jobs()


if __name__ == "__main__":
    asyncio.run(_run())
