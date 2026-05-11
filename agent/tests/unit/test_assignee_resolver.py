"""Unit tests for the canonical-by-data assignee resolver (Q-05).

Covers the scoring function in isolation + the stateful ``AssigneeResolver``
against an in-memory fake Redis, plus the end-to-end wiring into
``normalize_tasks``. We intentionally never ship a dependency on
``fakeredis`` — the tests use a hand-rolled minimal stub that implements the
three set operations the resolver cares about, keeping the test suite runnable
on a vanilla Python install.
"""
from __future__ import annotations

from app.pipeline.nodes.normalize_tasks import normalize_tasks
from app.services import assignee_resolver as ar
from app.services.assignee_resolver import (
    CANONICAL_MATCH_THRESHOLD,
    AssigneeCanonical,
    AssigneeResolver,
    score_names,
)


class _FakeRedis:
    """Minimum stub for the ops ``resolver`` uses.

    Now covers pipeline(), hget(), hset() in addition to smembers/sadd/expire
    so that the F.2 exact-match hash and the pipeline-based learn() work in
    tests without a real Redis process.
    """

    def __init__(self) -> None:
        self.store: dict[str, set[str]] = {}
        self.hash_store: dict[str, dict[str, str]] = {}
        self.expiries: dict[str, int] = {}

    def smembers(self, key: str) -> set[str]:
        return set(self.store.get(key, set()))

    def sadd(self, key: str, *values: str) -> int:
        existing = self.store.setdefault(key, set())
        before = len(existing)
        for v in values:
            existing.add(v)
        return len(existing) - before

    def expire(self, key: str, ttl: int) -> bool:
        self.expiries[key] = ttl
        return True

    def hget(self, key: str, field: str) -> str | None:
        return self.hash_store.get(key, {}).get(field)

    def hset(self, key: str, field: str, value: str) -> int:
        h = self.hash_store.setdefault(key, {})
        is_new = field not in h
        h[field] = value
        return int(is_new)

    def pipeline(self) -> "_FakePipeline":
        return _FakePipeline(self)


class _FakePipeline:
    def __init__(self, r: _FakeRedis) -> None:
        self._r = r
        self._ops: list[tuple] = []

    def sadd(self, key: str, *values: str) -> "_FakePipeline":
        self._ops.append(("sadd", key, values))
        return self

    def expire(self, key: str, ttl: int) -> "_FakePipeline":
        self._ops.append(("expire", key, ttl))
        return self

    def hset(self, key: str, field: str, value: str) -> "_FakePipeline":
        self._ops.append(("hset", key, field, value))
        return self

    def execute(self) -> list:
        results = []
        for op in self._ops:
            if op[0] == "sadd":
                results.append(self._r.sadd(op[1], *op[2]))
            elif op[0] == "expire":
                results.append(self._r.expire(op[1], op[2]))
            elif op[0] == "hset":
                results.append(self._r.hset(op[1], op[2], op[3]))
        self._ops.clear()
        return results


# ---------------------------------------------------------------------------
# score_names
# ---------------------------------------------------------------------------


def test_exact_match_returns_one():
    assert score_names("Hương", "Hương") == 1.0
    assert score_names("HƯƠNG", "hương") == 1.0  # case fold


def test_token_subset_raw_has_extra_scores_above_threshold():
    """The core Q-05 case: the pool has the short canonical, raw has a
    prefix token. No honorific list is consulted; the match relies purely on
    token-set containment. The exact extra token is irrelevant to the
    algorithm (hence no keyword list)."""
    s = score_names("Bạn Hương", "Hương")
    assert s >= CANONICAL_MATCH_THRESHOLD
    # And it holds for an address the enumeration-based bridge would miss
    # (``Sếp``, ``Thầy`` etc. are NOT in the rubric prefix list) — this is the
    # whole point of moving to canonical-by-data.
    assert score_names("Sếp Hương", "Hương") >= CANONICAL_MATCH_THRESHOLD
    assert score_names("Thầy Nam", "Nam") >= CANONICAL_MATCH_THRESHOLD


def test_token_subset_canonical_has_extra_scores_above_threshold():
    """Symmetric to the previous case: pool has the long form, raw drops a
    token. Same semantics — extra tokens are evidenced as non-identifying by
    having the shorter form exist in the pool."""
    s = score_names("Hương", "Bạn Hương")
    assert s >= CANONICAL_MATCH_THRESHOLD


def test_disjoint_tokens_score_low():
    """Two names with no shared token should never collapse — that's how we
    avoid false merges in the pool."""
    assert score_names("Hương", "Tuấn") < CANONICAL_MATCH_THRESHOLD
    assert score_names("Anh Minh", "Chị Lan") < CANONICAL_MATCH_THRESHOLD


