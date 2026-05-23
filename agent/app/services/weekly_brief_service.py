"""Weekly Brief (Phase 8.3) — the manager's digest, self-sent via Gmail.

Three layers, kept separate so the data shaping and HTML are unit-testable
without a DB or network:

  * ``build_brief_data``   — pure aggregation over tasks + conflicts
  * ``render_brief_html``  — pure HTML rendering of that aggregate
  * ``async_send_weekly_brief`` — loads from DB, builds, renders, sends via the
    Gmail MCP (requires the gmail.send scope; a token without it 403s).

Reuses the same lifecycle/provenance semantics as the rest of the app:
``confirmed_by='system'`` = auto-confirmed, ``status='pending'`` +
``confirmed_by IS NULL`` = needs review.
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

WEEKLY_BRIEF_WINDOW_DAYS = 7
_MAX_CONFLICTS_SHOWN = 10
_MAX_TEAM_ROWS = 8


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def build_brief_data(
    tasks: list[Task],
    conflicts: list[Conflict],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Aggregate the week's activity. Pure — no DB, no clock side effects."""
    now = now or datetime.now(UTC)
    today = now.date()
    window_start = now - timedelta(days=WEEKLY_BRIEF_WINDOW_DAYS)
    week_end = today + timedelta(days=7)

    new_this_week = 0
    auto_confirmed_week = 0
    confirmed_total = 0
    pending_review = 0
    overdue = 0
    due_this_week = 0

    team: dict[str, dict[str, int]] = {}

    for t in tasks:
        created = t.created_at
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created)
            except ValueError:
                created = None
        is_new = isinstance(created, datetime) and created >= window_start
        if is_new:
            new_this_week += 1
            if t.confirmed_by == "system":
                auto_confirmed_week += 1

        if t.status == "dismissed":
            continue
        if t.status == "confirmed":
            confirmed_total += 1
        elif t.status == "pending" and t.confirmed_by is None:
            pending_review += 1

        dl = _as_date(t.deadline)
        if dl is not None:
            if dl < today:
                overdue += 1
            elif today <= dl <= week_end:
                due_this_week += 1

        name = (t.assignee_canonical or t.assignee or "").strip()
        if name:
            row = team.setdefault(name, {"open": 0, "overdue": 0})
            row["open"] += 1
            if dl is not None and dl < today:
                row["overdue"] += 1

    open_conflicts = [c for c in conflicts if not c.resolved]
    team_rows = sorted(
        ({"assignee": k, **v} for k, v in team.items()),
        key=lambda r: (r["overdue"], r["open"]),
        reverse=True,
    )[:_MAX_TEAM_ROWS]

    auto_rate = round(auto_confirmed_week / new_this_week, 4) if new_this_week else 0.0

    return {
        "period_start": window_start.date().isoformat(),
        "period_end": today.isoformat(),
        "new_this_week": new_this_week,
        "auto_confirmed_week": auto_confirmed_week,
        "auto_confirm_rate": auto_rate,
        "confirmed_total": confirmed_total,
        "pending_review": pending_review,
        "overdue": overdue,
        "due_this_week": due_this_week,
        "open_conflict_count": len(open_conflicts),
        "open_conflicts": [
            {
                "conflict_type": c.conflict_type,
                "scope": c.scope,
                "description": c.description or "",
            }
            for c in open_conflicts[:_MAX_CONFLICTS_SHOWN]
        ],
        "team": team_rows,
    }


def _e(s: Any) -> str:
    return html.escape(str(s if s is not None else ""))


