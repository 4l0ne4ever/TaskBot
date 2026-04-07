"""
Baseline 1 — Rule-based task extraction using regex and heuristics.

No LLM calls. Pure pattern matching for titles, assignees, deadlines.
"""
from __future__ import annotations

import re
from datetime import date, timedelta


_TASK_MARKER_RE = re.compile(
    r"(?:^|\n)\s*[-•*]\s+(.+)|"
    r"(?:^|\n)\s*\d+[.)]\s*(.+)|"
    r"(?:nhờ|please|cần|need)\s+(.+?)(?:\.|$)",
    re.IGNORECASE | re.MULTILINE,
)

_NAME_RE = re.compile(
    r"\b([A-ZÀÁẢÃẠÂẦẤẨẪẬĂẰẮẲẴẶÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ]"
    r"[a-zàáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]*"
    r"(?:\s+[A-ZÀÁẢÃẠÂẦẤẨẪẬĂẰẮẲẴẶÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ]"
    r"[a-zàáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]*)*)\b"
)

_SKIP_NAMES = {
    "chào", "hi", "hey", "dear", "fyi", "note", "notice", "update",
    "cập nhật", "thông báo", "cảm ơn", "thanks", "team", "all",
    "email", "thread", "action", "items", "attendees",
    "meeting", "notes", "biên bản", "họp", "tham dự",
    "chào team", "hi team", "hi all", "kế hoạch",
    "project", "plan", "assigned", "deliverable", "due",
    "người", "nội dung", "ghi chú", "hạn",
}

_WEEKDAY_RE_VI = re.compile(r"thứ\s+(hai|ba|tư|năm|sáu|bảy|chủ nhật)", re.IGNORECASE)
_WEEKDAY_MAP_VI = {"hai": 0, "ba": 1, "tư": 2, "năm": 3, "sáu": 4, "bảy": 5, "chủ nhật": 6}

_TOMORROW_RE = re.compile(r"\b(ngày mai|tomorrow)\b", re.IGNORECASE)
_IN_N_DAYS_RE = re.compile(r"\b(?:trong|within)\s+(\d+)\s+(?:ngày|days?)\b", re.IGNORECASE)
_END_MONTH_RE = re.compile(r"\b(?:cuối tháng|end of month)\b", re.IGNORECASE)
_NEXT_WEEK_RE = re.compile(r"\b(?:tuần tới|next week|next monday)\b", re.IGNORECASE)
_BY_FRIDAY_RE = re.compile(r"\b(?:thứ sáu|friday)\b", re.IGNORECASE)
_ABS_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_ABS_DATE_SLASH_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")


def _parse_sent_at(meta: dict) -> date:
    raw = meta.get("sent_at")
    if raw:
        try:
            return date.fromisoformat(str(raw)[:10])
        except ValueError:
            pass
    return date(2026, 3, 30)


def _extract_deadline(text: str, sent: date) -> str | None:
    m = _ABS_DATE_RE.search(text)
    if m:
        try:
            return date.fromisoformat(m.group(1)).isoformat()
        except ValueError:
            pass

    m = _ABS_DATE_SLASH_RE.search(text)
    if m:
        try:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return date(y, mo, d).isoformat()
        except ValueError:
            pass

    if _TOMORROW_RE.search(text):
        return (sent + timedelta(days=1)).isoformat()

    m = _IN_N_DAYS_RE.search(text)
    if m:
        return (sent + timedelta(days=int(m.group(1)))).isoformat()

    if _END_MONTH_RE.search(text):
        if sent.month == 12:
            return date(sent.year + 1, 1, 1).isoformat()
        eom = date(sent.year, sent.month + 1, 1) - timedelta(days=1)
        return eom.isoformat()

    if _BY_FRIDAY_RE.search(text):
        days = (4 - sent.weekday()) % 7
        if days == 0 and sent.weekday() != 4:
            days = 7
        return (sent + timedelta(days=days)).isoformat()

    if _NEXT_WEEK_RE.search(text):
        days = (7 - sent.weekday()) % 7
        if days == 0:
            days = 7
        return (sent + timedelta(days=days)).isoformat()

    return None


def _extract_assignee(text: str) -> str | None:
    for m in _NAME_RE.finditer(text):
        candidate = m.group(0).strip()
        if candidate.lower() in _SKIP_NAMES or len(candidate) < 2:
            continue
        return candidate
    return None


def _extract_task_lines(text: str) -> list[str]:
    lines = []
    for m in _TASK_MARKER_RE.finditer(text):
        raw = (m.group(1) or m.group(2) or m.group(3) or "").strip()
        if raw and len(raw) > 3:
            lines.append(raw[:80])
    return lines


def _make_title(line: str) -> str:
    line = re.sub(r"\b(?:trước|by|before|within|trong)\b.*$", "", line, flags=re.IGNORECASE).strip()
    line = re.sub(r"\s+", " ", line).strip(" .,;:")
    return line[:80] if line else ""


def extract_rule_based(text: str, metadata: dict) -> dict:
    sent = _parse_sent_at(metadata)
    deadline = _extract_deadline(text, sent)
    assignee = _extract_assignee(text)

    task_lines = _extract_task_lines(text)

    if not task_lines:
        title = _make_title(text.split("\n")[0]) if text.strip() else ""
        if not title or len(title) < 5:
            return {"tasks": [], "conflicts": [], "missing_fields": []}
        task_lines = [title]

    tasks = []
    for line in task_lines:
        title = _make_title(line)
        if not title:
            continue
        line_assignee = _extract_assignee(line)
        line_deadline = _extract_deadline(line, sent)
        tasks.append({
            "title": title,
            "assignee": line_assignee or assignee,
            "deadline": line_deadline or deadline,
            "priority": None,
        })

    missing = []
    if tasks:
        if not any(t.get("deadline") for t in tasks):
            missing.append("deadline")
        if not any(t.get("assignee") for t in tasks):
            missing.append("assignee")

    return {"tasks": tasks, "conflicts": [], "missing_fields": missing}
