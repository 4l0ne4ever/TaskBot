#!/usr/bin/env python3
"""
Generate the labeled evaluation dataset for TaskBot.

Outputs tests/eval/labeled_dataset.json with 250 samples across 17 categories.
Uses deterministic seed for reproducibility. Re-run to regenerate.

Categories:
  Core (180):
    email_simple(30), email_multi_task(25), email_no_task(25),
    email_ambiguous(20), doc_simple(20), doc_meeting_notes(15),
    conflict_deadline(15), conflict_assignee(10),
    missing_deadline(10), missing_assignee(10)
  Edge cases (70):
    edge_mixed_lang(10), edge_noisy_long(10), edge_forwarded(8),
    edge_priority(10), edge_tricky_negative(15),
    edge_special_format(10), edge_nickname(7)
"""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

OUT_PATH = Path(__file__).parent / "labeled_dataset.json"

VN_NAMES_FULL = [
    "Nguyễn Văn An", "Trần Thị Bình", "Lê Minh Đức", "Phạm Hương",
    "Hoàng Nam", "Vũ Thảo", "Phan Đức Anh", "Đặng Tuấn Kiệt",
    "Bùi Lan Anh", "Hồ Quang Huy", "Ngô Thanh Tùng", "Dương Thị Mai",
    "Lý Hoàng Long", "Huỳnh Minh Tâm", "Đỗ Văn Hải",
]
VN_NAMES_SHORT = [
    "Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Vũ", "Phan",
    "Đặng", "Bùi", "Hồ", "Ngô", "Dương", "Lý", "Huỳnh", "Đỗ",
]
VN_NICKNAMES = [
    "An", "Bình", "Đức", "Hương", "Nam", "Thảo", "Lan", "Huy",
    "Tùng", "Mai", "Long", "Tâm", "Hải", "Kiệt", "Anh",
]
EN_NAMES = [
    "Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace",
    "Henry", "Ivy", "Jack", "Karen", "Leo", "Maria", "Nathan",
    "Olivia", "Paul", "Quinn", "Rachel", "Steve", "Tina",
]
EN_NICKNAMES = [
    "Al", "Bobby", "Chuck", "Di", "Frankie", "Hank", "Nat", "Rach",
]

VN_SUBJECTS = [
    "Nhắc việc", "Cập nhật tiến độ", "Phân công công việc",
    "Yêu cầu nộp báo cáo", "Họp team", "Chuẩn bị demo",
    "Review tài liệu", "Gửi kết quả", "Kế hoạch tuần tới",
    "Bàn giao công việc", "Reminder", "[Urgent] Deadline update",
]
EN_SUBJECTS = [
    "Task reminder", "Progress update", "Assignment", "Report due",
    "Team meeting", "Demo preparation", "Document review", "Deliverables",
    "Weekly plan", "Handover", "RE: Follow-up", "FW: Action needed",
]

VN_TASK_VERBS = [
    "nộp", "gửi", "hoàn thành", "chuẩn bị", "viết", "review",
    "kiểm tra", "cập nhật", "chỉnh sửa", "tổng hợp", "soạn", "dịch",
]
EN_TASK_VERBS = [
    "submit", "send", "complete", "prepare", "write", "review",
    "check", "update", "revise", "compile", "draft", "finalize",
]

VN_TASK_OBJECTS = [
    "báo cáo Q1", "tài liệu thiết kế", "slide thuyết trình",
    "bảng số liệu tài chính", "bản kế hoạch dự án", "file mockup UI",
    "kết quả kiểm thử", "proposal hợp tác", "biên bản họp",
    "báo cáo tháng 3", "hợp đồng NDA", "bản đánh giá nhân sự",
    "tài liệu API docs", "wireframe trang chủ",
]
EN_TASK_OBJECTS = [
    "Q1 report", "design document", "presentation slides",
    "financial spreadsheet", "project plan", "UI mockup file",
    "test results", "partnership proposal", "meeting minutes",
    "March report", "NDA contract", "performance review",
    "API documentation", "homepage wireframe",
]

BASE_DATE = date(2026, 3, 30)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pick(items):
    return random.choice(items)


def _pick_n(items, n):
    return random.sample(items, min(n, len(items)))


def _sent_at(offset_days=0):
    return (BASE_DATE + timedelta(days=offset_days)).isoformat()


def _dl(sent: str, days: int) -> str:
    return (date.fromisoformat(sent) + timedelta(days=days)).isoformat()


def _friday(sent: str) -> str:
    d = date.fromisoformat(sent)
    off = (4 - d.weekday()) % 7
    if off == 0 and d.weekday() == 4:
        return d.isoformat()
    return (d + timedelta(days=off)).isoformat()


def _next_friday(sent: str) -> str:
    d = date.fromisoformat(sent)
    off = (4 - d.weekday()) % 7
    if off == 0:
        off = 7
    return (d + timedelta(days=off + 7 if off > 0 else 7)).isoformat()


def _next_monday(sent: str) -> str:
    d = date.fromisoformat(sent)
    off = (7 - d.weekday()) % 7
    return (d + timedelta(days=off or 7)).isoformat()


def _eom(sent: str) -> str:
    d = date.fromisoformat(sent)
    nxt = date(d.year, d.month + 1, 1) if d.month < 12 else date(d.year + 1, 1, 1)
    return (nxt - timedelta(days=1)).isoformat()


