from typing import Literal, TypedDict


class PipelineState(TypedDict, total=False):
    user_id: str
    access_token: str
    source_doc_id: str
    pipeline_run_id: str
    eval_sample_id: str  # set by tests/eval pipeline_runner for LangSmith correlation
    policy_version: str
    content_hash: str
    source_type: Literal["gmail", "drive", "upload"]
    raw_content: str | bytes

    cleaned_text: str
    metadata: dict  # optional: dedupe_group_id (Gmail thread / Drive file) for update-in-place on re-sync
    chunks: list[str]

    extracted_tasks: list[dict]
    normalized_tasks: list[dict]
    existing_tasks: list[dict]
    validated_tasks: list[dict]
    conflicts: list[dict]
    saved_task_ids: list[str]
    notifications_sent: list[dict]

    errors: list[str]
    should_stop: bool
