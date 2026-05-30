"""Daily Digest (Round 9, 2026-05-30) — end-of-day self-sent summary.

Mirrors the three-layer split of ``weekly_brief_service`` so the data shaping
and HTML rendering are unit-testable without a DB or network:

  * ``build_digest_data``         — pure aggregation over today's tasks +
                                     conflicts, no I/O
  * ``render_digest_html`` / ``render_digest_text`` — pure renderers
  * ``async_send_daily_digest``   — loads from DB, builds, renders, sends via
                                     the Gmail MCP (requires ``gmail.send``
                                     scope; a 403 is recorded, not raised)

Self-send model: the user's own OAuth token (with ``gmail.send``) is used to
send the digest from their own mailbox to themselves. Matches Weekly Brief
exactly so reviewers can see one consistent pattern across two sibling
features.

Content per the user spec:
    "bao nhiêu task auto confirm, bao nhiêu task cần review, ..."

Window: tasks created in the **last 24 hours** (rolling), counted at send
time. Pending review is a *snapshot* of the current state, not a window —
the user wants to see "what still needs me" right now.
"""
from __future__ import annotations

import html
import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.conflict import Conflict
from app.models.task import Task
from app.models.user import User

logger = logging.getLogger(__name__)

DAILY_DIGEST_WINDOW_HOURS = 24
_MAX_REVIEW_TASKS_SHOWN = 8