def _abs_date(y=2026, m=4, d=15) -> str:
    return date(y, m, d).isoformat()


_counter = 0


def _id(prefix="eval"):
    global _counter
    _counter += 1
    return f"{prefix}-{_counter:03d}"


def _vn() -> bool:
    return random.random() < 0.7


def _vn_name():
    return _pick(VN_NAMES_FULL) if random.random() < 0.5 else _pick(VN_NAMES_SHORT)


def _en_name():
    return _pick(EN_NAMES)


def _name(is_vi):
    return _vn_name() if is_vi else _en_name()


def _verb(is_vi):
    return _pick(VN_TASK_VERBS if is_vi else EN_TASK_VERBS)


def _obj(is_vi):
    return _pick(VN_TASK_OBJECTS if is_vi else EN_TASK_OBJECTS)


def _mk_title(verb, obj):
    return f"{verb.capitalize()} {obj}"


def _sample(sid, cat, src, lang, text, meta, expected, notes, edge_tags=None):
    s = {
        "id": sid,
        "category": cat,
        "source_type": src,
        "language": lang,
        "input_text": text,
        "metadata": meta,
        "expected": expected,
        "annotation_notes": notes,
    }
    if edge_tags:
        s["edge_tags"] = edge_tags
    return s


# ---------------------------------------------------------------------------
# Deadline variant pickers
# ---------------------------------------------------------------------------

DL_EXPRS_VI = [
    ("trước thứ Sáu này", lambda s: _friday(s), "thứ Sáu này"),
    ("trước ngày mai", lambda s: _dl(s, 1), "ngày mai"),
    ("trong 3 ngày tới", lambda s: _dl(s, 3), "sent_at + 3"),
    ("trước cuối tháng", lambda s: _eom(s), "cuối tháng"),
    ("trước tuần tới", lambda s: _next_monday(s), "tuần tới → Monday"),
    ("trước 15/4", lambda s: _abs_date(2026, 4, 15), "absolute date 15/4"),
    ("trước thứ Sáu tới", lambda s: _next_friday(s), "thứ Sáu tới"),
    ("trong vòng 2 ngày", lambda s: _dl(s, 2), "sent_at + 2"),
    ("trước ngày 10 tháng 4", lambda s: _abs_date(2026, 4, 10), "absolute 10/4"),
]

DL_EXPRS_EN = [
    ("by this Friday", lambda s: _friday(s), "this Friday"),
    ("by tomorrow", lambda s: _dl(s, 1), "tomorrow"),
    ("within 5 days", lambda s: _dl(s, 5), "sent_at + 5"),
    ("by end of month", lambda s: _eom(s), "EOM"),
    ("by next Monday", lambda s: _next_monday(s), "next Monday"),
    ("by April 15", lambda s: _abs_date(2026, 4, 15), "absolute Apr 15"),
    ("by next Friday", lambda s: _next_friday(s), "next Friday"),
    ("within 48 hours", lambda s: _dl(s, 2), "sent_at + 2"),
    ("before April 10th", lambda s: _abs_date(2026, 4, 10), "absolute Apr 10"),
    ("no later than Wednesday", lambda s: _dl(s, (2 - date.fromisoformat(s).weekday()) % 7 or 7), "next Wed"),
]


def _dl_vi(sent):
    expr, fn, note = _pick(DL_EXPRS_VI)
    return expr, fn(sent), note


def _dl_en(sent):
    expr, fn, note = _pick(DL_EXPRS_EN)
    return expr, fn(sent), note


# ===================================================================
# CORE CATEGORIES
# ===================================================================

def gen_email_simple(i):
    sent = _sent_at(i % 14)
    iv = _vn()
    name = _name(iv)
    v, o = _verb(iv), _obj(iv)
    title = _mk_title(v, o)

    templates_vi = [
        lambda: f"Chào team,\n\nNhờ {name} {v} {o} {dl_expr} nhé. Cảm ơn.",
        lambda: f"Hi {name},\n\nBạn {v} {o} {dl_expr} giúp mình nhé. Thanks!",
        lambda: f"@{name} — {v} {o} {dl_expr}. Ưu tiên cái này nhé.",
        lambda: f"Gửi {name},\n\nPhiền bạn {v} {o} {dl_expr}.\n\nTrân trọng,\nQuản lý dự án",
        lambda: f"Anh/chị {name} ơi, nhờ {v} {o} {dl_expr} ạ.",
    ]
    templates_en = [
        lambda: f"Hi team,\n\nPlease ask {name} to {v} the {o} {dl_expr}. Thanks.",
        lambda: f"Hey {name},\n\nCould you {v} the {o} {dl_expr}? Appreciate it.",
        lambda: f"{name} — please {v} the {o} {dl_expr}.",
        lambda: f"Dear {name},\n\nKindly {v} the {o} {dl_expr}.\n\nBest regards,\nProject Manager",
        lambda: f"Quick reminder: {name}, {o} is due {dl_expr}. Please {v} it.",
    ]

    if iv:
        dl_expr, dl_val, dl_note = _dl_vi(sent)
        text = _pick(templates_vi)()
    else:
        dl_expr, dl_val, dl_note = _dl_en(sent)
        text = _pick(templates_en)()

    return _sample(
        _id(), "email_simple", "gmail", "vi" if iv else "en", text,
        {"sent_at": sent, "sender": _pick(["manager@company.com", "lead@team.vn", "boss@example.com"]), "subject": _pick(VN_SUBJECTS if iv else EN_SUBJECTS)},
        {"tasks": [{"title": title, "assignee": name, "deadline": dl_val, "priority": None}], "conflicts": [], "missing_fields": []},
        f"deadline: '{dl_expr}' = {dl_note}",
    )


