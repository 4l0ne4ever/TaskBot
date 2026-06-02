import { API_BASE_URL } from "./config";
import { getAuthToken } from "./auth";
import type {
  CalendarEvent,
  Conflict,
  ConflictMergeResult,
  ConflictScope,
  MergeableField,
  ObservabilitySummary,
  PipelineRunRow,
  QualityMetrics,
  SettingsPayload,
  SyncHealth,
  SyncStateRow,
  Task,
  TaskSource,
  TeamView,
} from "./types";

export type ConflictSort = "priority" | "created_at";

async function parseError(res: Response): Promise<string> {
  const body = await res.json().catch(() => null);
  if (body && typeof body === "object" && "detail" in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (d && typeof d === "object" && "message" in d) {
      return String((d as { message: string }).message);
    }
  }
  return `HTTP ${res.status}`;
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getAuthToken();
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });

  if (!res.ok) {
    throw new Error(await parseError(res));
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

// Same-origin fetch for the Next.js observability proxy (app/api/observability).
// The proxy injects the server-only internal token; here we only forward the
// user's JWT. Path is relative (same origin), not the backend base URL.
async function proxyFetch<T>(path: string): Promise<T> {
  const token = getAuthToken();
  const res = await fetch(path, {
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  if (!res.ok) {
    throw new Error(await parseError(res));
  }
  return res.json() as Promise<T>;
}

async function apiFetchForm<T>(path: string, form: FormData): Promise<T> {
  const token = getAuthToken();
  const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
  const res = await fetch(`${API_BASE_URL}${path}`, { method: "POST", body: form, headers });
  if (!res.ok) {
    throw new Error(await parseError(res));
  }
  return res.json() as Promise<T>;
}

function tasksQuery(params: {
  status?: string;
  source?: string;
  missing?: string;
  priority?: string;
  sort?: string;
  limit?: number;
  offset?: number;
}) {
  const q = new URLSearchParams();
  if (params.status) q.set("status", params.status);
  if (params.source) q.set("source", params.source);
  if (params.missing) q.set("missing", params.missing);
  if (params.priority) q.set("priority", params.priority);
  if (params.sort) q.set("sort", params.sort);
  if (params.limit != null) q.set("limit", String(params.limit));
  if (params.offset != null) q.set("offset", String(params.offset));
  const s = q.toString();
  return s ? `?${s}` : "";
}

export type TaskListResult = { tasks: Task[]; total: number };

async function apiFetchList<T>(path: string, options?: RequestInit): Promise<{ data: T; total: number }> {
  const token = getAuthToken();
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });

  if (!res.ok) {
    throw new Error(await parseError(res));
  }

  const totalHeader = res.headers.get("X-Total-Count");
  const data = (await res.json()) as T;
  let total = totalHeader != null && totalHeader !== "" ? Number(totalHeader) : NaN;
  if (!Number.isFinite(total) || total < 0) {
    // Header unreadable (e.g. CORS) — infer from page fill so Next still works.
    const len = Array.isArray(data) ? data.length : 0;
    const limitMatch = /[?&]limit=(\d+)/.exec(path);
    const offsetMatch = /[?&]offset=(\d+)/.exec(path);
    const limit = limitMatch ? Number(limitMatch[1]) : len;
    const offset = offsetMatch ? Number(offsetMatch[1]) : 0;
    total = len < limit ? offset + len : offset + limit + 1;
  }
  return { data, total };
}

export const api = {
  auth: {
    me: () => apiFetch<{ id: string; email: string }>("/auth/me"),
    logout: () => apiFetch<{ message: string }>("/auth/logout", { method: "POST" }),
  },
  tasks: {
    list: async (params?: { status?: string; source?: string; missing?: string; priority?: string; sort?: string; limit?: number; offset?: number }) => {
      const { data, total } = await apiFetchList<Task[]>(`/tasks${tasksQuery(params ?? {})}`);
      return { tasks: data, total };
    },
    get: (id: string) => apiFetch<Task>(`/tasks/${id}`),
    update: (
      id: string,
      data: Partial<
        Pick<
          Task,
          "title" | "description" | "assignee" | "deadline" | "deadline_time" | "deadline_v2" | "priority" | "uncertainty" | "status" | "progress_state"
        >
      >,
    ) =>
      apiFetch<Task>(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    delete: (id: string) => apiFetch<{ deleted: string; calendar_event_id: string }>(`/tasks/${id}`, { method: "DELETE" }),
    source: (id: string) => apiFetch<TaskSource>(`/tasks/${id}/source`),
    sourceByRef: (ref: string) => apiFetch<TaskSource>(`/tasks/source-by-ref?ref=${encodeURIComponent(ref)}`),
    deleteAll: (status?: string) => {
      const q = status ? `?status=${status}` : "";
      return apiFetch<{ deleted: number }>(`/tasks${q}`, { method: "DELETE" });
    },
    team: () => apiFetch<TeamView>("/tasks/team"),
  },
  conflicts: {
    list: (params: {
      resolved?: boolean;
      scope?: ConflictScope;
      sort?: ConflictSort;
      limit?: number;
      offset?: number;
    } = {}) => {
      const q = new URLSearchParams();
      if (params.resolved !== undefined) q.set("resolved", String(params.resolved));
      if (params.scope) q.set("scope", params.scope);
      if (params.sort) q.set("sort", params.sort);
      q.set("limit", String(params.limit ?? 50));
      q.set("offset", String(params.offset ?? 0));
      return apiFetch<Conflict[]>(`/tasks/conflicts?${q.toString()}`);
    },
    resolve: (id: string, resolution: "accept_a" | "accept_b" | "dismiss") =>
      apiFetch<Conflict>(`/tasks/conflicts/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ resolution }),
      }),
    merge: (id: string, fields: MergeableField[]) =>
      apiFetch<ConflictMergeResult>(`/tasks/conflicts/${id}/merge`, {
        method: "POST",
        body: JSON.stringify({ fields }),
      }),
    dismissAll: () => apiFetch<{ dismissed: number }>("/tasks/conflicts/dismiss-all", { method: "POST" }),
  },
  sync: {
    status: () => apiFetch<SyncStateRow[]>("/sync/status"),
    trigger: (source: "gmail" | "drive", timeRange: string = "1d") =>
      apiFetch<{ status: string; source: string }>(`/sync/trigger?source=${source}&time_range=${timeRange}`, { method: "POST" }),
    clear: () => apiFetch<{ status: string }>("/sync/clear", { method: "POST" }),
    history: (limit = 20, offset = 0) => apiFetch<PipelineRunRow[]>(`/sync/history?limit=${limit}&offset=${offset}`),
    deleteHistory: (status?: string) => {
      const q = status ? `?status=${status}` : "";
      return apiFetch<{ deleted: number }>(`/sync/history${q}`, { method: "DELETE" });
    },
    progress: (source: "gmail" | "drive") =>
      apiFetch<{ active: boolean; step: string; detail: string; current: number; total: number }>(`/sync/progress?source=${source}`),
  },
  settings: {
    get: () => apiFetch<SettingsPayload>("/settings"),
    patch: (body: {
      gmail_interval?: number;
      drive_interval?: number;
      sync_profile?: "strict_work" | "balanced" | "broad";
      mode?: "single" | "team";
    }) =>
      apiFetch<SettingsPayload>("/settings", { method: "PATCH", body: JSON.stringify(body) }),
    disconnect: () => apiFetch<{ message: string }>("/settings/disconnect", { method: "POST" }),
  },
  calendar: {
    events: (start?: string, end?: string) => {
      const q = new URLSearchParams();
      if (start) q.set("start", start);
      if (end) q.set("end", end);
      const s = q.toString();
      return apiFetch<CalendarEvent[]>(`/calendar/events${s ? `?${s}` : ""}`);
    },
    create: (data: { title: string; deadline: string; assignee?: string; priority?: string }) =>
      apiFetch<CalendarEvent>("/calendar/events", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: Partial<Pick<CalendarEvent, "title" | "assignee" | "deadline" | "priority" | "status">>) =>
      apiFetch<CalendarEvent>(`/calendar/events/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    delete: (id: string) => apiFetch<{ deleted: string }>(`/calendar/events/${id}`, { method: "DELETE" }),
  },
  upload: {
    file: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return apiFetchForm<{ upload_id: string; status: string }>("/upload", form);
    },
    status: (uploadId: string) =>
      apiFetch<{
        upload_id: string;
        status: string;
        // Round 14 (2026-05-31): when status === "done", backend also returns
        // the extracted count + a small preview list so the upload UI can
        // show what was actually created instead of leaving the user
        // staring at a "Done" checkmark with no result feedback.
        extracted_count?: number;
        extracted_tasks?: { id: string; title: string }[];
      }>(`/upload/${uploadId}/status`),
  },
  digest: {
    send: () =>
      apiFetch<{ status: string; message: string; reason?: string }>("/digest/send", {
        method: "POST",
      }),
  },
  observability: {
    quality: (window?: string) =>
      proxyFetch<QualityMetrics>(
        `/api/observability/quality${window ? `?window=${encodeURIComponent(window)}` : ""}`,
      ),
    syncHealth: () => proxyFetch<SyncHealth>("/api/observability/sync-health"),
    summary: () => proxyFetch<ObservabilitySummary>("/api/observability/summary"),
  },
};
