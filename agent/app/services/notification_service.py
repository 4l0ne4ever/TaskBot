import asyncio
import uuid
from datetime import date

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.mcp.calendar_client import CalendarMCPClient
from app.models.task import Task
from app.pipeline.state import PipelineState


def _parse_uuid_list(values: list[str] | None) -> list[uuid.UUID]:
    ids: list[uuid.UUID] = []
    for raw in values or []:
        try:
            ids.append(uuid.UUID(str(raw)))
        except ValueError:
            continue
    return ids


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def _to_iso_date(value: object) -> str | None:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return value[:10]
    return None


async def async_dispatch_notifications(state: PipelineState) -> dict:
    errors = list(state.get("errors", []))
    notifications_sent: list[dict] = []
    access_token = state.get("access_token")
    user_id = state.get("user_id")
    user_uuid = _parse_uuid(str(user_id)) if user_id else None
    saved_task_ids = _parse_uuid_list(state.get("saved_task_ids"))

    if not access_token:
        errors.append("dispatch_notifications: missing access_token")
        return {"notifications_sent": notifications_sent, "errors": errors}
    if not user_uuid or not saved_task_ids:
        return {"notifications_sent": notifications_sent, "errors": errors}

    calendar = CalendarMCPClient(access_token=access_token)
    calendar_blocked = False

    async with AsyncSessionLocal() as session:
        async with session.begin():
            stmt = select(Task).where(
                Task.user_id == user_uuid,
                Task.id.in_(saved_task_ids),
                Task.status == "confirmed",
            )
            result = await session.execute(stmt)
            tasks = list(result.scalars().all())

            for task in tasks:
                date_iso = _to_iso_date(task.deadline)
                if not date_iso:
                    notifications_sent.append({"task_id": str(task.id), "type": "in_app_reminder"})
                    continue
                if calendar_blocked:
                    notifications_sent.append({"task_id": str(task.id), "type": "calendar_skipped"})
                    continue
                # Round 13 (2026-05-31): pass deadline_time through so the
                # calendar client creates a *timed* event (1h duration in
                # ICT) instead of all-day when the source said a time.
                time_str = (
                    task.deadline_time.strftime("%H:%M:%S")
                    if getattr(task, "deadline_time", None) is not None
                    else None
                )
                # Phase 6.6 (2026-06-03): when recurrence_rule is set, the
                # event is created/updated as a Google Calendar recurring
                # series. recurrence_suggested (LLM-detected, awaiting user
                # confirm) is NOT dispatched — only the explicit recurrence_rule
                # drives the calendar so a dismissed suggestion never reaches
                # Google.
                recurrence_rule = getattr(task, "recurrence_rule", None) or None
                try:
                    if task.calendar_event_id:
                        update_resp = await calendar.update_event(
                            event_id=task.calendar_event_id,
                            title=task.title,
                            date_iso=date_iso,
                            description=f"Auto-synced task {task.id}",
                            time_str=time_str,
                            recurrence_rule=recurrence_rule,
                        )
                        event_id = str(update_resp.get("event_id") or task.calendar_event_id)
                    else:
                        create_resp = await calendar.create_event(
                            title=task.title,
                            date_iso=date_iso,
                            description=f"Task {task.id}",
                            time_str=time_str,
                            recurrence_rule=recurrence_rule,
                        )
                        event_id = str(create_resp.get("event_id") or "")
                    task.calendar_event_id = event_id or task.calendar_event_id
                    task.notification_sent = True
                    notifications_sent.append({"task_id": str(task.id), "type": "calendar", "event_id": event_id})
                except Exception as exc:  # keep pipeline alive
                    errors.append(f"dispatch_notifications failed for task {task.id}: {exc}")
                    if "403" in str(exc):
                        calendar_blocked = True

    return {"notifications_sent": notifications_sent, "errors": errors}


def dispatch_notifications_sync(state: PipelineState) -> dict:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(async_dispatch_notifications(state))

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, async_dispatch_notifications(state))
        return future.result()