def render_brief_html(data: dict[str, Any]) -> str:
    """Render the aggregate as a self-contained HTML email (inline styles)."""
    rate_pct = f"{data['auto_confirm_rate'] * 100:.0f}%"

    def stat(label: str, value: Any, tone: str = "#111827") -> str:
        return (
            f'<td style="padding:8px 14px;text-align:center">'
            f'<div style="font-size:22px;font-weight:600;color:{tone}">{_e(value)}</div>'
            f'<div style="font-size:11px;color:#6b7280;text-transform:uppercase">{_e(label)}</div>'
            f"</td>"
        )

    overdue_tone = "#dc2626" if data["overdue"] else "#111827"
    conflict_tone = "#dc2626" if data["open_conflict_count"] else "#111827"

    stats_row = (
        "<table style='border-collapse:collapse;margin:8px 0'><tr>"
        + stat("New this week", data["new_this_week"])
        + stat("Auto-confirmed", f"{data['auto_confirmed_week']} ({rate_pct})", "#2563eb")
        + stat("Need review", data["pending_review"], "#2563eb")
        + stat("Overdue", data["overdue"], overdue_tone)
        + stat("Due 7d", data["due_this_week"], "#d97706")
        + stat("Open conflicts", data["open_conflict_count"], conflict_tone)
        + "</tr></table>"
    )

    if data["open_conflicts"]:
        rows = "".join(
            f"<li style='margin:4px 0'><b>{_e(c['conflict_type'])}</b>"
            f"{' · ' + _e(c['scope']) if c['scope'] else ''}"
            f"<br><span style='color:#4b5563;font-size:13px'>{_e(c['description'])}</span></li>"
            for c in data["open_conflicts"]
        )
        conflicts_html = f"<ul style='padding-left:18px;margin:6px 0'>{rows}</ul>"
        if data["open_conflict_count"] > len(data["open_conflicts"]):
            conflicts_html += (
                f"<p style='color:#6b7280;font-size:13px'>"
                f"+{data['open_conflict_count'] - len(data['open_conflicts'])} more</p>"
            )
    else:
        conflicts_html = "<p style='color:#6b7280'>No open conflicts. 🎉</p>"

    if data["team"]:
        trs = "".join(
            f"<tr><td style='padding:4px 10px'>{_e(m['assignee'])}</td>"
            f"<td style='padding:4px 10px;text-align:center'>{m['open']}</td>"
            f"<td style='padding:4px 10px;text-align:center;color:{'#dc2626' if m['overdue'] else '#111827'}'>"
            f"{m['overdue']}</td></tr>"
            for m in data["team"]
        )
        team_html = (
            "<table style='border-collapse:collapse;font-size:14px'>"
            "<tr style='color:#6b7280;font-size:12px;text-transform:uppercase'>"
            "<td style='padding:4px 10px;text-align:left'>Member</td>"
            "<td style='padding:4px 10px'>Open</td><td style='padding:4px 10px'>Overdue</td></tr>"
            f"{trs}</table>"
        )
    else:
        team_html = "<p style='color:#6b7280'>No assigned tasks.</p>"

    return f"""\
<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:640px;margin:0 auto;color:#111827">
  <h2 style="margin-bottom:2px">TaskBot Weekly Brief</h2>
  <p style="color:#6b7280;margin-top:0">{_e(data['period_start'])} → {_e(data['period_end'])}</p>
  {stats_row}
  <h3 style="margin-top:24px;margin-bottom:4px">Open conflicts</h3>
  {conflicts_html}
  <h3 style="margin-top:24px;margin-bottom:4px">Team workload</h3>
  {team_html}
  <p style="color:#9ca3af;font-size:12px;margin-top:28px">
    Sent by TaskBot. Reply STOP semantics not applicable — this is your own digest.
  </p>
</div>"""


def render_brief_text(data: dict[str, Any]) -> str:
    """Plain-text fallback for non-HTML clients."""
    lines = [
        f"TaskBot Weekly Brief ({data['period_start']} -> {data['period_end']})",
        "",
        f"New this week: {data['new_this_week']} "
        f"(auto-confirmed {data['auto_confirmed_week']}, {data['auto_confirm_rate'] * 100:.0f}%)",
        f"Need review: {data['pending_review']}  Overdue: {data['overdue']}  Due 7d: {data['due_this_week']}",
        f"Open conflicts: {data['open_conflict_count']}",
    ]
    for c in data["open_conflicts"]:
        lines.append(f"  - {c['conflict_type']} {c['scope'] or ''}: {c['description']}")
    if data["team"]:
        lines.append("")
        lines.append("Team workload:")
        for m in data["team"]:
            lines.append(f"  {m['assignee']}: {m['open']} open, {m['overdue']} overdue")
    return "\n".join(lines)


async def async_send_weekly_brief(user_id: str, access_token: str) -> dict[str, Any]:
    """Load the week's data, render the brief, and self-send it via Gmail MCP.

    Returns ``{"sent": bool, "errors": [...], "data": {...}}``. Never raises on a
    send failure — a 403 (missing gmail.send scope) is recorded and surfaced so
    the UI can prompt a reconnect, mirroring the calendar dispatch fail-safe.
    """
    from app.mcp.base_client import MCPClientError
    from app.mcp.gmail_client import GmailMCPClient

    errors: list[str] = []
    try:
        user_uuid = uuid.UUID(str(user_id))
    except ValueError:
        return {"sent": False, "errors": ["weekly_brief: invalid user_id"], "data": None}

    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_uuid)
        if not user or not user.email:
            return {"sent": False, "errors": ["weekly_brief: user or email not found"], "data": None}
        recipient = user.email
        tasks = list(
            (await session.execute(select(Task).where(Task.user_id == user_uuid))).scalars().all()
        )
        conflicts = list(
            (
                await session.execute(
                    select(Conflict).where(
                        Conflict.user_id == user_uuid,
                        Conflict.resolved == False,  # noqa: E712
                    )
                )
            ).scalars().all()
        )

    data = build_brief_data(tasks, conflicts)
    subject = (
        f"TaskBot Weekly Brief — {data['new_this_week']} new, "
        f"{data['open_conflict_count']} open conflicts"
    )

    try:
        gmail = GmailMCPClient(access_token=access_token)
        await gmail.send_message(
            to=recipient,
            subject=subject,
            body_html=render_brief_html(data),
            body_text=render_brief_text(data),
        )
        logger.info("weekly_brief sent to %s (user %s)", recipient, user_id)
        return {"sent": True, "errors": [], "data": data}
    except MCPClientError as exc:
        msg = f"weekly_brief send failed: {exc}"
        errors.append(msg)
        logger.warning(msg)
        return {"sent": False, "errors": errors, "data": data}
