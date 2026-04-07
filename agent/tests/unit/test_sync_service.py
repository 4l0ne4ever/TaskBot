import pytest

from app.services.sync_service import run_drive_sync_for_user, run_gmail_sync_for_user


@pytest.mark.asyncio
async def test_run_gmail_sync_for_user_skip_when_lock_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _acquire(*args, **kwargs):
        return False

    monkeypatch.setattr("app.services.sync_service.acquire_sync_lock", _acquire)
    result = await run_gmail_sync_for_user(user_id="u1", access_token="t1")
    assert result == []


@pytest.mark.asyncio
async def test_run_drive_sync_for_user_releases_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"released": False}

    async def _acquire(*args, **kwargs):
        return True

    async def _release(*args, **kwargs):
        called["released"] = True

    async def _pull(*args, **kwargs):
        return [{"id": "f1"}]

    monkeypatch.setattr("app.services.sync_service.acquire_sync_lock", _acquire)
    monkeypatch.setattr("app.services.sync_service.release_sync_lock", _release)
    monkeypatch.setattr("app.services.sync_service.pull_recent_drive_files", _pull)
    result = await run_drive_sync_for_user(user_id="u1", access_token="t1")
    assert result == [{"id": "f1"}]
    assert called["released"] is True
