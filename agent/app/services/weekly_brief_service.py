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
# Round 14 (2026-05-31): the weekly brief used to show only aggregate
# counters ("Need review: 5") without naming which tasks needed action.
# Anna's feedback: she wants to *see* the backlog in the email so she can
# triage from her inbox without opening the dashboard. Mirrors the
# Round-12 outstanding section in ``daily_digest_service``.
_MAX_OUTSTANDING_TASKS_SHOWN = 20


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
    # Round 14: collect the actual backlog rows (pending OR
    # confirmed-with-missing-fields) so the email can show *what* needs
    # attention, not just *how many*. Sorted by urgency before truncation.
    outstanding_all: list[dict[str, Any]] = []
    # Phase 3 (no-deadline UX): high/medium-priority tasks missing a
    # deadline. Mirrors daily_digest_service so the weekly view nudges
    # the user with the same prompt as the daily one.
    needs_deadline_all: list[dict[str, Any]] = []

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

        # Round 14: backlog candidate? Matches the Daily Digest definition:
        # pending OR confirmed-with-any-missing-field. Dismissed already
        # short-circuited above, so we don't have to re-check here.
        missing = list(getattr(t, "missing_fields", None) or [])
        needs_attention = (
            t.status == "pending"
            or (t.status == "confirmed" and len(missing) > 0)
        )
        if needs_attention:
            title = getattr(t, "title", None) or "(untitled)"
            outstanding_all.append({
                "title": title,
                "status": t.status,
                "assignee": name or None,
                "deadline": dl.isoformat() if dl else None,
                "missing": missing,
            })

        # Phase 3 — needs-deadline bucket for high/medium-priority
        # non-dismissed, not-done tasks without a deadline. Read priority
        # safely; test fakes (SimpleNamespace) may omit the attribute.
        # Done-state exclusion aligns the brief with /tasks default-archive.
        prio = getattr(t, "priority", None)
        if (
            dl is None
            and prio in ("high", "medium")
            and t.status != "dismissed"
            and getattr(t, "progress_state", None) != "done"
        ):
            needs_deadline_all.append({
                "title": getattr(t, "title", None) or "(untitled)",
                "status": t.status,
                "assignee": name or None,
                "priority": prio,
            })

    open_conflicts = [c for c in conflicts if not c.resolved]
    team_rows = sorted(
        ({"assignee": k, **v} for k, v in team.items()),
        key=lambda r: (r["overdue"], r["open"]),
        reverse=True,
    )[:_MAX_TEAM_ROWS]

    auto_rate = round(auto_confirmed_week / new_this_week, 4) if new_this_week else 0.0

    # Round 14: sort outstanding by urgency — overdue → due today → future →
    # no-deadline (each bucket sorted by date asc). Same key as the daily
    # digest so the two emails feel consistent.
    today_iso = today.isoformat()

    def _urgency_key(item: dict[str, Any]) -> tuple:
        dl = item.get("deadline")
        if dl is None:
            return (3, "")
        if dl < today_iso:
            return (0, dl)
        if dl == today_iso:
            return (1, dl)
        return (2, dl)

    outstanding_all.sort(key=_urgency_key)
    outstanding_samples = outstanding_all[:_MAX_OUTSTANDING_TASKS_SHOWN]
    outstanding_total = len(outstanding_all)

    # Phase 3 — sort needs-deadline by priority then title (deterministic).
    _PRIO_RANK = {"high": 0, "medium": 1}
    needs_deadline_all.sort(
        key=lambda x: (_PRIO_RANK.get(x.get("priority") or "", 99), x.get("title") or "")
    )
    needs_deadline_samples = needs_deadline_all[:_MAX_OUTSTANDING_TASKS_SHOWN]
    needs_deadline_total = len(needs_deadline_all)

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
        # Round 14: the actual backlog, age-agnostic. Used by the new
        # "Open items needing your attention" section in the email.
        "outstanding_total": outstanding_total,
        "outstanding_samples": outstanding_samples,
        # Phase 3 (no-deadline UX) — high/medium-priority tasks without
        # a deadline, surfaced as their own section.
        "needs_deadline_total": needs_deadline_total,
        "needs_deadline_samples": needs_deadline_samples,
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

    outstanding_html = _render_outstanding_html(data)
    needs_deadline_html = _render_needs_deadline_html(data)

    return f"""\
<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:640px;margin:0 auto;color:#111827">
  <h2 style="margin-bottom:2px">TaskBot Weekly Brief</h2>
  <p style="color:#6b7280;margin-top:0">{_e(data['period_start'])} → {_e(data['period_end'])}</p>
  {stats_row}
  {needs_deadline_html}
  {outstanding_html}
  <h3 style="margin-top:24px;margin-bottom:4px">Open conflicts</h3>
  {conflicts_html}
  <h3 style="margin-top:24px;margin-bottom:4px">Team workload</h3>
  {team_html}
  <p style="color:#9ca3af;font-size:12px;margin-top:28px">
    Sent by TaskBot. Reply STOP semantics not applicable — this is your own digest.
  </p>
</div>"""


