export interface Task {
  id: string;
  title: string;
  assignee: string | null;
  deadline: string | null;
  priority: string | null;
  status: string;
  missing_fields: string[] | null;
  calendar_event_id: string | null;
  notification_sent: boolean;
  source_doc_id: string | null;
  source_type: string | null;
  created_at: string;
  updated_at: string;
}

export interface Conflict {
  id: string;
  conflict_type: string;
  description: string | null;
  source_a_ref: string | null;
  source_b_ref: string | null;
  task_ids: string[] | null;
  resolved: boolean;
  created_at: string;
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

export interface SettingsPayload {
  gmail_interval: number;
  drive_interval: number;
  google_connected: boolean;
}

export interface CalendarEvent {
  id: string;
  title: string;
  assignee: string | null;
  deadline: string | null;
  priority: string | null;
  status: string;
  calendar_event_id: string | null;
  source_doc_id: string | null;
  created_at: string;
  updated_at: string;
}
