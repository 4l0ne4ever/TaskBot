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
# Round 12 (2026-05-30): a separate "still outstanding" section lists tasks
# that need the user's attention regardless of age — pending tasks plus any
# confirmed task with a missing field. The today-only counters above don't
# convey the actual backlog; this fills that gap. Capped higher than the
# today-window list because the user requested a real backlog view, not just
# a sample.
_MAX_OUTSTANDING_TASKS_SHOWN = 20


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
    # Round 12: backlog of everything still needing attention (pending OR
    # confirmed-with-missing-fields), regardless of age. Collected here as a
    # superset of review_samples, sorted later by urgency before rendering.
    outstanding_all: list[dict[str, Any]] = []
    # Phase 3 (no-deadline UX): a dedicated bucket for high/medium-priority
    # tasks that are missing a deadline. The general "still outstanding"
    # list buries them at the bottom (sorted by urgency, no-deadline = last)
    # — but high-priority work without a deadline is the exact thing the
    # Anna persona keeps losing track of. Surface it separately at the top.
    needs_deadline_all: list[dict[str, Any]] = []

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

        missing = list(t.missing_fields or [])
        # "Needs attention" = pending OR confirmed-with-any-missing-field.
        # Dismissed tasks are excluded — the user already triaged them.
        needs_attention = (
            t.status == "pending"
            or (t.status == "confirmed" and len(missing) > 0)
        )
        # Phase 3 — read priority safely; test fakes (SimpleNamespace) may
        # omit the attribute entirely.
        prio = getattr(t, "priority", None)
        if needs_attention:
            outstanding_all.append({
                "title": t.title or "(untitled)",
                "status": t.status,
                "assignee": t.assignee,
                "deadline": _coerce_date(t.deadline).isoformat() if _coerce_date(t.deadline) else None,
                "missing": missing,
                "created": (created.date().isoformat() if created else None),
                "priority": prio,
            })

        # Phase 3 — separate "needs deadline" bucket. Only tasks the user
        # cares about (high/medium priority, not dismissed, not done) and
        # with no deadline set. Pending and confirmed both qualify; the
        # goal is to nudge the user into picking a date so the work hits
        # the calendar. Excluding ``progress_state='done'`` keeps the
        # email aligned with the /tasks default-archive rule (Phase 4):
        # don't nag about work the user already marked complete.
        if (
            t.deadline is None
            and prio in ("high", "medium")
            and t.status != "dismissed"
            and getattr(t, "progress_state", None) != "done"
        ):
            needs_deadline_all.append({
                "title": t.title or "(untitled)",
                "status": t.status,
                "assignee": t.assignee,
                "priority": prio,
            })

        if t.status == "pending":
            pending_review_now += 1
            if len(review_samples) < _MAX_REVIEW_TASKS_SHOWN:
                review_samples.append(
                    {
                        "title": t.title or "(untitled)",
                        "assignee": t.assignee,
                        "deadline": _coerce_date(t.deadline).isoformat() if _coerce_date(t.deadline) else None,
                        "missing": missing,
                    }
                )

        if t.status == "confirmed":
            dl = _coerce_date(t.deadline)
            if dl is not None:
                if dl < today:
                    overdue_now += 1
                elif dl == today:
                    due_today += 1

    # Sort outstanding by urgency: overdue first, then due-today, then
    # future-with-deadline (soonest first), then no-deadline rows last.
    today_iso = today.isoformat()
    def _urgency_key(item: dict[str, Any]) -> tuple:
        dl = item.get("deadline")
        if dl is None:
            return (3, "")              # no deadline — last
        if dl < today_iso:
            return (0, dl)              # overdue — first, by date asc
        if dl == today_iso:
            return (1, dl)              # due today — second
        return (2, dl)                  # future — third, by date asc
    outstanding_all.sort(key=_urgency_key)
    outstanding_samples = outstanding_all[:_MAX_OUTSTANDING_TASKS_SHOWN]
    outstanding_total = len(outstanding_all)

    # Phase 3 — sort needs-deadline by priority (high first), then title for
    # determinism. Cap at the same outstanding cap so the section stays
    # bounded even on big backlogs.
    _PRIO_RANK = {"high": 0, "medium": 1}
    needs_deadline_all.sort(
        key=lambda x: (_PRIO_RANK.get(x.get("priority") or "", 99), x.get("title") or "")
    )
    needs_deadline_samples = needs_deadline_all[:_MAX_OUTSTANDING_TASKS_SHOWN]
    needs_deadline_total = len(needs_deadline_all)

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
        # Round 12: full backlog of tasks needing attention, age-agnostic
        # (Anna wants to see what's *still* outstanding, not just today's).
        "outstanding_total": outstanding_total,
        "outstanding_samples": outstanding_samples,
        # Phase 3 (no-deadline UX): high/medium-priority tasks missing
        # a deadline. Rendered as its own section above the general
        # outstanding list so the user picks dates before the work slips.
        "needs_deadline_total": needs_deadline_total,
        "needs_deadline_samples": needs_deadline_samples,
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

  <h3 style="margin:22px 0 6px 0;font-size:14px;">Pending your review (today)</h3>
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

  {_render_needs_deadline_html(data)}

  {_render_outstanding_html(data)}

  <p style="margin:18px 0 0 0;font-size:12px;color:#9ca3af;">
    Sent from your own Gmail to yourself — TaskBot uses your ``gmail.send`` scope.
  </p>