def _render_needs_deadline_html(data: dict[str, Any]) -> str:
    """Phase 3 — high/medium-priority tasks without a deadline.

    Sibling of the daily-digest renderer of the same name; kept here as
    its own function so the brief stays self-contained. Empty bucket →
    empty string (don't render a "clean slate" header).
    """
    total = int(data.get("needs_deadline_total") or 0)
    samples = data.get("needs_deadline_samples") or []
    if not samples:
        return ""
    rows = ""
    for s in samples:
        prio = s.get("priority") or ""
        if prio == "high":
            prio_bg, prio_fg = "#fee2e2", "#b91c1c"
        elif prio == "medium":
            prio_bg, prio_fg = "#fef3c7", "#b45309"
        else:
            prio_bg, prio_fg = "#e5e7eb", "#374151"
        prio_chip = (
            f'<span style="display:inline-block;padding:1px 6px;border-radius:8px;'
            f'background:{prio_bg};color:{prio_fg};font-size:11px;font-weight:600;'
            f'text-transform:uppercase;letter-spacing:.04em;margin-left:6px;">'
            f"{_e(prio)}</span>"
        )
        status_chip = (
            f'<span style="display:inline-block;padding:1px 6px;border-radius:8px;'
            f'background:#e0f2fe;color:#0369a1;font-size:11px;margin-left:6px;">'
            f'{_e(s.get("status") or "")}</span>'
        )
        rows += (
            "<tr>"
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;">'
            f'{_e(s.get("title") or "")}{prio_chip}{status_chip}</td>'
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;color:#6b7280;">'
            f'{_e(s.get("assignee") or "—")}</td>'
            "</tr>"
        )
    more_footer = ""
    if total > len(samples):
        more_footer = (
            f'<p style="margin:6px 0 0 0;font-size:12px;color:#6b7280;font-style:italic;">'
            f"+ {total - len(samples)} more not shown — open TaskBot to set deadlines.</p>"
        )
    return (
        f'<h3 style="margin-top:24px;margin-bottom:4px;color:#b91c1c">'
        f"Needs a deadline ({total})</h3>"
        f'<p style="margin:0 0 6px 0;font-size:12px;color:#6b7280;">'
        f"High/medium-priority work without a deadline doesn't land on the calendar. "
        f"Pick a date so the team knows when each item is due."
        f"</p>"
        f'<table style="border-collapse:collapse;width:100%;font-size:13px;">'
        f'<thead><tr style="text-align:left;color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:.04em;">'
        f'<th style="padding:6px 10px;border-bottom:1px solid #d1d5db;">Title</th>'
        f'<th style="padding:6px 10px;border-bottom:1px solid #d1d5db;">Assignee</th>'
        f"</tr></thead>"
        f"<tbody>{rows}</tbody></table>"
        f"{more_footer}"
    )