def gen_email_multi_task(i):
    sent = _sent_at(i % 14)
    iv = _vn()
    n_tasks = random.choice([2, 2, 2, 3, 3])
    names = _pick_n(VN_NAMES_FULL if iv else EN_NAMES, n_tasks)
    verbs = [_verb(iv) for _ in range(n_tasks)]
    objs = _pick_n(VN_TASK_OBJECTS if iv else EN_TASK_OBJECTS, n_tasks)

    tasks_expected = []
    lines = []
    for idx in range(n_tasks):
        dl_val = _dl(sent, random.choice([2, 3, 5, 7]))
        days = (date.fromisoformat(dl_val) - date.fromisoformat(sent)).days
        if iv:
            lines.append(f"{idx+1}. {names[idx]}: {verbs[idx]} {objs[idx]} trong {days} ngày.")
        else:
            lines.append(f"{idx+1}. {names[idx]}: {verbs[idx]} the {objs[idx]} within {days} days.")
        tasks_expected.append({"title": _mk_title(verbs[idx], objs[idx]), "assignee": names[idx], "deadline": dl_val, "priority": None})

    if iv:
        text = f"Chào team,\n\n" + "\n".join(lines) + "\n\nCảm ơn mọi người."
    else:
        text = f"Hi all,\n\n" + "\n".join(lines) + "\n\nThanks everyone."

    return _sample(
        _id(), "email_multi_task", "gmail", "vi" if iv else "en", text,
        {"sent_at": sent, "sender": "lead@company.com", "subject": _pick(VN_SUBJECTS if iv else EN_SUBJECTS)},
        {"tasks": tasks_expected, "conflicts": [], "missing_fields": []},
        f"{n_tasks} tasks",
        edge_tags=["3_tasks"] if n_tasks == 3 else None,
    )


def gen_email_no_task(i):
    sent = _sent_at(i % 14)
    iv = _vn()

    vi_pool = [
        ("Họp sáng nay diễn ra suôn sẻ. Báo cáo Q1 đã được nộp đúng hạn. Cảm ơn team!", "past-tense completion"),
        ("Kết quả kiểm thử tuần này khả quan. Không có lỗi nghiêm trọng nào.", "informational status"),
        ("FYI: lịch nghỉ lễ 30/4 - 1/5 đã được cập nhật trên hệ thống.", "FYI announcement"),
        ("Cảm ơn mọi người đã tham gia buổi workshop hôm qua. Slide đã được upload.", "thank-you / past-tense"),
        ("Phòng họp tầng 3 sẽ bảo trì từ thứ Hai tới. Mọi người lưu ý nhé.", "facility notice"),
        ("Dưới đây là link tài liệu tham khảo: https://docs.google.com/xxx\n\nMọi người đọc qua nhé.", "link sharing — no action item"),
        ("Tôi đã hoàn thành xong phần thiết kế database rồi ạ.", "self-report completion"),
        ("Chúc mừng team đã đạt target Q1! 🎉", "celebration — no task"),
        ("Mình vừa push code lên branch feature/auth. Mọi người có thể pull về test.", "dev status update"),
        ("Nhắc lại: công ty nghỉ lễ từ 29/4 đến 3/5.", "schedule reminder — no task"),
    ]
    en_pool = [
        ("Great news — the Q1 report was submitted on time. Thanks team!", "past-tense completion"),
        ("Test results this week look good. No critical issues found.", "informational status"),
        ("FYI: holiday schedule for April has been updated in the system.", "FYI announcement"),
        ("Thanks everyone for attending the workshop. Slides are on Drive.", "thank-you / past-tense"),
        ("The 3rd floor meeting room will be under maintenance next week.", "facility notice"),
        ("Here's the reference doc: https://docs.google.com/xxx — take a look when you can.", "link sharing — no action"),
        ("I've finished the database design.", "self-report completion"),
        ("Congrats team on hitting our Q1 targets! 🎉", "celebration — no task"),
        ("Just pushed code to feature/auth. Feel free to pull and test.", "dev status update"),
        ("Reminder: the office is closed April 29–May 3 for holidays.", "schedule reminder — no task"),
    ]

    pool = vi_pool if iv else en_pool
    text, note = _pick(pool)
    return _sample(
        _id(), "email_no_task", "gmail", "vi" if iv else "en", text,
        {"sent_at": sent, "sender": "info@company.com", "subject": "FYI"},
        {"tasks": [], "conflicts": [], "missing_fields": []},
        f"No actionable task: {note}",
    )


