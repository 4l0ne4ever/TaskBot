import { API_BASE_URL } from "./config";
import { getAuthToken } from "./auth";
import type { CalendarEvent, Conflict, PipelineRunRow, SettingsPayload, SyncStateRow, Task } from "./types";

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
  sort?: string;
  limit?: number;
  offset?: number;
}) {
  const q = new URLSearchParams();
  if (params.status) q.set("status", params.status);
  if (params.source) q.set("source", params.source);
  if (params.sort) q.set("sort", params.sort);
  if (params.limit != null) q.set("limit", String(params.limit));
  if (params.offset != null) q.set("offset", String(params.offset));
  const s = q.toString();
  return s ? `?${s}` : "";
}

export const api = {
  auth: {
    me: () => apiFetch<{ id: string; email: string }>("/auth/me"),
    logout: () => apiFetch<{ message: string }>("/auth/logout", { method: "POST" }),
  },
  tasks: {
    list: (params?: { status?: string; source?: string; sort?: string; limit?: number; offset?: number }) =>
      apiFetch<Task[]>(`/tasks${tasksQuery(params ?? {})}`),
    get: (id: string) => apiFetch<Task>(`/tasks/${id}`),
    update: (
      id: string,
      data: Partial<
        Pick<
          Task,
          "title" | "description" | "assignee" | "deadline" | "deadline_v2" | "priority" | "uncertainty" | "status"
        >
      >,
    ) =>
      apiFetch<Task>(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    delete: (id: string) => apiFetch<{ deleted: string; calendar_event_id: string }>(`/tasks/${id}`, { method: "DELETE" }),
    deleteAll: (status?: string) => {
      const q = status ? `?status=${status}` : "";
      return apiFetch<{ deleted: number }>(`/tasks${q}`, { method: "DELETE" });
    },
  },
  conflicts: {
    list: (resolved?: boolean, limit = 50, offset = 0) => {
      const q = new URLSearchParams();
      if (resolved !== undefined) q.set("resolved", String(resolved));
      q.set("limit", String(limit));
      q.set("offset", String(offset));
      return apiFetch<Conflict[]>(`/tasks/conflicts?${q.toString()}`);
    },
    resolve: (id: string, resolution: "accept_a" | "accept_b" | "dismiss") =>
      apiFetch<Conflict>(`/tasks/conflicts/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ resolution }),
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
    patch: (body: { gmail_interval?: number; drive_interval?: number; sync_profile?: "strict_work" | "balanced" | "broad" }) =>
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
      apiFetch<{ upload_id: string; status: string }>(`/upload/${uploadId}/status`),
  },
};
