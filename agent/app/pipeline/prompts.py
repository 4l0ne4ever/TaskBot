EXTRACTION_SYSTEM_V1 = """You are a task extraction assistant.
Identify explicit work tasks and action items from text.
Return JSON only.
"""

EXTRACTION_USER_V1 = """Extract all tasks from this text.

Return a JSON array. Each item must contain:
- "title": concise task description
- "assignee_raw": person name/email exactly as written, or null
- "deadline_raw": deadline phrase exactly as written, or null
- "priority_raw": priority phrase exactly as written, or null

Text:
{text}

Metadata:
- Source: {source_type}
- Sender: {sender}
- Date: {sent_at}

JSON array only.
"""

EXTRACTION_RETRY_HINT_V1 = (
    "Look carefully for any requests, assignments, or action items that imply future work."
)

NORMALIZATION_USER_V1 = """Normalize the task information below.

Return a JSON array with the SAME number of items as input.
For each item include:
- "title": keep exactly as input
- "assignee": normalized assignee name or null
- "deadline": ISO date YYYY-MM-DD or null
- "priority": one of high/medium/low/null

Reference date: {reference_date}
Tasks:
{tasks_json}

JSON array only.
"""

CONFLICT_USER_V1 = """Compare these two tasks and detect if there is a conflict.

Task A (new):
{task_a_json}

Task B (existing):
{task_b_json}

Return JSON object:
- "conflict_type": "deadline_conflict" | "assignee_conflict" | "no_conflict"
- "description": short reason or null

Rules:
- deadline_conflict: same deliverable but different explicit deadlines
- assignee_conflict: same deliverable but mutually-exclusive assignees
- otherwise no_conflict

JSON only.
"""
