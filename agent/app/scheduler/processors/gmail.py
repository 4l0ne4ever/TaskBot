"""Gmail job processor — fetch messages, dedup, run LangGraph pipeline."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from app.db.session import AsyncSessionLocal
from app.mcp.gmail_client import GmailMCPClient
from app.models.pipeline_run import PipelineRun
from app.models.source_document import SourceDocument
from app.services.observability import record_pipeline_error
from app.services.sync_service import (
    _gmail_limit_for_profile,
    pull_recent_gmail_messages,
)

from .._runtime import (
    clear_progress,
    ensure_sync_state,
    logger,
    publish_progress,
    settings,
)
from ..auth import (
    flag_user_auth_revoked,
    is_auth_revoked_error,
    is_sync_disabled_for_auth,
    record_mcp_auth_outcome,
)
from ..pipeline_runner import (
    content_hash,
    find_existing_source_doc,
    invoke_pipeline,
    mark_run_failed,
    time_range_to_datetime,
)
from ..pressure import llm_pressure_snapshot, requeue_deferred_job

_FETCH_CONCURRENCY = 5


def parse_gmail_message(full: dict | str, msg: dict) -> dict | None:
    """Extract body, subject, sender, thread_id from a fetched Gmail message."""
    body = ""
    if isinstance(full, dict):
        body = full.get("body") or full.get("html") or full.get("snippet") or ""
    elif isinstance(full, str):
        body = full
    if not body:
        return None

    msg_id = msg.get("id") or msg.get("message_id") or ""
    thread_id = ""
    subject = ""
    sender = ""
    sent_at = ""
    if isinstance(full, dict):
        thread_id = full.get("threadId") or msg.get("threadId") or msg.get("thread_id") or msg_id
        headers = full.get("headers") or full.get("payload", {}).get("headers") or []
        if isinstance(headers, list):
            for h in headers:
                name = (h.get("name") or "").lower()
                if name == "subject":
                    subject = h.get("value", "")
                elif name == "from":
                    sender = h.get("value", "")
                elif name == "date":
                    sent_at = h.get("value", "")
        if not subject:
            subject = full.get("subject", "")
        if not sender:
            sender = full.get("from", "")
        if not sent_at:
            sent_at = full.get("date", "")
    if not thread_id:
        thread_id = msg.get("threadId") or msg.get("thread_id") or msg_id

    sent_at_iso = ""
    internal_date = ""
    if sent_at:
        try:
            sent_at_iso = parsedate_to_datetime(sent_at).astimezone(UTC).isoformat()
        except Exception:
            sent_at_iso = ""
    if isinstance(full, dict):
        internal_date = str(full.get("internalDate") or msg.get("internalDate") or "").strip()
    if not sent_at_iso and internal_date.isdigit():
        try:
            sent_at_iso = datetime.fromtimestamp(int(internal_date) / 1000, tz=UTC).isoformat()
        except Exception:
            sent_at_iso = ""

    return {
        "body": body,
        "thread_id": thread_id,
        "subject": subject,
        "sender": sender,
        "sent_at": sent_at_iso,
        "msg_id": msg_id,
    }


async def process_gmail_job(
    user_id: str,
    access_token: str,
    time_range: str = "1d",
    sync_profile: str = "balanced",
    raw_job: dict | None = None,
    folder: str = "inbox",
) -> None:
    # ``folder`` (Round 11, 2026-05-30): "inbox" (default, every user) or
    # "sent" (team-mode users only — see jobs.sync_all_users_gmail). Propagates
    # through pull_recent_gmail_messages → gmail_client to pick the Gmail
    # query, and is stamped onto SourceDocument's source_type so /tasks can
    # default-exclude sent rows.
    uid = uuid.UUID(user_id)
    profile_limit = _gmail_limit_for_profile(sync_profile)
    disabled = await is_sync_disabled_for_auth(user_id, "gmail")
    if disabled and str(disabled.get("reason")) == "mcp_auth_revoked":
        logger.info(
            "gmail sync: skipping user %s — auth_revoked since %s",
            user_id,
            disabled.get("since"),
        )
        await ensure_sync_state(
            uid,
            "gmail",
            "error",
            f"mcp_auth_revoked: reconnect Google account (since {disabled.get('since')})",
        )
        await publish_progress(
            user_id,
            "gmail",
            "error",
            "Google authorization was revoked — reconnect in Settings to resume sync",
        )
        return
    await ensure_sync_state(uid, "gmail", "running")
    await publish_progress(
        user_id,
        "gmail",
        "connecting",
        f"Connecting to Gmail (last {time_range}, profile={sync_profile}, cap={profile_limit})",
    )

    last_sync_at = time_range_to_datetime(time_range)
    error_msg: str | None = None
    try:
        messages = await pull_recent_gmail_messages(
            user_id=user_id,
            access_token=access_token,
            last_sync_at=last_sync_at,
            sync_profile=sync_profile,
            folder=folder,
        )
        if not messages:
            logger.info("gmail sync: no new messages for user %s", user_id)
            await publish_progress(user_id, "gmail", "done", "No new messages found")
            return

        total = len(messages)
        await publish_progress(user_id, "gmail", "fetching", f"Fetching {total} messages", 0, total)

        gmail = GmailMCPClient(access_token=access_token)
        sem = asyncio.Semaphore(_FETCH_CONCURRENCY)

        async def fetch_one(m: dict) -> tuple[dict, dict | str | None]:
            mid = m.get("id") or m.get("message_id") or ""
            if not mid:
                return m, None
            async with sem:
                try:
                    return m, await gmail.get_message(str(mid))
                except Exception:
                    logger.warning("gmail: failed to fetch message %s", mid)
                    return m, None

        fetched = await asyncio.gather(*(fetch_one(m) for m in messages))
        await publish_progress(user_id, "gmail", "processing", f"Processing {total} messages", 0, total)

        processed = 0
        skipped_dedup = 0
        failed_docs = 0
        (
            llm_pressure_high,
            pressure_ratio,
            pressure_sample_size,
            daily_quota_exhausted,
        ) = await llm_pressure_snapshot()
        max_docs_under_pressure = max(settings.llm_pressure_max_documents_per_job, 1)
        deferred = 0
        if daily_quota_exhausted:
            error_msg = (
                f"llm_daily_quota_exhausted: {pressure_ratio:.0%} rate-limited "
                f"(TPD/RPD) in last {pressure_sample_size} calls; sync will "
                f"retry after the next UTC day boundary"
            )
            logger.warning("gmail sync: %s (user=%s)", error_msg, user_id)
            await publish_progress(user_id, "gmail", "throttling", error_msg, 0, total)
            return
        if llm_pressure_high:
            await publish_progress(
                user_id,
                "gmail",
                "throttling",
                f"LLM pressure high ({pressure_ratio:.0%} in last {pressure_sample_size}); deferring after {max_docs_under_pressure} docs",
                0,
                total,
            )
        for idx, (msg, full) in enumerate(fetched):
            if full is None:
                continue
            parsed = parse_gmail_message(full, msg)
            if parsed is None:
                continue
            if llm_pressure_high and processed >= max_docs_under_pressure:
                deferred += 1
                continue

            body_html = parsed["body"]
            chash = content_hash(body_html if isinstance(body_html, str) else str(body_html))
            msg_ref = str(parsed["msg_id"])

            doc_id_val: uuid.UUID | None = None
            run_id_val: uuid.UUID | None = None
            skip_pipeline = False
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Dedup must be scoped to the *same* source_type — a
                    # self-sent email (Daily Digest TaskBot sends to the user)
                    # would otherwise land as 'gmail' first, then the sent
                    # pass would skip its 'gmail_sent' counterpart. Inbox and
                    # sent are distinct logical sources of the same message.
                    dedup_source_type = "gmail_sent" if folder == "sent" else "gmail"
                    existing = await find_existing_source_doc(
                        session, user_id=uid, source_type=dedup_source_type, source_ref=msg_ref
                    )
                    if existing is not None:
                        doc_id_val = existing.id
                        if existing.processed_at is not None:
                            skip_pipeline = True
                        else:
                            run_id_val = uuid.uuid4()
                            session.add(
                                PipelineRun(
                                    id=run_id_val,
                                    user_id=uid,
                                    source_doc_id=doc_id_val,
                                    status="running",
                                )
                            )
                    else:
                        doc_id_val = uuid.uuid4()
                        run_id_val = uuid.uuid4()
                        # Persist Gmail's parsed Date: / internalDate as
                        # received_at so the task-detail Source panel shows
                        # when the email arrived (not when TaskBot synced).
                        # Migration 0012. Empty string from parse_gmail_message
                        # means parsing failed — leave NULL.
                        sent_at_raw = parsed.get("sent_at") if isinstance(parsed, dict) else None
                        received_at_dt = None
                        if isinstance(sent_at_raw, str) and sent_at_raw:
                            try:
                                received_at_dt = datetime.fromisoformat(sent_at_raw)
                            except ValueError:
                                received_at_dt = None
                        doc_source_type = "gmail_sent" if folder == "sent" else "gmail"
                        doc = SourceDocument(
                            id=doc_id_val,
                            user_id=uid,
                            source_type=doc_source_type,
                            source_ref=msg_ref,
                            dedupe_group_id=str(parsed["thread_id"]),
                            content_hash=chash,
                            raw_text=body_html[:50_000] if isinstance(body_html, str) else None,
                            received_at=received_at_dt,
                        )
                        session.add(doc)
                        await session.flush()
                        session.add(
                            PipelineRun(
                                id=run_id_val,
                                user_id=uid,
                                source_doc_id=doc_id_val,
                                status="running",
                            )
                        )

            if skip_pipeline:
                skipped_dedup += 1
                logger.info(
                    "gmail sync: skip already-processed msg=%s doc=%s",
                    msg_ref,
                    doc_id_val,
                )
                continue

            doc_id = str(doc_id_val)
            run_id = str(run_id_val) if run_id_val is not None else ""

            processed += 1
            await publish_progress(user_id, "gmail", "extracting", f"Extracting {processed}/{total}", processed, total)

            state = {
                "user_id": user_id, "access_token": access_token,
                "source_doc_id": doc_id, "pipeline_run_id": run_id,
                # state.source_type stays "gmail" so parse_input/validate
                # treat sent and inbox docs identically (both are Gmail HTML
                # with the same headers structure). The folder distinction
                # is carried in metadata.folder and consumed only by
                # extract_tasks to pick the sent-context system prompt.
                "content_hash": chash, "source_type": "gmail", "raw_content": body_html,
                "metadata": {
                    "subject": parsed["subject"],
                    "sender": parsed["sender"],
                    "sent_at": parsed["sent_at"],
                    "sync_profile": sync_profile,
                    "dedupe_group_id": str(parsed["thread_id"]),
                    "folder": folder,
                },
            }
            try:
                await invoke_pipeline(state)
                logger.info("gmail pipeline ok: msg=%s doc=%s", parsed["msg_id"], doc_id)
            except Exception as exc:
                logger.exception("gmail pipeline failed: msg=%s", parsed["msg_id"])
                failed_docs += 1
                await mark_run_failed(run_id, error_msg=str(exc)[:500])
                record_pipeline_error(
                    source_type="gmail",
                    user_id=user_id,
                    error=f"doc={doc_id}: {str(exc)[:400]}",
                )
                err = str(exc).lower()
                if "429" in err or "rate limit" in err or "rate_limit" in err:
                    remaining = max(total - (idx + 1), 0)
                    deferred += remaining
                    await publish_progress(
                        user_id,
                        "gmail",
                        "throttling",
                        f"LLM rate-limited mid-run; deferred {remaining} remaining messages",
                        processed,
                        total,
                    )
                    break
            await asyncio.sleep(max(settings.llm_per_document_cooldown_seconds, 0.0))

        detail = f"Completed — processed {processed} messages"
        if skipped_dedup:
            detail = f"{detail}, skipped {skipped_dedup} already-processed"
        if deferred:
            detail = f"{detail}, deferred {deferred} due to LLM pressure"
            if raw_job is not None:
                asyncio.create_task(requeue_deferred_job(raw_job, deferred))
        if failed_docs and error_msg is None:
            error_msg = f"partial_failure: {failed_docs}/{total} documents failed"
        await publish_progress(user_id, "gmail", "done", detail, processed, total)
    except Exception as exc:
        logger.exception("gmail sync job failed for user %s", user_id)
        error_msg = str(exc)[:500]
        auth_error = is_auth_revoked_error(error_msg)
        record_pipeline_error(source_type="gmail", user_id=user_id, error=error_msg)
        if auth_error:
            await flag_user_auth_revoked(user_id, "gmail", error_msg)
        await publish_progress(user_id, "gmail", "error", str(exc)[:200])
    else:
        await record_mcp_auth_outcome(user_id, "gmail", auth_error=False)
    finally:
        if error_msg:
            await ensure_sync_state(uid, "gmail", "error", error_msg)
        else:
            await ensure_sync_state(uid, "gmail", "idle")
        await clear_progress(user_id, "gmail")