</body></html>"""


def _render_needs_deadline_html(data: dict[str, Any]) -> str:
    """Phase 3 (no-deadline UX) — high/medium-priority tasks without a deadline.

    Rendered above the general outstanding list so the user is nudged to set
    dates before the work slips. Empty bucket → empty string (no clean-slate
    copy; the rest of the digest already conveys it).
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
        f'<h3 style="margin:22px 0 6px 0;font-size:14px;color:#b91c1c;">'
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
    """Render the Round-12 "Still outstanding" section below today's report.

    Lists every task that needs attention regardless of age (pending OR
    confirmed-with-missing-fields), sorted by urgency (overdue → due today →
    future → no-deadline). Capped at ``_MAX_OUTSTANDING_TASKS_SHOWN`` rows;
    a "+N more" footer surfaces the remaining count so the user knows the
    list is truncated.
    """
    total = data.get("outstanding_total", 0)
    samples = data.get("outstanding_samples", [])
    if not samples:
        # Don't render an empty section — the today section already says
        # "clean slate" when there's nothing. A second "clean slate" would
        # be noise.
        return ""
    today_iso = data.get("date_label", "")
    rows = ""
    for s in samples:
        dl = s.get("deadline")
        # Tint deadline by urgency: overdue red, due-today amber, future muted.
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
            f'Missing: {_e(missing)}</span>'
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
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;">{_e(s["title"])}{status_chip}{miss_chip}</td>'
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;color:#6b7280;">{_e(s.get("assignee") or "—")}</td>'
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;font-variant-numeric:tabular-nums;{dl_style}">{dl_label}</td>'
            "</tr>"
        )
    more_footer = ""
    if total > len(samples):
        more_footer = (
            f'<p style="margin:6px 0 0 0;font-size:12px;color:#6b7280;font-style:italic;">'
            f'+ {total - len(samples)} more not shown — open TaskBot to see the full backlog.</p>'
        )
    return (
        f'<h3 style="margin:22px 0 6px 0;font-size:14px;">Still outstanding ({total} total, any age)</h3>'
        f'<p style="margin:0 0 6px 0;font-size:12px;color:#6b7280;">'
        f"Tasks that still need your attention — pending or with missing fields — regardless of when they appeared. "
        f"Overdue deadlines are in red, due-today in amber."
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
    # Phase 3 (no-deadline UX): high/medium-priority tasks without a deadline.
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

    # Round 12: still-outstanding section (age-agnostic backlog).
    outstanding_total = data.get("outstanding_total", 0)
    outstanding_samples = data.get("outstanding_samples", [])
    if outstanding_samples:
        lines += ["", f"Still outstanding ({outstanding_total} total, any age):"]
        today_iso = data.get("date_label", "")
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
                f"  - [{status}] {s['title']} · {s.get('assignee') or '—'} · {dl_label}{miss}"
            )
        if outstanding_total > len(outstanding_samples):
            lines.append(
                f"  (+ {outstanding_total - len(outstanding_samples)} more — open TaskBot to see all)"
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