def test_diacritic_typo_recovered_via_secondary_score():
    """Typing ``Huong`` for ``Hương`` should be recovered — that's what the
    diacritic-folded secondary score is for. But only when the primary score
    would have failed (no token subset)."""
    s = score_names("Huong", "Hương")
    assert s >= CANONICAL_MATCH_THRESHOLD


def test_empty_strings_score_zero():
    assert score_names("", "Hương") == 0.0
    assert score_names("Hương", "") == 0.0


# ---------------------------------------------------------------------------
# AssigneeResolver
# ---------------------------------------------------------------------------


def _resolver_with(pool_entries: dict[str, list[str]] | None = None) -> tuple[AssigneeResolver, _FakeRedis]:
    fake = _FakeRedis()
    for user_id, names in (pool_entries or {}).items():
        fake.store[f"user:{user_id}:assignee_pool"] = set(names)
    return AssigneeResolver(redis_client=fake), fake


def test_resolver_returns_none_for_empty_input():
    resolver, _ = _resolver_with()
    assert resolver.resolve(None, user_id="u1") is None
    assert resolver.resolve("", user_id="u1") is None
    assert resolver.resolve("   ", user_id="u1") is None


def test_resolver_passthrough_when_pool_empty():
    """F.3 cold-start: when the pool is genuinely empty and Redis is reachable,
    the resolver emits ``source="cold_start"`` to signal first-time encounter.
    This is distinct from ``source="passthrough"`` (pool has entries but none
    matched), allowing save_tasks_service to prioritise learning."""
    resolver, _ = _resolver_with()
    result = resolver.resolve("Hương", user_id="u1")
    assert isinstance(result, AssigneeCanonical)
    assert result.canonical == "Hương"
    assert result.source == "cold_start"


def test_resolver_matches_pool_entry():
    resolver, _ = _resolver_with({"u1": ["Hương"]})
    result = resolver.resolve("Bạn Hương", user_id="u1")
    assert result is not None
    assert result.canonical == "Hương"
    assert result.source == "pool_match"
    assert result.similarity >= CANONICAL_MATCH_THRESHOLD


def test_resolver_prefers_best_match_when_multiple_candidates():
    """Pool has both ``Hương`` and ``Nam``; raw ``Hương`` must resolve to
    ``Hương`` — the higher-scoring candidate wins."""
    resolver, _ = _resolver_with({"u1": ["Hương", "Nam"]})
    result = resolver.resolve("Hương", user_id="u1")
    assert result is not None
    assert result.canonical == "Hương"
    assert result.source == "exact"


def test_resolver_no_match_returns_passthrough_when_names_disjoint():
    """Pool has ``Nam``, raw is ``Hương`` — must NOT collapse. Canonical =
    raw so dedupe stays truthful."""
    resolver, _ = _resolver_with({"u1": ["Nam"]})
    result = resolver.resolve("Hương", user_id="u1")
    assert result is not None
    assert result.canonical == "Hương"
    assert result.source == "passthrough"


def test_learn_persists_canonical_and_sets_ttl():
    resolver, fake = _resolver_with()
    added = resolver.learn("u1", "Hương")
    assert added is True
    assert "Hương" in fake.store["user:u1:assignee_pool"]
    assert fake.expiries["user:u1:assignee_pool"] > 0
    # Re-learning the same canonical is idempotent.
    assert resolver.learn("u1", "Hương") is False


def test_learn_rejects_bad_input():
    resolver, fake = _resolver_with()
    assert resolver.learn(None, "Hương") is False
    assert resolver.learn("u1", None) is False
    assert resolver.learn("u1", "   ") is False
    assert "user:u1:assignee_pool" not in fake.store


def test_learn_pool_isolated_per_user():
    resolver, fake = _resolver_with()
    resolver.learn("u1", "Hương")
    resolver.learn("u2", "Nam")
    # User 1 resolving "Nam" must NOT hit user 2's pool.
    result = resolver.resolve("Nam", user_id="u1")
    assert result is not None
    assert result.source == "passthrough"  # no match in u1 pool


def test_resolver_redis_failure_degrades_to_passthrough(monkeypatch):
    """If Redis is unreachable, the resolver must never raise — it returns
    passthrough so the pipeline keeps going. Production-grade graceful
    degradation is a stated contract."""

    class _BrokenRedis:
        def smembers(self, key):
            raise RuntimeError("simulated redis down")

        def sadd(self, key, *values):
            raise RuntimeError("simulated redis down")

        def expire(self, key, ttl):
            raise RuntimeError("simulated redis down")

    resolver = AssigneeResolver(redis_client=_BrokenRedis())
    result = resolver.resolve("Hương", user_id="u1")
    assert result is not None
    assert result.canonical == "Hương"
    assert result.source == "passthrough"
    assert resolver.learn("u1", "Hương") is False