def _coerce_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _coerce_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def build_digest_data(
    tasks: list[Task],
    conflicts: list[Conflict],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Aggregate the last 24h of activity. Pure — no DB, no clock side effects."""
    now = now or datetime.now(UTC)
    today = now.date()
    window_start = now - timedelta(hours=DAILY_DIGEST_WINDOW_HOURS)

    new_today = 0
    auto_confirmed_today = 0
    user_confirmed_today = 0
    dismissed_today = 0
    pending_review_now = 0     # snapshot, not window — what still needs the user
    overdue_now = 0            # confirmed tasks past their deadline as of today
    due_today = 0
    review_samples: list[dict[str, Any]] = []

    for t in tasks:
        created = _coerce_dt(t.created_at)
        is_new = created is not None and created >= window_start
        if is_new:
            new_today += 1
            if t.confirmed_by == "system":
                auto_confirmed_today += 1
            elif t.status == "confirmed" and t.confirmed_by == "user":
                user_confirmed_today += 1
            if t.status == "dismissed":
                dismissed_today += 1

        if t.status == "pending":
            pending_review_now += 1
            if len(review_samples) < _MAX_REVIEW_TASKS_SHOWN:
                review_samples.append(
                    {
                        "title": t.title or "(untitled)",
                        "assignee": t.assignee,
                        "deadline": _coerce_date(t.deadline).isoformat() if _coerce_date(t.deadline) else None,
                        "missing": list(t.missing_fields or []),
                    }
                )

        if t.status == "confirmed":
            dl = _coerce_date(t.deadline)
            if dl is not None:
                if dl < today:
                    overdue_now += 1
                elif dl == today:
                    due_today += 1

    conflicts_today = 0
    open_conflicts = 0
    for c in conflicts:
        created = _coerce_dt(c.created_at)
        if created is not None and created >= window_start:
            conflicts_today += 1
        if not c.resolved:
            open_conflicts += 1

    return {
        "as_of": now.isoformat(),
        "date_label": today.isoformat(),
        "window_hours": DAILY_DIGEST_WINDOW_HOURS,
        "new_today": new_today,
        "auto_confirmed_today": auto_confirmed_today,
        "user_confirmed_today": user_confirmed_today,
        "dismissed_today": dismissed_today,
        "pending_review_now": pending_review_now,
        "overdue_now": overdue_now,
        "due_today": due_today,
        "conflicts_today": conflicts_today,
        "open_conflicts": open_conflicts,
        "review_samples": review_samples,
    }


def _e(s: Any) -> str:
    return html.escape(str(s)) if s is not None else ""


def render_digest_html(data: dict[str, Any]) -> str:
    """Render the digest as a single HTML email body. Minimal styling, inline only —
    Gmail strips most CSS. Headlines first, then a short review-needed list."""
    samples_rows = ""
    for s in data["review_samples"]:
        missing = ", ".join(s["missing"]) if s["missing"] else ""
        miss_chip = (
            f'<span style="display:inline-block;padding:1px 6px;border-radius:8px;'
            f'background:#fef3c7;color:#92400e;font-size:11px;margin-left:6px;">'
            f'Missing: {_e(missing)}</span>'
            if missing
            else ""
        )
        samples_rows += (
            "<tr>"
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;">{_e(s["title"])}{miss_chip}</td>'
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;color:#6b7280;">'
            f'{_e(s["assignee"] or "—")}</td>'
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;color:#6b7280;font-variant-numeric:tabular-nums;">'
            f'{_e(s["deadline"] or "—")}</td>'
            "</tr>"
        )
    if not samples_rows:
        samples_rows = (
            '<tr><td colspan="3" style="padding:8px 10px;color:#6b7280;font-style:italic;">'
            "Nothing pending review — clean slate.</td></tr>"
        )

    return f"""<!doctype html>
<html><body style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:640px;margin:0 auto;padding:20px;color:#111827;">
  <h2 style="margin:0 0 4px 0;">TaskBot — Daily Digest</h2>
  <p style="margin:0 0 16px 0;color:#6b7280;font-size:13px;">For {_e(data["date_label"])} · last {data["window_hours"]}h</p>

  <table style="border-collapse:collapse;width:100%;margin-bottom:18px;">
    <tr>
      <td style="padding:10px;background:#f0f9ff;border-radius:6px;width:25%;">
        <div style="font-size:28px;font-weight:700;color:#0369a1;">{data["auto_confirmed_today"]}</div>
        <div style="font-size:11px;color:#0369a1;text-transform:uppercase;letter-spacing:.04em;">Auto-confirmed today</div>
      </td>
      <td style="width:8px;"></td>
      <td style="padding:10px;background:#fffbeb;border-radius:6px;width:25%;">
        <div style="font-size:28px;font-weight:700;color:#b45309;">{data["pending_review_now"]}</div>
        <div style="font-size:11px;color:#b45309;text-transform:uppercase;letter-spacing:.04em;">Need your review</div>
      </td>
      <td style="width:8px;"></td>
      <td style="padding:10px;background:#fee2e2;border-radius:6px;width:25%;">
        <div style="font-size:28px;font-weight:700;color:#b91c1c;">{data["overdue_now"]}</div>
        <div style="font-size:11px;color:#b91c1c;text-transform:uppercase;letter-spacing:.04em;">Overdue</div>
      </td>
    </tr>
  </table>

  <p style="margin:0 0 6px 0;font-size:13px;color:#374151;">
    New tasks today: <b>{data["new_today"]}</b>
    &nbsp;·&nbsp; You confirmed: <b>{data["user_confirmed_today"]}</b>
    &nbsp;·&nbsp; Dismissed: <b>{data["dismissed_today"]}</b>
    &nbsp;·&nbsp; Due today: <b>{data["due_today"]}</b>
    &nbsp;·&nbsp; Conflicts (new today / still open): <b>{data["conflicts_today"]} / {data["open_conflicts"]}</b>
  </p>

  <h3 style="margin:22px 0 6px 0;font-size:14px;">Pending your review</h3>
  <table style="border-collapse:collapse;width:100%;font-size:13px;">
    <thead>
      <tr style="text-align:left;color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:.04em;">
        <th style="padding:6px 10px;border-bottom:1px solid #d1d5db;">Title</th>
        <th style="padding:6px 10px;border-bottom:1px solid #d1d5db;">Assignee</th>
        <th style="padding:6px 10px;border-bottom:1px solid #d1d5db;">Deadline</th>
      </tr>
    </thead>
    <tbody>{samples_rows}</tbody>
  </table>

  <p style="margin:18px 0 0 0;font-size:12px;color:#9ca3af;">
    Sent from your own Gmail to yourself — TaskBot uses your ``gmail.send`` scope.
  </p>
</body></html>"""


def render_digest_text(data: dict[str, Any]) -> str:
    """Plaintext fallback — same content, no styling. Gmail uses it when the
    recipient's client refuses HTML."""
    lines = [
        f"TaskBot — Daily Digest for {data['date_label']}",
        f"(last {data['window_hours']}h)",
        "",
        f"  Auto-confirmed today : {data['auto_confirmed_today']}",
        f"  Need your review     : {data['pending_review_now']}",
        f"  Overdue              : {data['overdue_now']}",
        "",
        f"  New tasks today      : {data['new_today']}",
        f"  You confirmed today  : {data['user_confirmed_today']}",
        f"  Dismissed today      : {data['dismissed_today']}",
        f"  Due today            : {data['due_today']}",
        f"  Conflicts (new/open) : {data['conflicts_today']} / {data['open_conflicts']}",
        "",
        "Pending your review:",
    ]
    if not data["review_samples"]:
        lines.append("  (nothing — clean slate)")
    else:
        for s in data["review_samples"]:
            miss = f" [missing: {', '.join(s['missing'])}]" if s["missing"] else ""
            lines.append(
                f"  - {s['title']} · {s['assignee'] or '—'} · {s['deadline'] or '—'}{miss}"
            )
    lines += [
        "",
        "(Sent from your own Gmail to yourself — gmail.send scope.)",
    ]
    return "\n".join(lines)


async def async_send_daily_digest(user_id: str, access_token: str) -> dict[str, Any]:
    """Load today's data, render the digest, and self-send it via Gmail MCP.

    Returns ``{"sent": bool, "errors": [...], "data": {...}}``. Never raises on a
    send failure — a 403 (missing gmail.send scope) is recorded and surfaced so
    the UI can prompt a reconnect. Mirrors ``async_send_weekly_brief`` exactly.
    """
    from app.mcp.base_client import MCPClientError
    from app.mcp.gmail_client import GmailMCPClient

    errors: list[str] = []
    try:
        user_uuid = uuid.UUID(str(user_id))
    except ValueError:
        return {"sent": False, "errors": ["daily_digest: invalid user_id"], "data": None}

    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_uuid)
        if not user or not user.email:
            return {"sent": False, "errors": ["daily_digest: user or email not found"], "data": None}
        recipient = user.email
        tasks = list(
            (await session.execute(select(Task).where(Task.user_id == user_uuid))).scalars().all()
        )
        conflicts = list(
            (
                await session.execute(
                    select(Conflict).where(Conflict.user_id == user_uuid)
                )
            ).scalars().all()
        )

    data = build_digest_data(tasks, conflicts)
    subject = (
        f"TaskBot Daily Digest — {data['auto_confirmed_today']} auto-confirmed, "
        f"{data['pending_review_now']} need review"
    )

    try:
        gmail = GmailMCPClient(access_token=access_token)
        await gmail.send_message(
            to=recipient,
            subject=subject,
            body_html=render_digest_html(data),
            body_text=render_digest_text(data),
        )
        logger.info("daily_digest sent to %s (user %s)", recipient, user_id)
        return {"sent": True, "errors": [], "data": data}
    except MCPClientError as exc:
        msg = f"daily_digest send failed: {exc}"
        errors.append(msg)
        logger.warning(msg)
        return {"sent": False, "errors": errors, "data": data}
