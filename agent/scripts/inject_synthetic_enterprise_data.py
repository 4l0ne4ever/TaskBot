"""Inject synthetic enterprise emails into the pipeline for thesis demo + metric capture.

Purpose:
    Dev data is FYI-noise (91% have no deadline/assignee). This script populates
    the system with ~28 realistic enterprise emails following the Anna persona
    (Frontend Tech Lead, team 8) so the auto-confirm rate is measurable on
    representative data.

    Each email is designed to be realistic and task-bearing: explicit deadlines,
    named assignees, cross-team coordination — the kind of content Anna actually
    processes.

Usage (from workspace root, with venv active):
    cd agent
    DATABASE_URL="postgresql+asyncpg://taskbot:taskbot@localhost:55432/taskbot" \\
    REDIS_URL="redis://127.0.0.1:56379" \\
    python scripts/inject_synthetic_enterprise_data.py

What it does:
    1. Inserts SourceDocument rows (source_type="gmail", synthetic message IDs)
    2. Pushes one pipeline:jobs entry per document (access_token="" → dispatch
       is skipped fail-safe; save_tasks + auto-confirm run normally)
    3. Prints queue depth so you can watch the agent drain it

Do NOT commit the generated task rows to any eval dataset — this is demo/thesis
data only. Document in thesis: "Demo uses representative synthetic enterprise
emails; quantitative eval uses labeled 250-sample dataset."
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid

# ---------------------------------------------------------------------------
# Synthetic enterprise email corpus — Anna persona, Frontend Tech Lead
# Mix: high-confidence (deadline + assignee → auto-confirm candidate),
#      medium (one field only → auto-confirm if uncertainty=NULL),
#      vague (no fields → stays pending, tests abstention)
# ---------------------------------------------------------------------------

EMAILS: list[dict] = [
    # ── High-confidence: explicit deadline + assignee ────────────────────────
    {
        "subject": "URGENT: Submit Q2 Performance Review by Friday",
        "body": (
            "Hi team,\n\n"
            "Reminder: all Q2 performance reviews must be submitted to HR by this Friday 30/05.\n"
            "Hương sẽ phụ trách tổng hợp kết quả và gửi lên board.\n"
            "Deadline cứng, không gia hạn được.\n\n"
            "Best,\nDirector Nguyễn"
        ),
    },
    {
        "subject": "Action Required: Update NDA with Techsoft before June 1",
        "body": (
            "Dear Legal Team,\n\n"
            "Please update the NDA contract with Techsoft Corp. per the revised terms "
            "discussed in Monday's call. Minh Đức sẽ review và ký trước ngày 01/06/2026.\n"
            "Gửi final draft cho client trước EOD 31/05.\n\n"
            "Thanks,\nCEO"
        ),
    },
    {
        "subject": "[P0] Critical payment gateway bug — fix by 5pm today",
        "body": (
            "Team,\n\n"
            "We have a P0 bug in the payment gateway causing checkout failures (~12% error rate).\n"
            "Huy Trần nhận việc này: root-cause + hotfix deployed to production by 17:00 hôm nay.\n"
            "Update trong Slack mỗi 30 phút.\n\n"
            "— CTO"
        ),
    },
    {
        "subject": "Board Demo Slides — cần xong trước thứ Năm 29/05",
        "body": (
            "Hương ơi,\n\n"
            "Cần chuẩn bị slides demo cho board meeting thứ Năm 29/05 lúc 14:00.\n"
            "Nội dung: Q2 roadmap, feature highlights, KPI dashboard.\n"
            "Gửi bản draft cho tôi review trước thứ Tư EOD.\n\n"
            "PM Lan"
        ),
    },
    {
        "subject": "Security audit of production APIs — deadline 30/05",
        "body": (
            "Hi Huy,\n\n"
            "As per compliance requirements, we need a full security audit of all production "
            "API endpoints before the end of this month (30/05/2026).\n"
            "Please run OWASP ZAP + manual review and submit the report by EOD 30/05.\n\n"
            "Regards,\nSecurity Lead"
        ),
    },
    {
        "subject": "Client invoice April — gửi trước 28/05",
        "body": (
            "Lan,\n\n"
            "Invoice tháng 4 cho client VinTech chưa được gửi. "
            "Em xử lý và gửi trước ngày 28/05 nhé — họ đang chờ để process payment.\n"
            "Attach PO #2026-047 vào email.\n\n"
            "Finance Manager"
        ),
    },
    {
        "subject": "Deploy hotfix v2.3.1 to production — today",
        "body": (
            "Minh,\n\n"
            "Hotfix v2.3.1 đã pass QA. Bạn deploy lên production environment hôm nay trước 16:00 nhé.\n"
            "Backup database trước khi deploy. Notify #ops-channel sau khi xong.\n\n"
            "Lead Dev"
        ),
    },
    {
        "subject": "Q3 Budget Approval — submit by June 1",
        "body": (
            "Lan,\n\n"
            "Finance team needs the Q3 budget proposal submitted by June 1st for board review.\n"
            "Include headcount plan, infrastructure costs, and marketing budget.\n"
            "Template in shared drive: /Finance/Q3-2026-Budget-Template.xlsx\n\n"
            "CFO"
        ),
    },
    {
        "subject": "Accessibility fixes for mobile app — sprint end 31/05",
        "body": (
            "Hi Huy,\n\n"
            "WCAG 2.1 audit flagged 7 accessibility issues in the mobile app (see attached report).\n"
            "Priority: fix P1 issues (contrast ratio, screen reader labels) before sprint end 31/05.\n"
            "P2 items can go in the next sprint.\n\n"
            "QA Lead"
        ),
    },
    {
        "subject": "Senior Developer hiring — decision by Tuesday 27/05",
        "body": (
            "Hương,\n\n"
            "We need to finalize the hiring decision for the Senior Frontend Dev role by Tuesday 27/05.\n"
            "3 candidates shortlisted — please review scorecards and confirm your recommendation.\n"
            "HR will send offer letter same day.\n\n"
            "HR Director"
        ),
    },
    {
        "subject": "Cloud migration Phase 2 — Minh và Huy complete by 15/06",
        "body": (
            "Team,\n\n"
            "Phase 2 of the AWS migration (moving remaining microservices to EKS) must complete by 15/06/2026.\n"
            "Minh Đức: migrate auth-service, user-service.\n"
            "Huy Trần: migrate notification-service, file-service.\n"
            "Weekly sync mỗi thứ Hai 9am.\n\n"
            "CTO"
        ),
    },
    {
        "subject": "Submit travel reimbursement — deadline 31/05",
        "body": (
            "Lan ơi,\n\n"
            "Chị cần submit travel reimbursement cho chuyến Hà Nội tuần trước trước ngày 31/05.\n"
            "Form ở đây: /HR/Travel-Reimbursement-Form-2026.pdf\n"
            "Attach receipts cho khách sạn và vé máy bay.\n\n"
            "Finance"
        ),
    },
    {
        "subject": "Update project timeline after scope change — EOW",
        "body": (
            "Hương,\n\n"
            "Client đã approve scope change request (thêm real-time notification module).\n"
            "Cần update project timeline và Gantt chart trước cuối tuần này.\n"
            "Share với client và internal team sau khi update.\n\n"
            "PM"
        ),
    },
    {
        "subject": "Deploy new features to staging — by Wednesday 28/05",
        "body": (
            "Minh,\n\n"
            "Features: dark mode, export to PDF, batch task operations — all code merged và tested.\n"
            "Deploy to staging environment by Wednesday 28/05 EOD for client UAT.\n"
            "Smoke test checklist in Confluence: /DevOps/Staging-Deploy-Checklist\n\n"
            "Lead Dev"
        ),
    },
    # ── Medium-confidence: one actionable field ──────────────────────────────
    {
        "subject": "Weekly status report to VinTech — every Friday",
        "body": (
            "Hương,\n\n"
            "Starting this Friday and every Friday going forward, please send a weekly status "
            "report to the VinTech account team (cc: pm@vintech.vn).\n"
            "Template: tasks completed, in-progress, blockers, next week plan.\n\n"
            "Account Manager"
        ),
    },
    {
        "subject": "Complete mandatory security training — deadline 05/06",
        "body": (
            "All staff,\n\n"
            "Annual security awareness training is mandatory for all employees. "
            "Complete by June 5, 2026 via the LMS portal: training.company.com\n"
            "Estimated time: 45 minutes. HR will send reminders for non-completions.\n\n"
            "IT Security"
        ),
    },
    {
        "subject": "API documentation update — sprint deadline",
        "body": (
            "Minh,\n\n"
            "The REST API docs for the new endpoints (task bulk operations, conflict resolution) "
            "are missing. Update Swagger + Confluence by end of current sprint.\n"
            "Link: /Confluence/API-Docs-v3\n\n"
            "Tech Lead"
        ),
    },
    {
        "subject": "Prepare technical spec for notification module — this week",
        "body": (
            "Huy,\n\n"
            "Cần technical specification cho real-time notification module trước cuối tuần này.\n"
            "Include: architecture diagram, WebSocket vs SSE decision, DB schema changes.\n"
            "Review session thứ Sáu 10am với team.\n\n"
            "Architect"
        ),
    },
    {
        "subject": "Database schema documentation — Minh phụ trách",
        "body": (
            "Minh,\n\n"
            "Schema docs chưa được update từ migration 0008. "
            "Em document các tables mới: entity_graph, pipeline_runs, conflicts.\n"
            "Format: dbdocs.io, link trong README.\n\n"
            "Lead Dev"
        ),
    },
    {
        "subject": "Onboarding new intern — Lan coordinate",
        "body": (
            "Lan,\n\n"
            "Intern mới (Phạm Văn Khoa) bắt đầu ngày 02/06.\n"
            "Em chuẩn bị: laptop setup, account access, onboarding schedule tuần đầu.\n"
            "Gửi welcome email trước ngày bắt đầu.\n\n"
            "HR"
        ),
    },
    # ── Multi-task emails (tests extraction of multiple tasks per email) ──────
    {
        "subject": "Sprint planning actions — week of 26/05",
        "body": (
            "Team recap từ sprint planning:\n\n"
            "1. Huy Trần: Fix login timeout bug — priority P1, done by thứ Ba 27/05\n"
            "2. Minh Đức: Implement export PDF feature — done by thứ Năm 29/05\n"
            "3. Hương: Review design mockups với client — thứ Tư 28/05 2pm\n"
            "4. Lan: Update sprint board và send status to stakeholders — EOD Monday\n\n"
            "Blockers → ping #dev-team Slack\n\n"
            "Scrum Master"
        ),
    },
    {
        "subject": "Client feedback actions from Wednesday call",
        "body": (
            "Hi team,\n\n"
            "Sau cuộc họp với TechGroup client hôm qua, các action items:\n\n"
            "- Hương sẽ revise UI/UX của dashboard theo feedback (deadline: 01/06)\n"
            "- Minh Đức fix data export bug họ report (deadline: 28/05, urgent)\n"
            "- Lan gửi revised quote cho Phase 3 (deadline: 29/05)\n\n"
            "Please confirm receipt.\n\n"
            "Account Manager"
        ),
    },
    # ── Ambiguous/vague (should NOT auto-confirm — test abstention) ───────────
    {
        "subject": "FYI: Office closed on 02/06 (public holiday)",
        "body": (
            "Team,\n\n"
            "Nhắc nhở: văn phòng đóng cửa ngày 02/06/2026 (Ngày Quốc tế Thiếu nhi).\n"
            "Work from home nếu cần thiết. Không có meetings được lên lịch ngày này.\n\n"
            "Admin"
        ),
    },
    {
        "subject": "Interesting article on AI in enterprise software",
        "body": (
            "Sharing this article that's relevant to what we're building:\n"
            "https://example.com/ai-enterprise-2026\n\n"
            "Some good points about context-aware task extraction. "
            "Might inform our roadmap discussion next quarter.\n\n"
            "CTO"
        ),
    },
    {
        "subject": "Team lunch this Friday — poll for restaurant",
        "body": (
            "Hi everyone,\n\n"
            "Chúng ta có team lunch thứ Sáu để celebrate Q2 milestone!\n"
            "Vote cho nhà hàng yêu thích: poll.company.com/team-lunch-q2\n"
            "Budget: 300k/người. RSVP by Thursday.\n\n"
            "HR"
        ),
    },
    {
        "subject": "Reminder: update your LinkedIn profile",
        "body": (
            "Hi team,\n\n"
            "As part of our employer branding initiative, please update your LinkedIn profile "
            "to reflect your current role and add the company page.\n"
            "No hard deadline — whenever you have 10 minutes.\n\n"
            "Marketing"
        ),
    },
    {
        "subject": "Meeting notes: Q2 retrospective 23/05",
        "body": (
            "Notes từ Q2 retrospective:\n\n"
            "WENT WELL:\n- Ship velocity improved 20%\n- Zero production incidents\n\n"
            "IMPROVE:\n- Code review turnaround time\n- Documentation lag\n- Onboarding process\n\n"
            "ACTIONS: To be discussed and assigned in next sprint planning.\n\n"
            "Scrum Master"
        ),
    },
    {
        "subject": "Server maintenance notification",
        "body": (
            "Dear users,\n\n"
            "Scheduled maintenance window: Sunday 01/06/2026, 2am-4am.\n"
            "Services will be unavailable during this window.\n"
            "Please save your work before 2am.\n\n"
            "IT Operations"
        ),
    },
]


def _run_one(state: dict) -> dict:
    """Run the LangGraph pipeline synchronously in a dedicated thread (matches
    the queue consumer's _run_pipeline_in_thread pattern)."""
    from app.pipeline.graph import pipeline
    from app.pipeline.llm import collect_provenance
    with collect_provenance():
        return pipeline.invoke(state)


async def main() -> None:
    import concurrent.futures
    from sqlalchemy import select
    from app.db.session import AsyncSessionLocal
    from app.models.pipeline_run import PipelineRun
    from app.models.source_document import SourceDocument

    user_id = uuid.UUID("2f277bfc-9c90-4f1e-a713-7256ce0be2e8")  # sh1rohasbeencursed@gmail.com

    print(f"Processing {len(EMAILS)} synthetic enterprise emails for user {user_id}")
    print("=" * 60)

    # Step 1 — insert SourceDocuments for any emails not yet in DB
    doc_records: list[tuple[str, str, str]] = []  # (doc_id, raw_text, subject)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            for i, email in enumerate(EMAILS):
                raw = f"Subject: {email['subject']}\n\n{email['body']}"
                content_hash = hashlib.sha256(raw.encode()).hexdigest()
                source_ref = f"synth-{content_hash[:16]}"

                # Skip if already inserted (idempotent re-runs)
                existing = (await session.execute(
                    select(SourceDocument).where(
                        SourceDocument.user_id == user_id,
                        SourceDocument.source_ref == source_ref,
                    )
                )).scalar_one_or_none()

                if existing is not None:
                    doc_id = str(existing.id)
                    if existing.processed_at is not None:
                        print(f"  [{i+1:02d}] SKIP (already processed) {email['subject'][:55]}")
                        continue
                    print(f"  [{i+1:02d}] RESUME {email['subject'][:55]}")
                else:
                    doc_id = str(uuid.uuid4())
                    doc = SourceDocument(
                        id=uuid.UUID(doc_id),
                        user_id=user_id,
                        source_type="gmail",
                        source_ref=source_ref,
                        content_hash=content_hash,
                        raw_text=raw,
                    )
                    session.add(doc)
                    print(f"  [{i+1:02d}] NEW    {email['subject'][:55]}")

                doc_records.append((doc_id, raw, email["subject"]))

    if not doc_records:
        print("\nAll documents already processed. Nothing to do.")
        return

    print(f"\nRunning pipeline on {len(doc_records)} documents (direct invoke, no queue)...")
    print("Each document runs the full LangGraph pipeline: parse→extract→normalize→validate→save→dispatch")
    print("-" * 60)

    # Step 2 — invoke pipeline for each doc, one at a time (rate-limit friendly)
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    ok = err = 0
    for i, (doc_id, raw_text, subject) in enumerate(doc_records):
        run_id = str(uuid.uuid4())

        # Create PipelineRun record before invoking
        async with AsyncSessionLocal() as session:
            async with session.begin():
                session.add(PipelineRun(
                    id=uuid.UUID(run_id),
                    user_id=user_id,
                    source_doc_id=uuid.UUID(doc_id),
                    status="running",
                ))

        state = {
            "user_id": str(user_id),
            "access_token": "",           # dispatch_notifications skips (fail-safe)
            "source_doc_id": doc_id,
            "pipeline_run_id": run_id,
            "content_hash": hashlib.sha256(raw_text.encode()).hexdigest(),
            "source_type": "gmail",
            "raw_content": raw_text,
            "metadata": {
                "subject": subject,
                "sender": "enterprise-demo@company.com",
                "sent_at": "2026-05-21",
            },
        }
        try:
            result = await asyncio.get_event_loop().run_in_executor(executor, _run_one, state)
            n_tasks = len(result.get("saved_task_ids", []))
            errors = result.get("errors", [])
            status = "✓" if not errors else "⚠"
            print(f"  [{i+1:02d}] {status} +{n_tasks} tasks  {subject[:50]}")
            if errors:
                for e in errors[:2]:
                    print(f"        ↳ {str(e)[:100]}")
            ok += 1
        except Exception as exc:
            print(f"  [{i+1:02d}] ✗ FAILED  {subject[:50]}")
            print(f"        ↳ {str(exc)[:120]}")
            err += 1

    executor.shutdown(wait=False)

    print(f"\n{'='*60}")
    print(f"Done: {ok} ok, {err} errors")
    print("\nAuto-confirm rate on synthetic data:")
    print(
        "docker compose exec postgres psql -U taskbot taskbot -c \"\n"
        "SELECT\n"
        "  COUNT(*) FILTER (WHERE confirmed_by = 'system') AS auto_confirmed,\n"
        "  COUNT(*) FILTER (WHERE confirmed_by IS NULL AND status = 'pending') AS need_review,\n"
        "  COUNT(*) AS total_tasks,\n"
        "  ROUND(100.0 * COUNT(*) FILTER (WHERE confirmed_by = 'system') / NULLIF(COUNT(*),0), 1) || '%' AS auto_pct\n"
        "FROM tasks\n"
        "WHERE user_id = '2f277bfc-9c90-4f1e-a713-7256ce0be2e8'\n"
        "  AND created_at > NOW() - INTERVAL '30 minutes';\n"
        "\""
    )


if __name__ == "__main__":
    asyncio.run(main())