def gen_email_ambiguous(i):
    sent = _sent_at(i % 14)
    iv = _vn()
    name = _name(iv)
    o = _obj(iv)
    v = _verb(iv)
    title = _mk_title(v, o)

    vi_variants = [
        (f"{name} xử lý {o} sớm nhất có thể nhé.", "ASAP = null deadline"),
        (f"Khi nào rảnh thì {name} check lại {o} giúp.", "no concrete deadline"),
        (f"Nhờ {name} {v} {o} trong thời gian tới.", "vague 'thời gian tới'"),
        (f"{name} cố gắng xong {o} càng sớm càng tốt ạ.", "'càng sớm càng tốt' = null"),
        (f"Bạn {name} thu xếp {v} {o} khi thuận tiện nhé.", "'khi thuận tiện' = null"),
    ]
    en_variants = [
        (f"{name}, please handle the {o} ASAP.", "ASAP = null deadline"),
        (f"When you get a chance, {name}, please look into the {o}.", "no concrete deadline"),
        (f"Could {name} work on the {o} sometime soon?", "vague 'soon'"),
        (f"{name} — try to get the {o} done as soon as possible.", "'as soon as possible' = null"),
        (f"Whenever convenient, {name}, please {v} the {o}.", "'whenever convenient' = null"),
    ]

    text, note = _pick(vi_variants if iv else en_variants)
    return _sample(
        _id(), "email_ambiguous", "gmail", "vi" if iv else "en", text,
        {"sent_at": sent, "sender": "team@company.com", "subject": _pick(VN_SUBJECTS if iv else EN_SUBJECTS)},
        {"tasks": [{"title": title, "assignee": name, "deadline": None, "priority": None}], "conflicts": [], "missing_fields": ["deadline"]},
        note,
    )


def gen_doc_simple(i):
    sent = _sent_at(i % 14)
    iv = _vn()
    name = _name(iv)
    o = _obj(iv)
    dl_val = _dl(sent, random.choice([3, 5, 7, 10, 14]))
    dl_fmt = date.fromisoformat(dl_val).strftime("%d/%m/%Y") if iv else dl_val
    title = o[0].upper() + o[1:] if o[0].islower() else o

    vi_templates = [
        f"Kế hoạch dự án\n\nNgười phụ trách: {name}\nNội dung: {o}\nHạn nộp: {dl_fmt}",
        f"PHÂN CÔNG CÔNG VIỆC\n\n- Nhân viên: {name}\n- Nhiệm vụ: {o}\n- Deadline: {dl_fmt}",
        f"To-do list:\n\n☐ {o} — {name} — hạn {dl_fmt}",
    ]
    en_templates = [
        f"Project Plan\n\nAssigned to: {name}\nDeliverable: {o}\nDue date: {dl_val}",
        f"WORK ASSIGNMENT\n\n- Staff: {name}\n- Task: {o}\n- Deadline: {dl_val}",
        f"To-do list:\n\n☐ {o} — {name} — due {dl_val}",
    ]

    text = _pick(vi_templates if iv else en_templates)
    return _sample(
        _id(), "doc_simple", "drive", "vi" if iv else "en", text,
        {"sent_at": sent, "sender": None, "subject": None},
        {"tasks": [{"title": title, "assignee": name, "deadline": dl_val, "priority": None}], "conflicts": [], "missing_fields": []},
        f"doc with explicit date {dl_val}",
    )


def gen_doc_meeting_notes(i):
    sent = _sent_at(i % 14)
    iv = _vn()
    n = random.choice([2, 2, 3])
    names = _pick_n(VN_NAMES_FULL if iv else EN_NAMES, n)
    objs = _pick_n(VN_TASK_OBJECTS if iv else EN_TASK_OBJECTS, n)
    dl = _friday(sent)

    items = []
    tasks = []
    for idx in range(n):
        t = objs[idx][0].upper() + objs[idx][1:] if objs[idx][0].islower() else objs[idx]
        if iv:
            items.append(f"- {names[idx]}: {objs[idx]} trước thứ Sáu")
        else:
            items.append(f"- {names[idx]}: {objs[idx]} by Friday")
        tasks.append({"title": t, "assignee": names[idx], "deadline": dl, "priority": None})

    if iv:
        text = f"Biên bản họp ngày {sent}\n\nTham dự: {', '.join(names)}\n\nAction items:\n" + "\n".join(items)
    else:
        text = f"Meeting Notes — {sent}\n\nAttendees: {', '.join(names)}\n\nAction items:\n" + "\n".join(items)

    return _sample(
        _id(), "doc_meeting_notes", "drive", "vi" if iv else "en", text,
        {"sent_at": sent, "sender": None, "subject": None},
        {"tasks": tasks, "conflicts": [], "missing_fields": []},
        f"meeting notes; {n} tasks all due Friday {dl}",
    )


def gen_conflict_deadline(i):
    sent = _sent_at(i % 14)
    iv = _vn()
    name = _name(iv)
    o = _obj(iv)
    title = o[0].upper() + o[1:] if o[0].islower() else o
    dl_a = _friday(sent)
    dl_b = _dl(sent, 1)

    if iv:
        text = (
            f"Email thread:\n\n"
            f"[Email 1 — {_sent_at((i % 14) - 2)}]\n"
            f"{name}, {o} nộp trước thứ Sáu nhé.\n\n"
            f"[Email 2 — {sent}]\n"
            f"Cập nhật: {o} cần nộp trước ngày mai."
        )
    else:
        text = (
            f"Email thread:\n\n"
            f"[Email 1 — {_sent_at((i % 14) - 2)}]\n"
            f"{name}, please submit the {o} by Friday.\n\n"
            f"[Email 2 — {sent}]\n"
            f"Update: the {o} is now due by tomorrow."
        )
    return _sample(
        _id("dc"), "conflict_deadline", "gmail", "vi" if iv else "en", text,
        {"sent_at": sent, "sender": "pm@company.com", "subject": "Re: deadline"},
        {
            "tasks": [{"title": title, "assignee": name, "deadline": dl_b, "priority": None}],
            "conflicts": [{"type": "deadline_conflict", "task_title": title, "source_a_value": dl_a, "source_b_value": dl_b}],
            "missing_fields": [],
        },
        f"Email 1: Friday ({dl_a}), Email 2: tomorrow ({dl_b})",
    )


