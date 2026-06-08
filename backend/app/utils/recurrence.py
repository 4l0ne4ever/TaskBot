"""RFC 5545 RRULE whitelist validator + helpers for recurring tasks.

Phase 6.6 (2026-06-03). The whitelist is intentionally narrow — we accept
the patterns the UI can express (4 presets + pattern builder) and reject
anything else so unsupported RRULE shapes cannot reach Google Calendar
dispatch and surprise the user.

Accepted properties
-------------------
FREQ        DAILY | WEEKLY | MONTHLY | YEARLY      (required)
INTERVAL    1..365                                  (optional, default 1)
BYDAY       MO|TU|WE|TH|FR|SA|SU (comma list)       (optional, weekly + monthly weekday)
            Numeric prefix allowed: ``2MO`` (second Monday), ``-1FR`` (last Friday).
BYMONTHDAY  1..31                                   (optional, monthly by date)
UNTIL       YYYYMMDDTHHMMSSZ (UTC, future)          (optional, end condition)
COUNT       1..520 (=~10y weekly)                   (optional, end condition)

Rejected
--------
- Combined COUNT + UNTIL (ambiguous)
- UNTIL in the past (no future occurrences)
- Any other RRULE property (BYHOUR, BYMINUTE, BYSETPOS, BYMONTH, WKST, ...)
- Malformed syntax (final structural check via ``dateutil.rrulestr``)

The agent uses this in ``normalize_tasks`` (to vet LLM-suggested rules
before persisting) and in ``dispatch_notifications`` (sanity check before
calling Google Calendar). The backend mirrors this module at
``backend/app/utils/recurrence.py`` and calls it from the Pydantic
``TaskUpdate`` schema.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from dateutil.rrule import rrulestr


ALLOWED_KEYS = frozenset({"FREQ", "INTERVAL", "BYDAY", "BYMONTHDAY", "UNTIL", "COUNT"})
ALLOWED_FREQ = frozenset({"DAILY", "WEEKLY", "MONTHLY", "YEARLY"})
ALLOWED_WEEKDAYS = frozenset({"MO", "TU", "WE", "TH", "FR", "SA", "SU"})

INTERVAL_MAX = 365
COUNT_MAX = 520


class RecurrenceError(ValueError):
    """Raised when an RRULE fails whitelist validation."""


def _parse_kv(rrule: str) -> dict[str, str]:
    """Parse ``FREQ=WEEKLY;BYDAY=MO,WE`` → ``{'FREQ': 'WEEKLY', ...}``.

    Strips a leading ``RRULE:`` prefix if present (RFC 5545 line form).
    """
    s = rrule.strip()
    if s.upper().startswith("RRULE:"):
        s = s.split(":", 1)[1]
    out: dict[str, str] = {}
    for chunk in s.split(";"):
        if not chunk:
            continue
        if "=" not in chunk:
            raise RecurrenceError(f"malformed RRULE segment: {chunk!r}")
        k, v = chunk.split("=", 1)
        k = k.strip().upper()
        v = v.strip()
        if not k or not v:
            raise RecurrenceError(f"empty key or value in RRULE: {chunk!r}")
        if k in out:
            raise RecurrenceError(f"duplicate RRULE key: {k}")
        out[k] = v
    return out


def _parse_until_utc(value: str) -> datetime:
    """Parse ``YYYYMMDDTHHMMSSZ`` (UTC RFC 5545) → tz-aware datetime."""
    if not value.endswith("Z"):
        raise RecurrenceError(f"UNTIL must end with 'Z' (UTC), got {value!r}")
    try:
        dt = datetime.strptime(value, "%Y%m%dT%H%M%SZ")
    except ValueError as exc:
        raise RecurrenceError(f"malformed UNTIL: {value!r}") from exc
    return dt.replace(tzinfo=timezone.utc)


def _validate_byday(value: str) -> None:
    for token in value.split(","):
        t = token.strip().upper()
        if not t:
            raise RecurrenceError(f"empty BYDAY token in {value!r}")
        prefix = ""
        i = 0
        while i < len(t) and (t[i].isdigit() or t[i] == "-"):
            prefix += t[i]
            i += 1
        day = t[i:]
        if day not in ALLOWED_WEEKDAYS:
            raise RecurrenceError(f"BYDAY weekday must be MO..SU, got {t!r}")
        if prefix:
            try:
                n = int(prefix)
            except ValueError as exc:
                raise RecurrenceError(f"BYDAY numeric prefix invalid: {prefix!r}") from exc
            if n == 0 or not (-53 <= n <= 53):
                raise RecurrenceError(f"BYDAY numeric prefix out of range: {n}")


def validate_rrule(rrule: str, *, now: datetime | None = None) -> str:
    """Validate an RRULE string against the whitelist.

    Returns a canonicalized form (uppercased keys, no leading ``RRULE:``,
    keys ordered FREQ, INTERVAL, BYDAY, BYMONTHDAY, UNTIL, COUNT).

    Raises ``RecurrenceError`` on any rejection.

    ``now`` is the reference time for "UNTIL in the past" checks. Defaults
    to ``datetime.now(timezone.utc)``. Injectable for deterministic tests.
    """
    if not isinstance(rrule, str) or not rrule.strip():
        raise RecurrenceError("RRULE must be a non-empty string")
    if now is None:
        now = datetime.now(timezone.utc)

    kv = _parse_kv(rrule)

    extra = set(kv) - ALLOWED_KEYS
    if extra:
        raise RecurrenceError(f"unsupported RRULE properties: {sorted(extra)}")

    if "FREQ" not in kv:
        raise RecurrenceError("FREQ is required")
    freq = kv["FREQ"].upper()
    if freq not in ALLOWED_FREQ:
        raise RecurrenceError(f"FREQ must be one of {sorted(ALLOWED_FREQ)}, got {freq!r}")
    kv["FREQ"] = freq

    if "INTERVAL" in kv:
        try:
            interval = int(kv["INTERVAL"])
        except ValueError as exc:
            raise RecurrenceError(f"INTERVAL must be int, got {kv['INTERVAL']!r}") from exc
        if not (1 <= interval <= INTERVAL_MAX):
            raise RecurrenceError(f"INTERVAL must be 1..{INTERVAL_MAX}, got {interval}")
        kv["INTERVAL"] = str(interval)

    if "BYDAY" in kv:
        _validate_byday(kv["BYDAY"])
        kv["BYDAY"] = kv["BYDAY"].upper()

    if "BYMONTHDAY" in kv:
        try:
            d = int(kv["BYMONTHDAY"])
        except ValueError as exc:
            raise RecurrenceError(f"BYMONTHDAY must be int, got {kv['BYMONTHDAY']!r}") from exc
        if not (1 <= d <= 31):
            raise RecurrenceError(f"BYMONTHDAY must be 1..31, got {d}")
        kv["BYMONTHDAY"] = str(d)

    if "UNTIL" in kv and "COUNT" in kv:
        raise RecurrenceError("UNTIL and COUNT are mutually exclusive")

    if "UNTIL" in kv:
        until_dt = _parse_until_utc(kv["UNTIL"])
        if until_dt <= now:
            raise RecurrenceError(f"UNTIL must be in the future, got {kv['UNTIL']!r}")

    if "COUNT" in kv:
        try:
            count = int(kv["COUNT"])
        except ValueError as exc:
            raise RecurrenceError(f"COUNT must be int, got {kv['COUNT']!r}") from exc
        if not (1 <= count <= COUNT_MAX):
            raise RecurrenceError(f"COUNT must be 1..{COUNT_MAX}, got {count}")
        kv["COUNT"] = str(count)

    canonical = ";".join(
        f"{k}={kv[k]}"
        for k in ("FREQ", "INTERVAL", "BYDAY", "BYMONTHDAY", "UNTIL", "COUNT")
        if k in kv
    )
    try:
        rrulestr(
            f"DTSTART:{now.strftime('%Y%m%dT%H%M%SZ')}\nRRULE:{canonical}",
            forceset=False,
        )
    except (ValueError, TypeError) as exc:
        raise RecurrenceError(f"dateutil parse failed: {exc}") from exc

    return canonical


def next_occurrence(rrule: str, anchor: date, *, after: date | None = None) -> date | None:
    """Return the next occurrence ``>= after`` (default today).

    ``anchor`` is the original first occurrence (DTSTART). Returns ``None``
    if the rule has no future occurrences (UNTIL passed or COUNT exhausted).
    """
    after = after or date.today()
    body = rrule.strip()
    if body.upper().startswith("RRULE:"):
        body = body.split(":", 1)[1]
    dtstart = datetime.combine(anchor, datetime.min.time())
    try:
        rule = rrulestr(
            f"DTSTART:{dtstart.strftime('%Y%m%dT%H%M%S')}\nRRULE:{body}",
            forceset=False,
        )
    except (ValueError, TypeError):
        return None
    nxt = rule.after(datetime.combine(after, datetime.min.time()), inc=True)
    if nxt is None:
        return None
    return nxt.date()
