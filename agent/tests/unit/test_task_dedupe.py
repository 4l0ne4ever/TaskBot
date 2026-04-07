import uuid
from datetime import UTC, datetime

from app.services.task_dedupe import pick_task_to_reuse, title_similarity


class _FakeTask:
    def __init__(self, tid: uuid.UUID, title: str, updated_at: datetime | None = None):
        self.id = tid
        self.title = title
        self.updated_at = updated_at


def test_title_similarity_case_insensitive() -> None:
    assert title_similarity("Hello Task", "hello task") == 1.0


def test_pick_task_prefers_better_title_match() -> None:
    a = _FakeTask(uuid.uuid4(), "Submit Q1 report", datetime(2026, 1, 1, tzinfo=UTC))
    b = _FakeTask(uuid.uuid4(), "Totally different", datetime(2026, 2, 1, tzinfo=UTC))
    chosen = pick_task_to_reuse([a, b], "Submit Q1 report", excluded_ids=set())
    assert chosen is a


def test_pick_task_respects_excluded_ids() -> None:
    a = _FakeTask(uuid.uuid4(), "Same title", None)
    chosen = pick_task_to_reuse([a], "Same title", excluded_ids={a.id})
    assert chosen is None


def test_pick_task_tie_breaker_newer_updated_at() -> None:
    older = _FakeTask(uuid.uuid4(), "Report", datetime(2026, 1, 1, tzinfo=UTC))
    newer = _FakeTask(uuid.uuid4(), "Report", datetime(2026, 3, 1, tzinfo=UTC))
    chosen = pick_task_to_reuse([older, newer], "Report", excluded_ids=set())
    assert chosen is newer
