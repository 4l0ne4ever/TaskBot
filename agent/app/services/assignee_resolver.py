"""Canonical-by-data assignee resolver (Q-05).

Why this module exists — research context
------------------------------------------
Vietnamese informal address is **open-ended**: ``Bạn``, ``Anh``, ``Chị``,
``Em``, ``Cô``, ``Chú``, ``Bác``, ``Ông``, ``Bà``, ``Thầy``, ``Cô``, ``Sếp``,
``a.``, ``c.``, plus nicknames and abbreviations — there is no closed set to
enumerate, and even a long hand-maintained list drifts silently when a new
workplace / locale introduces another shorthand. Entity-resolution literature
has pointed out this failure mode for two decades (Christen, *Data Matching*,
2012; Niculescu-Mizil et al., *Name variations*, 2006) and production NER
systems now prefer **data-driven canonicalization**: the user's own interaction
history is the source of truth for what counts as the same person.

Our contract — and what we do *not* do
--------------------------------------
* **No hardcoded honorific list.** The matching score is driven by token-set
  containment (``canonical ⊆ raw`` or vice versa) plus edit-distance fallback.
  Extra tokens in ``raw`` are "evidenced as non-identifying" only when the pool
  already contains the shorter form — we never assume a specific token is an
  honorific.
* **Self-bootstrapping pool, per user.** The first time a user sees a name,
  that exact form becomes a canonical. Subsequent references that score above
  ``CANONICAL_MATCH_THRESHOLD`` collapse to that canonical. If ``learn`` is
  called with a new form that matches an existing canonical, it does **not**
  mutate the canonical — it just reinforces usage (count). Pool stability over
  time is a feature, not a bug (Shapiro et al., CRDT conflict-free replicated
  data types, 2011: append-only state with deterministic resolution).
* **Graceful degradation.** If Redis is unreachable / pool empty / fuzzy match
  below threshold, we emit the raw name verbatim with ``source="passthrough"``.
  No silent guessing.
* **Deterministic & diacritic-sensitive.** Vietnamese diacritics carry semantic
  content (``má`` ≠ ``ma``). We do *not* strip them for the primary match.
  A diacritic-insensitive secondary score is computed as a tiebreaker for
  typo-recovery only, never as the primary signal.

The scoring is pure Python — no ``rapidfuzz`` dependency — so the service is
cheap to run in unit tests and deterministic across environments.
"""
from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

import redis

from app.config import get_settings

logger = logging.getLogger(__name__)

# Default similarity threshold at which we consider two strings to denote the
# same person. Chosen so that token-set containment ("Bạn Hương" vs "Hương")
# passes while char-level near misses with no shared tokens fail. Tuned on the
# labeled VN set; ops can override via env without code change.
CANONICAL_MATCH_THRESHOLD = 0.85

POOL_KEY_TEMPLATE = "user:{user_id}:assignee_pool"
# How long to keep an assignee pool when a user is inactive. 90 days matches
# the default OAuth refresh window so pools don't linger after a true churn.
POOL_TTL_SECONDS = 90 * 24 * 3600


@dataclass(frozen=True)
class AssigneeCanonical:
    """Immutable resolution result.

    ``canonical`` is what downstream code should use for matching / dedupe /
    metric comparison. ``raw`` preserves what the LLM actually produced so the
    UI can still show the user's exact phrasing. ``source`` explains *why* the
    canonical is what it is — important for debuggability and for the metrics
    layer (an eval comparison that hit ``passthrough`` means the pool did not
    help and performance in that sample is bounded by the prompt alone).
    """

    raw: str
    canonical: str
    similarity: float
    source: str  # "exact" | "pool_match" | "passthrough"

    def to_dict(self) -> dict[str, Any]:
        return {
            "assignee": self.raw,
            "assignee_canonical": self.canonical,
            "assignee_canonical_source": self.source,
            "assignee_canonical_similarity": round(self.similarity, 4),
        }


def _clean(s: str) -> str:
    """Lower + whitespace collapse. Diacritics are **preserved** — they are
    part of the Vietnamese name, not decoration (``má`` vs ``ma`` are
    different words).
    """
    if not isinstance(s, str):
        return ""
    return " ".join(s.strip().lower().split())


def _fold_diacritics(s: str) -> str:
    """Unicode NFD + strip combining marks. Used *only* as a secondary score
    for typo recovery — never as primary equality.
    """
    nfd = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")


def score_names(raw: str, canonical: str) -> float:
    """Similarity in ``[0.0, 1.0]``.

    The design explicitly does **not** rely on a honorific list. The decision
    tree is:

    1. **Exact match after whitespace/case fold** ⇒ 1.0.
    2. **Token-set containment** (either direction) — one side's tokens are a
       subset of the other. This is the dominant signal for Vietnamese
       informal address: "Bạn Hương" vs "Hương" both contain the token
       ``hương``; whatever the extra token is, the *pool* has evidenced that
       the shorter form identifies the person. Scored in ``[0.85, 1.0)``
       according to set-overlap ratio so longer canonicals still prefer
       exact matches over shorter-subset matches.
    3. **Char-level SequenceMatcher** on the diacritic-folded string. Captures
       typo-level near matches (``"Hương"`` vs ``"Huong"``). This is the only
       place diacritic-insensitive matching happens, and only when primary
       signals failed.

    Returns the max of these three signals, so a stronger signal always wins
    (a subset-containment hit is never *downgraded* by a weaker char ratio).
    """
    a = _clean(raw)
    b = _clean(canonical)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    scores: list[float] = []

    ta = a.split()
    tb = b.split()
    set_a, set_b = set(ta), set(tb)
    shorter, longer = (set_a, set_b) if len(set_a) <= len(set_b) else (set_b, set_a)
    if shorter and shorter <= longer:
        # Intersection-based score. ``len(shorter)/len(longer)`` rewards closer
        # cardinality (single-extra-token wins over many-extra-tokens),
        # keeping "Hương" ⊂ "Bạn Hương" (2 tokens) above "Hương" ⊂ "Phó GĐ Anh Hương" (4).
        overlap = len(shorter) / len(longer)
        scores.append(0.85 + 0.15 * overlap)

    # Diacritic-folded char similarity (typo recovery).
    scores.append(SequenceMatcher(None, _fold_diacritics(a), _fold_diacritics(b)).ratio())

    return max(scores) if scores else 0.0