def test_resolver_accepts_explicit_pool_without_redis():
    """Eval / offline mode: pool is injected directly, no Redis touch."""
    resolver = AssigneeResolver(redis_client=_FakeRedis())
    result = resolver.resolve("Bạn Hương", pool=["Hương", "Tuấn"])
    assert result is not None
    assert result.canonical == "Hương"
    assert result.source == "pool_match"


# ---------------------------------------------------------------------------
# normalize_tasks integration
# ---------------------------------------------------------------------------


def test_normalize_tasks_stamps_assignee_canonical_passthrough(monkeypatch):
    """When the pool is empty (or Redis not wired for the test), each task
    must carry ``assignee_canonical`` = raw + ``source="passthrough"``."""
    fake = _FakeRedis()
    resolver = AssigneeResolver(redis_client=fake)
    monkeypatch.setattr(ar, "_default_resolver", resolver)

    dv2 = {"type": "none", "text": "", "iso": None, "confidence": 0.0, "source": "llm", "is_ambiguous": False}
    state = {
        "user_id": "user-xyz",
        "extracted_tasks": [
            {"title": "Chuẩn bị báo cáo", "assignee": "Bạn Hương", "confidence": 0.9, "deadline_v2": dv2},
            {"title": "Gửi email", "assignee": None, "confidence": 0.8, "deadline_v2": dv2},
        ],
    }
    out = normalize_tasks(state)
    tasks = out["normalized_tasks"]
    assert len(tasks) == 2
    assert tasks[0]["assignee"] == "Bạn Hương"  # raw preserved for UI
    assert tasks[0]["assignee_canonical"] == "Bạn Hương"
    # F.3: pool is genuinely empty (Redis reachable, no prior learns) → cold_start
    assert tasks[0]["assignee_canonical_source"] == "cold_start"
    # Task with no assignee: None in both raw and canonical — we don't invent
    # a canonical just because the field is empty.
    assert tasks[1]["assignee"] is None
    assert tasks[1]["assignee_canonical"] is None
    assert tasks[1]["assignee_canonical_source"] is None


def test_normalize_tasks_uses_pool_to_collapse_honorific(monkeypatch):
    """End-to-end: user pool contains ``Hương``; a new extraction with
    ``Bạn Hương`` must come out with canonical ``Hương`` stamped. No honorific
    list was consulted — the data did the work."""
    fake = _FakeRedis()
    fake.store["user:user-xyz:assignee_pool"] = {"Hương"}
    resolver = AssigneeResolver(redis_client=fake)
    monkeypatch.setattr(ar, "_default_resolver", resolver)

    dv2 = {"type": "none", "text": "", "iso": None, "confidence": 0.0, "source": "llm", "is_ambiguous": False}
    state = {
        "user_id": "user-xyz",
        "extracted_tasks": [
            {"title": "Báo cáo", "assignee": "Bạn Hương", "confidence": 0.9, "deadline_v2": dv2},
        ],
    }
    out = normalize_tasks(state)
    t = out["normalized_tasks"][0]
    assert t["assignee"] == "Bạn Hương"
    assert t["assignee_canonical"] == "Hương"
    assert t["assignee_canonical_source"] == "pool_match"


def test_normalize_tasks_without_user_id_falls_back_to_empty_pool(monkeypatch):
    """Pipeline runs without a ``user_id`` (eval / ad-hoc) must still stamp
    canonical fields, even if the pool is empty — this is the production-vs-eval
    mode split described in the module docstring."""
    fake = _FakeRedis()
    # Populate a pool, but the resolver should NOT hit it because there's no
    # user_id on the state.
    fake.store["user:someone-else:assignee_pool"] = {"Hương"}
    resolver = AssigneeResolver(redis_client=fake)
    monkeypatch.setattr(ar, "_default_resolver", resolver)

    dv2 = {"type": "none", "text": "", "iso": None, "confidence": 0.0, "source": "llm", "is_ambiguous": False}
    state = {
        "user_id": None,
        "extracted_tasks": [
            {"title": "Báo cáo", "assignee": "Bạn Hương", "confidence": 0.9, "deadline_v2": dv2},
        ],
    }
    out = normalize_tasks(state)
    t = out["normalized_tasks"][0]
    assert t["assignee_canonical"] == "Bạn Hương"
    assert t["assignee_canonical_source"] == "passthrough"
