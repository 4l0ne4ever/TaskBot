import asyncio

from app.scheduler.jobs import start_scheduler


async def _run() -> None:
    start_scheduler()
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(_run())