def gen_conflict_assignee(i):
    sent = _sent_at(i % 14)
    iv = _vn()
    pool = VN_NAMES_FULL if iv else EN_NAMES
    a, b = _pick_n(pool, 2)
    o = _obj(iv)
    title = o[0].upper() + o[1:] if o[0].islower() else o
    dl = _friday(sent)

    if iv:
        text = (
            f"Email thread:\n\n"
            f"[Email 1]\n{a} phụ trách {o}, nộp trước thứ Sáu.\n\n"
            f"[Email 2]\nĐã đổi: {b} phụ trách {o} thay {a}."
        )
    else:
        text = (
            f"Email thread:\n\n"
            f"[Email 1]\n{a} is responsible for the {o}, due Friday.\n\n"
            f"[Email 2]\nUpdate: {b} will take over the {o} from {a}."
        )
    return _sample(
        _id("ac"), "conflict_assignee", "gmail", "vi" if iv else "en", text,
        {"sent_at": sent, "sender": "lead@company.com", "subject": "Re: assignment"},
        {
            "tasks": [{"title": title, "assignee": b, "deadline": dl, "priority": None}],
            "conflicts": [{"type": "assignee_conflict", "task_title": title, "source_a_value": a, "source_b_value": b}],
            "missing_fields": [],
        },
        f"Email 1: {a}, Email 2: reassigned to {b}",
    )


def gen_missing_deadline(i):
    sent = _sent_at(i % 14)
    iv = _vn()
    name = _name(iv)
    v, o = _verb(iv), _obj(iv)

    if iv:
        templates = [
            f"Nhờ {name} {v} {o}. Cảm ơn.",
            f"{name} ơi, {v} {o} giúp mình nhé.",
            f"Phiền {name} {v} {o}. Mình cần kết quả sớm.",
        ]
    else:
        templates = [
            f"Hi {name}, please {v} the {o}. Thanks.",
            f"{name}, could you {v} the {o}?",
            f"Reminder for {name}: please {v} the {o} when you can.",
        ]
    text = _pick(templates)
    return _sample(
        _id(), "missing_deadline", "gmail", "vi" if iv else "en", text,
        {"sent_at": sent, "sender": "team@company.com", "subject": _pick(VN_SUBJECTS if iv else EN_SUBJECTS)},
        {"tasks": [{"title": _mk_title(v, o), "assignee": name, "deadline": None, "priority": None}], "conflicts": [], "missing_fields": ["deadline"]},
        "no deadline mentioned",
    )


def gen_missing_assignee(i):
    sent = _sent_at(i % 14)
    iv = _vn()
    o = _obj(iv)
    dl = _friday(sent)
    title = f"Hoàn thành {o}" if iv else f"Complete {o}"

    if iv:
        templates = [
            f"Cần hoàn thành {o} trước thứ Sáu.",
            f"Ai đó hoàn thành {o} trước thứ Sáu nhé.",
            f"Task: {o} — deadline thứ Sáu. Chưa assign.",
        ]
    else:
        templates = [
            f"The {o} needs to be completed by Friday.",
            f"Someone please complete the {o} by Friday.",
            f"Task: {o} — due Friday. Unassigned.",
        ]
    text = _pick(templates)
    return _sample(
        _id(), "missing_assignee", _pick(["gmail", "drive"]), "vi" if iv else "en", text,
        {"sent_at": sent, "sender": "team@company.com", "subject": "reminder"},
        {"tasks": [{"title": title, "assignee": None, "deadline": dl, "priority": None}], "conflicts": [], "missing_fields": ["assignee"]},
        f"no assignee; deadline=Friday {dl}",
    )


# ===================================================================
# EDGE CASE CATEGORIES
# ===================================================================

def gen_edge_mixed_lang(i):
    """Code-switching: Vietnamese text with English terms or vice versa."""
    sent = _sent_at(i % 14)
    name = _vn_name()
    o_en = _pick(EN_TASK_OBJECTS)
    dl_expr, dl_val, dl_note = _dl_vi(sent)

    templates = [
        (f"Chào team,\n\n{name} ơi, submit {o_en} {dl_expr} nhé. Thanks!",
         _mk_title("Submit", o_en), name, dl_val, "VI text + EN verb/object"),
        (f"Hi {name}, nhờ bạn review cái {o_en} {dl_expr}. Cảm ơn nha.",
         _mk_title("Review", o_en), name, dl_val, "mixed greeting + VI deadline"),
        (f"@{name}: update {o_en} asap, deadline là {dl_expr}.",
         _mk_title("Update", o_en), name, dl_val, "@mention + mixed lang"),
        (f"Mọi người ơi, {name} handle {o_en} {dl_expr}. Let me know if any issues.",
         _mk_title("Handle", o_en), name, dl_val, "VI opener + EN closer"),
    ]
    text, title, assignee, dl, note = _pick(templates)
    return _sample(
        _id("mx"), "edge_mixed_lang", "gmail", "mixed", text,
        {"sent_at": sent, "sender": "team@company.com", "subject": "Task update"},
        {"tasks": [{"title": title, "assignee": assignee, "deadline": dl, "priority": None}], "conflicts": [], "missing_fields": []},
        note,
        edge_tags=["code_switching"],
    )


