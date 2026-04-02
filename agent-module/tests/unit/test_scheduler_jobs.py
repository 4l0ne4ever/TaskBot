import pytest

from app.scheduler.jobs import sync_all_users_drive, sync_all_users_gmail


@pytest.mark.asyncio
async def test_sync_all_users_gmail_calls_sync_for_each_user(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    async def _users():
        return [{"id": "u1", "access_token": "t1"}, {"id": "u2", "access_token": "t2"}]

    async def _run(**kwargs):
        calls.append(kwargs)
        return []

    monkeypatch.setattr("app.scheduler.jobs.fetch_sync_enabled_users", _users)
    monkeypatch.setattr("app.scheduler.jobs.run_gmail_sync_for_user", _run)
    await sync_all_users_gmail()
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_sync_all_users_drive_skips_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    async def _users():
        return [{"id": "u1"}, {"id": "u2", "access_token": "t2"}]

    async def _run(**kwargs):
        calls.append(kwargs)
        return []

    monkeypatch.setattr("app.scheduler.jobs.fetch_sync_enabled_users", _users)
    monkeypatch.setattr("app.scheduler.jobs.run_drive_sync_for_user", _run)
    await sync_all_users_drive()
    assert calls == [{"user_id": "u2", "access_token": "t2"}]
