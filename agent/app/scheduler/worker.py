import asyncio
import logging

from app.scheduler.jobs import start_scheduler
from app.scheduler.queue_consumer import consume_pipeline_jobs

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


async def _run() -> None:
    start_scheduler()
    await consume_pipeline_jobs()


if __name__ == "__main__":
    asyncio.run(_run())