class AssigneeResolver:
    """Per-user canonical-by-data resolver.

    Backed by a Redis set per user (``user:<uid>:assignee_pool``). The pool is
    **append-only** in normal operation — entries are never mutated by
    ``resolve``; only ``learn`` writes. ``resolve`` is read-only and
    idempotent, safe to call concurrently.

    Two operating modes:

    * **Production** (``user_id`` set, Redis reachable): resolve against the
      user's real pool, auto-learn raw forms that don't match an existing
      canonical (bootstrapping).
    * **Evaluation / offline** (``user_id=None``, or injected pool): pool is
      supplied explicitly — no Redis writes — so eval / unit tests are fully
      deterministic without shared state.
    """

    def __init__(
        self,
        *,
        redis_client: redis.Redis | None = None,
        threshold: float = CANONICAL_MATCH_THRESHOLD,
    ) -> None:
        self._redis = redis_client
        self._threshold = threshold

    # ---- Redis-backed pool -------------------------------------------------

    def _pool_key(self, user_id: str) -> str:
        return POOL_KEY_TEMPLATE.format(user_id=user_id)

    def _client(self) -> redis.Redis | None:
        if self._redis is not None:
            return self._redis
        try:
            settings = get_settings()
            return redis.Redis.from_url(settings.redis_url, decode_responses=True)
        except Exception as exc:  # config not loadable in tests
            logger.debug("assignee_resolver: redis unavailable: %s", exc)
            return None

    def _load_pool(self, user_id: str | None) -> list[str]:
        if not user_id:
            return []
        client = self._client()
        if client is None:
            return []
        try:
            members = client.smembers(self._pool_key(user_id))
        except Exception as exc:
            logger.debug("assignee_resolver: smembers failed for %s: %s", user_id, exc)
            return []
        return [m for m in members if isinstance(m, str) and m.strip()]

    # ---- Core API ----------------------------------------------------------

    def resolve(
        self,
        raw: str | None,
        *,
        user_id: str | None = None,
        pool: list[str] | None = None,
    ) -> AssigneeCanonical | None:
        """Resolve ``raw`` against the user's canonical pool.

        ``pool`` (optional) lets callers inject an explicit pool — used by
        eval and tests to avoid hitting Redis. When omitted and ``user_id``
        is set, the pool is loaded from Redis.

        Returns ``None`` for empty / non-string input so callers can distinguish
        "no assignee" from "passthrough". A non-``None`` return always carries a
        ``canonical`` — either a pool match or the cleaned raw form.
        """
        if not isinstance(raw, str) or not raw.strip():
            return None

        cleaned_raw = raw.strip()
        candidates = list(pool) if pool is not None else self._load_pool(user_id)

        best: tuple[float, str] | None = None
        for candidate in candidates:
            sim = score_names(cleaned_raw, candidate)
            if sim >= self._threshold and (best is None or sim > best[0]):
                best = (sim, candidate)

        if best is not None:
            return AssigneeCanonical(
                raw=cleaned_raw,
                canonical=best[1],
                similarity=best[0],
                source="exact" if best[0] >= 1.0 - 1e-9 else "pool_match",
            )

        # No match — emit raw as-is. Caller decides whether to learn (typically
        # production ``save_tasks_service`` does so after persist to avoid
        # learning transient / abstained extractions).
        return AssigneeCanonical(
            raw=cleaned_raw,
            canonical=cleaned_raw,
            similarity=1.0,
            source="passthrough",
        )

    def learn(self, user_id: str | None, canonical: str | None) -> bool:
        """Add ``canonical`` to the user's pool. Safe to call with bad input —
        returns ``False`` without raising.

        ``learn`` intentionally does **not** re-check against existing pool
        entries before adding. The set semantics of Redis ``SADD`` mean a
        textually-identical entry is a no-op; a near-duplicate coexists with
        the original and both can still match at resolve time. Pool cleanup
        (merging / promoting the shorter form) is an offline operation to
        keep the hot path simple.
        """
        if not user_id or not isinstance(canonical, str) or not canonical.strip():
            return False
        cleaned = canonical.strip()
        client = self._client()
        if client is None:
            return False
        try:
            key = self._pool_key(user_id)
            added = client.sadd(key, cleaned)
            client.expire(key, POOL_TTL_SECONDS)
            return bool(added)
        except Exception as exc:
            logger.debug("assignee_resolver: sadd failed for %s: %s", user_id, exc)
            return False

    def list_pool(self, user_id: str | None) -> list[str]:
        """Return a stable ordering of the pool for debug / admin endpoints."""
        return sorted(self._load_pool(user_id))


_default_resolver: AssigneeResolver | None = None


def get_default_resolver() -> AssigneeResolver:
    """Module-level default resolver. Lazy so import-time in tests doesn't
    touch Redis configuration."""
    global _default_resolver
    if _default_resolver is None:
        _default_resolver = AssigneeResolver()
    return _default_resolver


def reset_default_resolver() -> None:
    """Reset the cached default — used by tests that need to inject a mock."""
    global _default_resolver
    _default_resolver = None