def gen_edge_noisy_long(i):
    """Long email with task buried in noise (signature, disclaimer, etc.)."""
    sent = _sent_at(i % 14)
    iv = _vn()
    name = _name(iv)
    v, o = _verb(iv), _obj(iv)
    dl_val = _dl(sent, random.choice([3, 5, 7]))
    days = (date.fromisoformat(dl_val) - date.fromisoformat(sent)).days

    noise_vi = (
        f"Chào team,\n\n"
        f"Cảm ơn mọi người đã tham gia buổi họp hôm qua. Mình tóm tắt lại một số điểm chính:\n\n"
        f"- Doanh thu Q1 tăng 15% so với cùng kỳ năm ngoái\n"
        f"- Chi phí marketing đã được tối ưu\n"
        f"- Nhóm R&D đang nghiên cứu tính năng mới\n\n"
        f"Về phần công việc, nhờ {name} {v} {o} trong {days} ngày tới nhé.\n\n"
        f"Ngoài ra, mình nhắc lại chính sách WFH: tối đa 2 ngày/tuần, cần báo trước 1 ngày.\n\n"
        f"---\n"
        f"Nguyễn Văn Manager\nGiám đốc dự án | Công ty ABC\nĐT: 0912-345-678\nEmail: manager@abc.vn"
    )
    noise_en = (
        f"Hi team,\n\n"
        f"Thanks for attending yesterday's meeting. Here's a quick recap:\n\n"
        f"- Q1 revenue up 15% YoY\n"
        f"- Marketing costs have been optimized\n"
        f"- R&D is exploring new features\n\n"
        f"Action item: {name}, please {v} the {o} within {days} days.\n\n"
        f"Also a reminder about WFH policy: max 2 days/week, notify 1 day in advance.\n\n"
        f"---\nJohn Manager\nProject Director | ABC Corp\nPhone: +1-555-0123\nEmail: john@abc.com\n\n"
        f"CONFIDENTIALITY NOTICE: This email is intended solely for the recipient. "
        f"If you received this in error, please delete it immediately."
    )
    text = noise_vi if iv else noise_en
    return _sample(
        _id("nl"), "edge_noisy_long", "gmail", "vi" if iv else "en", text,
        {"sent_at": sent, "sender": "manager@company.com", "subject": "Meeting recap + action item"},
        {"tasks": [{"title": _mk_title(v, o), "assignee": name, "deadline": dl_val, "priority": None}], "conflicts": [], "missing_fields": []},
        f"1 task buried in long email with signature, disclaimer, noise; dl=sent+{days}",
        edge_tags=["noisy", "long_text", "signature"],
    )


def gen_edge_forwarded(i):
    """Forwarded / reply chain emails."""
    sent = _sent_at(i % 14)
    iv = _vn()
    name = _name(iv)
    v, o = _verb(iv), _obj(iv)
    dl = _friday(sent)

    if iv:
        text = (
            f"---------- Forwarded message ----------\n"
            f"From: director@company.com\n"
            f"Date: {_sent_at((i % 14) - 1)}\n"
            f"Subject: Phân công\n\n"
            f"Nhờ {name} {v} {o} trước thứ Sáu.\n\n"
            f"---------- End forwarded ----------\n\n"
            f"FYI team, mọi người xem giúp nhé."
        )
    else:
        text = (
            f"---------- Forwarded message ----------\n"
            f"From: director@company.com\n"
            f"Date: {_sent_at((i % 14) - 1)}\n"
            f"Subject: Assignment\n\n"
            f"Please ask {name} to {v} the {o} by Friday.\n\n"
            f"---------- End forwarded ----------\n\n"
            f"FYI team, please take note."
        )
    return _sample(
        _id("fw"), "edge_forwarded", "gmail", "vi" if iv else "en", text,
        {"sent_at": sent, "sender": "forwarder@company.com", "subject": "Fwd: Assignment"},
        {"tasks": [{"title": _mk_title(v, o), "assignee": name, "deadline": dl, "priority": None}], "conflicts": [], "missing_fields": []},
        f"task in forwarded message body; dl=Friday {dl}",
        edge_tags=["forwarded", "nested_email"],
    )


