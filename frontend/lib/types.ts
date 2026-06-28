export interface TaskDeadlineV2 {
  type: "exact" | "range" | "relative" | "none" | null;
  iso: string | null;
  start: string | null;
  end: string | null;
  text: string | null;
  resolved_from: string | null;
  confidence: number | null;
  source: string | null;
  is_ambiguous: boolean | null;
  suggested_iso?: string | null;
}

export interface TaskUncertainty {
  type: "ambiguous" | "missing" | "conflict" | null;
  reason: string | null;
}

export interface Task {
  id: string;
  title: string;
  description: string | null;
  assignee: string | null;
  deadline: string | null;
  // Round 13 (2026-05-31): "HH:MM:SS" when the source said a time, null
  // otherwise. UI renders "YYYY-MM-DD HH:MM" when set, "YYYY-MM-DD" when
  // not — date-only behaviour preserved exactly for legacy rows.
  deadline_time: string | null;
  deadline_v2: TaskDeadlineV2 | null;
  priority: string | null;
  uncertainty: TaskUncertainty | null;
  status: string;
  missing_fields: string[] | null;
  calendar_event_id: string | null;
  notification_sent: boolean;
  evidence_quote: string | null;
  confirmed_by: string | null;
  // Phase 4 (no-deadline UX): Google-Tasks-like tracking state. Backend
  // returns null for legacy rows; the Tracking UI treats null as "todo".
  progress_state: ProgressState | null;
  // Phase 6.6 (recurring events): active RRULE drives the Google Calendar
  // recurring event; recurrence_suggested is the LLM-detected rule pending
  // user confirm; recurrence_dismissed_at suppresses re-suggestion on
  // re-sync of the same task.
  recurrence_rule: string | null;
  recurrence_suggested: string | null;
  recurrence_dismissed_at: string | null;
  source_doc_id: string | null;
  source_type: string | null;
  created_at: string;
  updated_at: string;
}

// Phase 4 (no-deadline UX) — tracking state, kept narrow with a string
// literal so a typo in the UI fails at compile time.
export type ProgressState = "todo" | "in_progress" | "done";

export type ConflictScope =
  | "multi_source"
  | "thread_update"
  | "inter_doc"
  | "intra_batch";

export interface Conflict {
  id: string;
  conflict_type: string;
  description: string | null;
  source_a_ref: string | null;
  source_b_ref: string | null;
  task_ids: string[] | null;
  scope: ConflictScope | null;
  resolved: boolean;
  created_at: string;
}

export interface TaskSource {
  source_type: string;
  source_ref: string;
  excerpt: string | null;
  // When TaskBot synced the document — fallback only.
  created_at: string;
  // When the email/file was originally received (Gmail Date: header, parsed by
  // queue_consumer._parse_gmail_message and persisted by migration 0012).
  // Null for Drive sources until file modifiedTime is wired. UI prefers this
  // over created_at when set.
  received_at: string | null;
}

export type MergeableField = "title" | "description" | "assignee" | "deadline" | "priority";

export interface CalendarSyncInfo {
  status: "skipped" | "queued" | "failed";
  reason: string | null;
  message: string;
}

export interface ConflictMergeResult {
  merged_task_id: string;
  dismissed_task_id: string;
  calendar_sync: CalendarSyncInfo;
}

export interface SyncStateRow {
  id: string;
  source_type: string;
  last_sync_at: string | null;
  status: string;
  error_message: string | null;
}

export interface PipelineRunRow {
  id: string;
  source_doc_id: string | null;
  status: string;
  tasks_extracted: number;
  conflicts_found: number;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
}

export type AccountMode = "single" | "team";

export interface SettingsPayload {
  gmail_interval: number;
  drive_interval: number;
  sync_profile: "strict_work" | "balanced" | "broad";
  google_connected: boolean;
  // Round 11 (2026-05-30): controls visibility of the /team route and whether
  // the user's Gmail sent folder is also synced (for the Lead persona).
  // Default "single" from the backend matches every legacy user.
  mode: AccountMode;
}

export interface CalendarEvent {
  id: string;
  title: string;
  assignee: string | null;
  deadline: string | null;
  // ``deadline_time`` and ``recurrence_rule`` mirror the same fields on
  // ``Task``. The /calendar grid uses the rule to expand recurring events
  // into per-occurrence chips for the visible month.
  deadline_time?: string | null;
  recurrence_rule?: string | null;
  priority: string | null;
  status: string;
  calendar_event_id: string | null;
  source_doc_id: string | null;
  created_at: string;
  updated_at: string;
}

// --- Observability / Admin dashboard ---

export interface QualityMetrics {
  window: string | null; // null = lifetime, e.g. "30d" = rolling window
  total_tasks: number;
  by_status: Record<string, number>;
  by_confirmed_by: { system: number; user: number; none: number };
  crosstab: { status: string; confirmed_by: string | null; count: number }[];
  auto_confirm: {
    system_confirmed: number;
    currently_confirmed_auto: number;
    user_confirmed: number;
    superseded: number;
    need_review: number;
    auto_confirm_rate: number;
  };
  calibration: { ece: number; source: string; note: string };
}

export interface SyncHealthSource {
  source_type: string;
  status: string;
  last_sync_at: string | null;
  staleness_minutes: number | null;
  interval_minutes: number;
  is_stale: boolean;
  has_error: boolean;
  error_message: string | null;
}

export interface SyncHealth {
  overall: "healthy" | "stale" | "error";
  sources: SyncHealthSource[];
}

export interface TeamMemberStats {
  assignee: string | null;
  open: number;
  pending: number;
  confirmed: number;
  overdue: number;
  due_this_week: number;
  in_conflict: number;
  needs_review: number;
}

export interface TeamView {
  members: TeamMemberStats[];
  unassigned: TeamMemberStats;
}

export interface ObservabilitySummary {
  llm: {
    sample_size: number;
    error_rate: number;
    p50_ms: number;
    p95_ms: number;
    p99_ms: number;
    total_tokens: number;
    estimated_cost_total: number;
  };
  pipeline: { window_days: number; failed_runs: number; total_runs: number; error_rate: number };
  quality: { missing_deadline_tasks: number; total_tasks: number; missing_deadline_rate: number };
  targets: { p50_lt_ms: number; p95_lt_ms: number; p99_lt_ms: number };
}