def _render_outstanding_html(data: dict[str, Any]) -> str:
    """Round-14 backlog table — what still needs the user's attention.

    Renders the same urgency-tinted rows the Daily Digest uses, so the two
    emails share a visual idiom. Empty backlog → empty string (no "clean
    slate" copy here; the stats row already conveys it).
    """
    total = int(data.get("outstanding_total") or 0)
    samples = data.get("outstanding_samples") or []
    if not samples:
        return ""
    today_iso = data.get("period_end", "")
    rows = ""
    for s in samples:
        dl = s.get("deadline")
        if dl is None:
            dl_style = "color:#6b7280;"
            dl_label = "—"
        elif dl < today_iso:
            dl_style = "color:#b91c1c;font-weight:600;"
            dl_label = _e(dl)
        elif dl == today_iso:
            dl_style = "color:#b45309;font-weight:600;"
            dl_label = _e(dl)
        else:
            dl_style = "color:#374151;"
            dl_label = _e(dl)
        missing = ", ".join(s.get("missing") or [])
        miss_chip = (
            f'<span style="display:inline-block;padding:1px 6px;border-radius:8px;'
            f'background:#fef3c7;color:#92400e;font-size:11px;margin-left:6px;">'
            f"Missing: {_e(missing)}</span>"
            if missing
            else ""
        )
        status_chip = (
            f'<span style="display:inline-block;padding:1px 6px;border-radius:8px;'
            f'background:#e0f2fe;color:#0369a1;font-size:11px;margin-left:6px;">'
            f'{_e(s.get("status") or "")}</span>'
        )
        rows += (
            "<tr>"
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;">{_e(s.get("title") or "")}{status_chip}{miss_chip}</td>'
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;color:#6b7280;">{_e(s.get("assignee") or "—")}</td>'
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;font-variant-numeric:tabular-nums;{dl_style}">{dl_label}</td>'
            "</tr>"
        )
    more_footer = ""
    if total > len(samples):
        more_footer = (
            f'<p style="margin:6px 0 0 0;font-size:12px;color:#6b7280;font-style:italic;">'
            f"+ {total - len(samples)} more not shown — open TaskBot to see the full backlog.</p>"
        )
    return (
        f'<h3 style="margin-top:24px;margin-bottom:4px">Open items needing your attention ({total})</h3>'
        f'<p style="margin:0 0 6px 0;font-size:12px;color:#6b7280;">'
        f"Tasks still pending review or missing a field. "
        f"Overdue deadlines in red, due-today in amber."
        f"</p>"
        f'<table style="border-collapse:collapse;width:100%;font-size:13px;">'
        f'<thead><tr style="text-align:left;color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:.04em;">'
        f'<th style="padding:6px 10px;border-bottom:1px solid #d1d5db;">Title</th>'
        f'<th style="padding:6px 10px;border-bottom:1px solid #d1d5db;">Assignee</th>'
        f'<th style="padding:6px 10px;border-bottom:1px solid #d1d5db;">Deadline</th>'
        f"</tr></thead>"
        f"<tbody>{rows}</tbody></table>"
        f"{more_footer}"
    )


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
    # Phase 3 — high/medium-priority tasks without a deadline.
    nd_total = int(data.get("needs_deadline_total") or 0)
    nd_samples = data.get("needs_deadline_samples") or []
    if nd_samples:
        lines += ["", f"Needs a deadline ({nd_total}):"]
        for s in nd_samples:
            prio = s.get("priority") or ""
            lines.append(
                f"  - [{prio.upper()}] {s.get('title') or ''} · {s.get('assignee') or '—'}"
            )
        if nd_total > len(nd_samples):
            lines.append(
                f"  (+ {nd_total - len(nd_samples)} more — open TaskBot to set deadlines)"
            )

    # Round 14: same backlog list as the HTML body.
    outstanding_total = int(data.get("outstanding_total") or 0)
    outstanding_samples = data.get("outstanding_samples") or []
    if outstanding_samples:
        today_iso = data.get("period_end", "")
        lines += ["", f"Open items needing your attention ({outstanding_total}):"]
        for s in outstanding_samples:
            dl = s.get("deadline")
            if dl is None:
                dl_label = "—"
            elif dl < today_iso:
                dl_label = f"{dl} [OVERDUE]"
            elif dl == today_iso:
                dl_label = f"{dl} [TODAY]"
            else:
                dl_label = dl
            status = s.get("status") or ""
            miss = f" [missing: {', '.join(s['missing'])}]" if s.get("missing") else ""
            lines.append(
                f"  - [{status}] {s.get('title') or ''} · {s.get('assignee') or '—'} · {dl_label}{miss}"
            )
        if outstanding_total > len(outstanding_samples):
            lines.append(
                f"  (+ {outstanding_total - len(outstanding_samples)} more — open TaskBot to see all)"
            )
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