def gen_edge_priority(i):
    """Emails with explicit priority keywords."""
    sent = _sent_at(i % 14)
    iv = _vn()
    name = _name(iv)
    v, o = _verb(iv), _obj(iv)
    dl = _dl(sent, random.choice([1, 2, 3]))

    vi_variants = [
        (f"[GẤP] {name} ơi, {v} {o} trước ngày mai. Rất gấp!", "high", "GẤP / Rất gấp"),
        (f"Ưu tiên cao: nhờ {name} {v} {o} trong 2 ngày.", "high", "Ưu tiên cao"),
        (f"Nhờ {name} {v} {o} trước thứ Sáu. Không gấp lắm, làm khi rảnh.", "low", "Không gấp lắm"),
        (f"URGENT: {name} {v} {o} ngay hôm nay nếu được.", "high", "URGENT"),
    ]
    en_variants = [
        (f"[URGENT] {name}, please {v} the {o} by tomorrow. This is critical!", "high", "URGENT / critical"),
        (f"High priority: {name}, {v} the {o} within 2 days.", "high", "High priority"),
        (f"{name}, please {v} the {o} by Friday. Low priority, no rush.", "low", "Low priority / no rush"),
        (f"CRITICAL: {name}, {v} the {o} today if possible.", "high", "CRITICAL"),
    ]

    text, prio, note = _pick(vi_variants if iv else en_variants)
    return _sample(
        _id("pr"), "edge_priority", "gmail", "vi" if iv else "en", text,
        {"sent_at": sent, "sender": "manager@company.com", "subject": "[Urgent]" if prio == "high" else "Task"},
        {"tasks": [{"title": _mk_title(v, o), "assignee": name, "deadline": dl, "priority": prio}], "conflicts": [], "missing_fields": []},
        f"explicit priority: {note}",
        edge_tags=["explicit_priority"],
    )


def gen_edge_tricky_negative(i):
    """Text that looks like a task but isn't — past tense, questions, signatures, conditionals."""
    sent = _sent_at(i % 14)
    iv = _vn()
    name = _name(iv)
    o = _obj(iv)

    vi_pool = [
        (f"{name} đã nộp {o} xong rồi ạ.", "past-tense completion"),
        (f"Mình đã hoàn thành review {o} hôm qua.", "self-completion past"),
        (f"Ai biết deadline {o} là khi nào không?", "question — not a task"),
        (f"{name} có cần hỗ trợ gì với {o} không?", "question offering help"),
        (f"Nếu có thời gian thì {name} xem qua {o}, nhưng không bắt buộc.", "optional / conditional"),
        (f"Báo cáo {o} đã được gửi cho khách hàng vào sáng nay.", "already-done report"),
        (f"Lưu ý: {o} chỉ cần làm khi phase 2 bắt đầu (chưa xác định).", "deferred — no action now"),
        (f"Nguyễn Văn An\nSenior Developer\nĐT: 0912-345-678\nEmail: an@company.com", "email signature — not a task"),
        (f"Mình nghĩ {o} nên được ưu tiên hơn, nhưng chưa quyết định.", "opinion — no assignment"),
        (f"Đính kèm: {o}.pdf (tham khảo)", "attachment reference — no action"),
    ]
    en_pool = [
        (f"{name} has already submitted the {o}.", "past-tense completion"),
        (f"I finished reviewing the {o} yesterday.", "self-completion past"),
        (f"Does anyone know when the {o} is due?", "question — not a task"),
        (f"Does {name} need help with the {o}?", "question offering help"),
        (f"If you have time, {name}, take a look at the {o} — not mandatory.", "optional / conditional"),
        (f"The {o} was sent to the client this morning.", "already-done report"),
        (f"Note: the {o} is only needed once phase 2 starts (TBD).", "deferred — no action now"),
        (f"John Smith\nSenior Developer\nPhone: +1-555-0123\nEmail: john@company.com", "email signature — not a task"),
        (f"I think the {o} should be prioritized, but no decision yet.", "opinion — no assignment"),
        (f"Attached: {o}.pdf (for reference)", "attachment reference — no action"),
    ]

    pool = vi_pool if iv else en_pool
    text, note = _pick(pool)
    return _sample(
        _id("tn"), "edge_tricky_negative", "gmail", "vi" if iv else "en", text,
        {"sent_at": sent, "sender": "colleague@company.com", "subject": "Re: update"},
        {"tasks": [], "conflicts": [], "missing_fields": []},
        f"Tricky negative: {note}",
        edge_tags=["tricky_negative", note.split(" — ")[0] if " — " in note else note],
    )


def gen_edge_special_format(i):
    """Tasks in table, checklist, or unusual formatting."""
    sent = _sent_at(i % 14)
    iv = _vn()
    names = _pick_n(VN_NAMES_FULL if iv else EN_NAMES, 2)
    objs = _pick_n(VN_TASK_OBJECTS if iv else EN_TASK_OBJECTS, 2)
    dl = _friday(sent)

    vi_templates = [
        (
            f"| STT | Người thực hiện | Công việc | Hạn |\n"
            f"|-----|-----------------|-----------|-----|\n"
            f"| 1   | {names[0]}      | {objs[0]} | {dl} |\n"
            f"| 2   | {names[1]}      | {objs[1]} | {dl} |",
            "markdown table"
        ),
        (
            f"Checklist sprint 14:\n\n"
            f"☐ {objs[0]} — {names[0]} — trước thứ Sáu\n"
            f"☐ {objs[1]} — {names[1]} — trước thứ Sáu\n"
            f"☑ Hoàn thành thiết kế UI (done)",
            "checklist with done item"
        ),
        (
            f"TODO:\n"
            f"* [{names[0]}] {objs[0]} (DL: thứ Sáu)\n"
            f"* [{names[1]}] {objs[1]} (DL: thứ Sáu)\n"
            f"* [DONE] Triển khai API endpoint",
            "custom bracket format"
        ),
    ]
    en_templates = [
        (
            f"| # | Assignee | Task | Due |\n"
            f"|---|----------|------|-----|\n"
            f"| 1 | {names[0]} | {objs[0]} | {dl} |\n"
            f"| 2 | {names[1]} | {objs[1]} | {dl} |",
            "markdown table"
        ),
        (
            f"Sprint 14 checklist:\n\n"
            f"☐ {objs[0]} — {names[0]} — by Friday\n"
            f"☐ {objs[1]} — {names[1]} — by Friday\n"
            f"☑ Complete UI design (done)",
            "checklist with done item"
        ),
        (
            f"TODO:\n"
            f"* [{names[0]}] {objs[0]} (due: Friday)\n"
            f"* [{names[1]}] {objs[1]} (due: Friday)\n"
            f"* [DONE] Deploy API endpoint",
            "custom bracket format"
        ),
    ]

    text, fmt_note = _pick(vi_templates if iv else en_templates)
    tasks = []
    for idx in range(2):
        t = objs[idx][0].upper() + objs[idx][1:] if objs[idx][0].islower() else objs[idx]
        tasks.append({"title": t, "assignee": names[idx], "deadline": dl, "priority": None})

    return _sample(
        _id("sf"), "edge_special_format", "drive", "vi" if iv else "en", text,
        {"sent_at": sent, "sender": None, "subject": None},
        {"tasks": tasks, "conflicts": [], "missing_fields": []},
        f"special format: {fmt_note}; 2 active tasks, ignore DONE items",
        edge_tags=["special_format", fmt_note],
    )


def gen_edge_nickname(i):
    """Tasks using nicknames, initials, or @mentions instead of full names."""
    sent = _sent_at(i % 14)
    iv = _vn()
    v, o = _verb(iv), _obj(iv)
    dl = _friday(sent)

    if iv:
        nick = _pick(VN_NICKNAMES)
        templates = [
            f"@{nick}: {v} {o} trước thứ Sáu nhé.",
            f"Bạn {nick} ơi, {v} {o} trước thứ Sáu.",
            f"{nick} — nhờ {v} {o} trước thứ Sáu. Thanks!",
        ]
    else:
        nick = _pick(EN_NICKNAMES)
        templates = [
            f"@{nick}: please {v} the {o} by Friday.",
            f"Hey {nick}, {v} the {o} by Friday pls.",
            f"{nick} — {v} the {o} by Friday. Thx!",
        ]
    text = _pick(templates)
    return _sample(
        _id("nn"), "edge_nickname", "gmail", "vi" if iv else "en", text,
        {"sent_at": sent, "sender": "colleague@company.com", "subject": "quick task"},
        {"tasks": [{"title": _mk_title(v, o), "assignee": nick, "deadline": dl, "priority": None}], "conflicts": [], "missing_fields": []},
        f"nickname/informal name: {nick}",
        edge_tags=["nickname", "informal_name"],
    )


# ===================================================================
# MAIN
# ===================================================================

CATEGORY_COUNTS = {
    "email_simple": 30,
    "email_multi_task": 25,
    "email_no_task": 25,
    "email_no_task_extra": 0,
    "email_ambiguous": 20,
    "doc_simple": 20,
    "doc_meeting_notes": 15,
    "conflict_deadline": 15,
    "conflict_assignee": 10,
    "missing_deadline": 10,
    "missing_assignee": 10,
    "edge_mixed_lang": 10,
    "edge_noisy_long": 10,
    "edge_forwarded": 8,
    "edge_priority": 10,
    "edge_tricky_negative": 15,
    "edge_special_format": 10,
    "edge_nickname": 7,
}

GENERATORS = {
    "email_simple": gen_email_simple,
    "email_multi_task": gen_email_multi_task,
    "email_no_task": gen_email_no_task,
    "email_ambiguous": gen_email_ambiguous,
    "doc_simple": gen_doc_simple,
    "doc_meeting_notes": gen_doc_meeting_notes,
    "conflict_deadline": gen_conflict_deadline,
    "conflict_assignee": gen_conflict_assignee,
    "missing_deadline": gen_missing_deadline,
    "missing_assignee": gen_missing_assignee,
    "edge_mixed_lang": gen_edge_mixed_lang,
    "edge_noisy_long": gen_edge_noisy_long,
    "edge_forwarded": gen_edge_forwarded,
    "edge_priority": gen_edge_priority,
    "edge_tricky_negative": gen_edge_tricky_negative,
    "edge_special_format": gen_edge_special_format,
    "edge_nickname": gen_edge_nickname,
}


def main():
    samples = []
    for cat, count in CATEGORY_COUNTS.items():
        if count == 0:
            continue
        gen = GENERATORS[cat]
        for idx in range(count):
            samples.append(gen(idx))

    random.shuffle(samples)
    OUT_PATH.write_text(json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated {len(samples)} samples → {OUT_PATH}")

    cats: dict[str, int] = {}
    langs: dict[str, int] = {}
    edge_count = 0
    for s in samples:
        cats[s["category"]] = cats.get(s["category"], 0) + 1
        langs[s["language"]] = langs.get(s["language"], 0) + 1
        if s.get("edge_tags"):
            edge_count += 1
    print("\nCategory distribution:")
    for cat, cnt in sorted(cats.items()):
        print(f"  {cat}: {cnt}")
    print(f"\nLanguage: {langs}")
    print(f"Edge-tagged samples: {edge_count}")
    print(f"Total: {sum(cats.values())}")


if __name__ == "__main__":
    main()
