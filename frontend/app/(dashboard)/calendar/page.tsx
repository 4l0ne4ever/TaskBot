"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import type { CalendarEvent } from "@/lib/types";
import { cn } from "@/lib/utils";

function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

function endOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth() + 1, 0);
}

function fmt(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function fmtMonthYear(d: Date): string {
  return d.toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function priorityColor(p: string | null) {
  if (p === "high") return "bg-red-500/20 text-red-600 dark:text-red-300 border-red-500/30";
  if (p === "medium") return "bg-amber-500/20 text-amber-600 dark:text-amber-300 border-amber-500/30";
  return "bg-emerald-500/20 text-emerald-600 dark:text-emerald-300 border-emerald-500/30";
}

function statusIcon(s: string) {
  if (s === "confirmed") return "✓";
  if (s === "dismissed") return "✕";
  return "○";
}

interface EventModalProps {
  event: CalendarEvent | null;
  date: string;
  onClose: () => void;
  onSave: () => void;
}

function EventModal({ event, date, onClose, onSave }: EventModalProps) {
  const [title, setTitle] = useState(event?.title ?? "");
  const [assignee, setAssignee] = useState(event?.assignee ?? "");
  const [deadline, setDeadline] = useState(event?.deadline ?? date);
  const [priority, setPriority] = useState(event?.priority ?? "medium");
  const [status, setStatus] = useState(event?.status ?? "pending");
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    if (!title.trim()) {
      toast.error("Title is required");
      return;
    }
    setSaving(true);
    try {
      if (event) {
        await api.calendar.update(event.id, { title, assignee: assignee || null, deadline, priority, status });
        toast.success("Event updated");
      } else {
        await api.calendar.create({ title, deadline, assignee: assignee || undefined, priority });
        toast.success("Event created");
      }
      onSave();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!event) return;
    setSaving(true);
    try {
      await api.calendar.delete(event.id);
      toast.success("Event deleted");
      onSave();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to delete");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-[var(--surface)] border border-[var(--border)] rounded-xl shadow-2xl w-full max-w-md p-6 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold">{event ? "Edit Event" : "New Event"}</h2>

        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-[var(--muted)] mb-1">Title</label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
              placeholder="Task title"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-[var(--muted)] mb-1">Deadline</label>
              <input
                type="date"
                value={deadline}
                onChange={(e) => setDeadline(e.target.value)}
                className="w-full bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-[var(--muted)] mb-1">Priority</label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                className="w-full bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
              >
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-[var(--muted)] mb-1">Assignee</label>
            <input
              value={assignee}
              onChange={(e) => setAssignee(e.target.value)}
              className="w-full bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
              placeholder="Optional"
            />
          </div>
          {event && (
            <div>
              <label className="block text-xs font-medium text-[var(--muted)] mb-1">Status</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
              >
                <option value="pending">Pending</option>
                <option value="confirmed">Confirmed</option>
                <option value="dismissed">Dismissed</option>
              </select>
            </div>
          )}
        </div>

        <div className="flex items-center justify-between pt-2">
          <div>
            {event && (
              <button
                type="button"
                onClick={() => void handleDelete()}
                disabled={saving}
                className="text-sm text-[var(--danger)] hover:text-red-400 transition-colors disabled:opacity-50"
              >
                Delete
              </button>
            )}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg border border-[var(--border)] text-sm hover:bg-[var(--card-hover)] transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={saving}
              className="px-4 py-2 rounded-lg bg-[var(--accent)] text-white text-sm hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {saving ? "Saving..." : event ? "Update" : "Create"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function CalendarPage() {
  const [current, setCurrent] = useState(() => startOfMonth(new Date()));
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalDate, setModalDate] = useState<string | null>(null);
  const [modalEvent, setModalEvent] = useState<CalendarEvent | null>(null);
  const [selectedDate, setSelectedDate] = useState<string>(fmt(new Date()));

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const s = fmt(startOfMonth(current));
      const e = fmt(endOfMonth(current));
      const data = await api.calendar.events(s, e);
      setEvents(data);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to load events");
    } finally {
      setLoading(false);
    }
  }, [current]);

  useEffect(() => {
    void load();
  }, [load]);

  const eventsByDate = useMemo(() => {
    const map: Record<string, CalendarEvent[]> = {};
    for (const ev of events) {
      if (ev.deadline) {
        (map[ev.deadline] ??= []).push(ev);
      }
    }
    return map;
  }, [events]);

  const calendarDays = useMemo(() => {
    const start = startOfMonth(current);
    const end = endOfMonth(current);
    let dayOfWeek = start.getDay();
    dayOfWeek = dayOfWeek === 0 ? 6 : dayOfWeek - 1;

    const days: { date: Date; inMonth: boolean }[] = [];
    for (let i = dayOfWeek - 1; i >= 0; i--) {
      const d = new Date(start);
      d.setDate(d.getDate() - i - 1);
      days.push({ date: d, inMonth: false });
    }
    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      days.push({ date: new Date(d), inMonth: true });
    }
    const remaining = 7 - (days.length % 7);
    if (remaining < 7) {
      for (let i = 1; i <= remaining; i++) {
        const d = new Date(end);
        d.setDate(d.getDate() + i);
        days.push({ date: d, inMonth: false });
      }
    }
    return days;
  }, [current]);

  const today = fmt(new Date());

  function prev() {
    setCurrent((c) => new Date(c.getFullYear(), c.getMonth() - 1, 1));
  }
  function next() {
    setCurrent((c) => new Date(c.getFullYear(), c.getMonth() + 1, 1));
  }
  function goToday() {
    setCurrent(startOfMonth(new Date()));
  }

  function openCreate(dateStr: string) {
    setModalEvent(null);
    setModalDate(dateStr);
  }
  function openEdit(ev: CalendarEvent) {
    setModalEvent(ev);
    setModalDate(ev.deadline ?? fmt(new Date()));
  }
  function closeModal() {
    setModalEvent(null);
    setModalDate(null);
  }
  function afterSave() {
    closeModal();
    void load();
  }

  const upcomingDeadlines = useMemo(() => {
    const todayStr = fmt(new Date());
    return events
      .filter((e) => e.deadline && e.deadline >= todayStr && e.status !== "dismissed")
      .sort((a, b) => (a.deadline ?? "").localeCompare(b.deadline ?? ""))
      .slice(0, 8);
  }, [events]);

  const selectedDayEvents = useMemo(
    () =>
      (eventsByDate[selectedDate] ?? []).slice().sort((a, b) => {
        return (a.title ?? "").localeCompare(b.title ?? "");
      }),
    [eventsByDate, selectedDate],
  );

  const selectedDateForGoogle = useMemo(() => {
    const [y, m, d] = selectedDate.split("-");
    return `${y}/${m}/${d}`;
  }, [selectedDate]);

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button type="button" onClick={prev} className="p-2 rounded-lg hover:bg-[var(--card-hover)] transition-colors">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <h2 className="text-lg font-semibold min-w-[200px] text-center">{fmtMonthYear(current)}</h2>
          <button type="button" onClick={next} className="p-2 rounded-lg hover:bg-[var(--card-hover)] transition-colors">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </button>
          <button type="button" onClick={goToday} className="ml-2 text-xs px-3 py-1.5 rounded-lg border border-[var(--border)] hover:bg-[var(--card-hover)] transition-colors">
            Today
          </button>
        </div>
        <div className="flex items-center gap-2">
          <a
            href={`https://calendar.google.com/calendar/u/0/r/day/${selectedDateForGoogle}`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-lg border border-[var(--border)] px-4 py-2 text-sm hover:bg-[var(--card-hover)] transition-colors"
          >
            Google Calendar
          </a>
          <button
            type="button"
            onClick={() => openCreate(selectedDate)}
            className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] text-white px-4 py-2 text-sm hover:opacity-90 transition-opacity"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            New Event
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Calendar grid */}
        <div className="lg:col-span-3">
          <div className="border border-[var(--border)] rounded-xl overflow-hidden bg-[var(--surface)]">
            <div className="grid grid-cols-7">
              {WEEKDAYS.map((d) => (
                <div key={d} className="text-center text-xs font-medium text-[var(--muted)] py-2 border-b border-[var(--border)]">
                  {d}
                </div>
              ))}
            </div>
            <div className="grid grid-cols-7">
              {calendarDays.map(({ date: d, inMonth }, i) => {
                const dateStr = fmt(d);
                const dayEvents = eventsByDate[dateStr] ?? [];
                const isToday = dateStr === today;
                return (
                  <div
                    key={i}
                    className={cn(
                      "min-h-[100px] border-b border-r border-[var(--border)] p-1.5 cursor-pointer transition-colors hover:bg-[var(--card-hover)]",
                      !inMonth && "opacity-40",
                    )}
                    onClick={() => setSelectedDate(dateStr)}
                  >
                    <div className={cn(
                      "text-xs font-medium mb-1 w-6 h-6 flex items-center justify-center rounded-full",
                      isToday && "bg-[var(--accent)] text-white",
                    )}>
                      {d.getDate()}
                    </div>
                    <div className="space-y-0.5">
                      {dayEvents.slice(0, 3).map((ev) => (
                        <button
                          key={ev.id}
                          type="button"
                          onClick={(e) => { e.stopPropagation(); openEdit(ev); }}
                          className={cn(
                            "w-full text-left text-[10px] leading-tight px-1.5 py-0.5 rounded border truncate",
                            priorityColor(ev.priority),
                            ev.status === "dismissed" && "line-through opacity-50",
                          )}
                          title={ev.title}
                        >
                          {statusIcon(ev.status)} {ev.title}
                        </button>
                      ))}
                      {dayEvents.length > 3 && (
                        <div className="text-[10px] text-[var(--muted)] pl-1">+{dayEvents.length - 3} more</div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="mt-4 bg-[var(--surface)] border border-[var(--border)] rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold">
                {new Date(`${selectedDate}T00:00:00`).toLocaleDateString("en-US", {
                  weekday: "long",
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                })}{" "}
                ({selectedDayEvents.length})
              </h3>
              <button
                type="button"
                onClick={() => openCreate(selectedDate)}
                className="text-xs px-3 py-1.5 rounded-lg border border-[var(--border)] hover:bg-[var(--card-hover)] transition-colors"
              >
                Add task
              </button>
            </div>
            {selectedDayEvents.length === 0 ? (
              <p className="text-xs text-[var(--muted)]">No tasks for this day.</p>
            ) : (
              <div className="space-y-2">
                {selectedDayEvents.map((ev) => (
                  <div key={ev.id} className="rounded-lg border border-[var(--border)] p-3">
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate">{ev.title}</p>
                        <p className="text-xs text-[var(--muted)]">
                          {ev.assignee || "Unassigned"} · {ev.status}
                        </p>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => openEdit(ev)}
                          className="text-xs px-2 py-1 rounded border border-[var(--border)] hover:bg-[var(--card-hover)]"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={async () => {
                            try {
                              await api.calendar.delete(ev.id);
                              toast.success("Event deleted");
                              void load();
                            } catch (e: unknown) {
                              toast.error(e instanceof Error ? e.message : "Failed to delete");
                            }
                          }}
                          className="text-xs px-2 py-1 rounded border border-red-500/30 text-red-500 hover:bg-red-500/10"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Sidebar: upcoming deadlines */}
        <div className="space-y-4">
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-4">
            <h3 className="text-sm font-semibold mb-3">Upcoming Deadlines</h3>
            {loading ? (
              <p className="text-xs text-[var(--muted)]">Loading...</p>
            ) : upcomingDeadlines.length === 0 ? (
              <p className="text-xs text-[var(--muted)]">No upcoming deadlines</p>
            ) : (
              <div className="space-y-2">
                {upcomingDeadlines.map((ev) => (
                  <button
                    key={ev.id}
                    type="button"
                    onClick={() => openEdit(ev)}
                    className="w-full text-left p-2 rounded-lg hover:bg-[var(--card-hover)] transition-colors group"
                  >
                    <div className="text-sm font-medium truncate group-hover:text-[var(--accent)] transition-colors">
                      {ev.title}
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className={cn("text-[10px] px-1.5 py-0.5 rounded border", priorityColor(ev.priority))}>
                        {ev.priority ?? "medium"}
                      </span>
                      <span className="text-[10px] text-[var(--muted)]">
                        {ev.deadline === today ? "Today" : new Date(ev.deadline + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                      </span>
                      {ev.assignee && (
                        <span className="text-[10px] text-[var(--muted)] truncate">{ev.assignee}</span>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-4">
            <h3 className="text-sm font-semibold mb-2">Summary</h3>
            <div className="grid grid-cols-2 gap-2 text-center">
              <div className="bg-[var(--background)] rounded-lg p-2">
                <div className="text-lg font-bold">{events.length}</div>
                <div className="text-[10px] text-[var(--muted)]">Total Events</div>
              </div>
              <div className="bg-[var(--background)] rounded-lg p-2">
                <div className="text-lg font-bold">{events.filter((e) => e.status === "pending").length}</div>
                <div className="text-[10px] text-[var(--muted)]">Pending</div>
              </div>
              <div className="bg-[var(--background)] rounded-lg p-2">
                <div className="text-lg font-bold">{events.filter((e) => e.priority === "high").length}</div>
                <div className="text-[10px] text-[var(--muted)]">High Priority</div>
              </div>
              <div className="bg-[var(--background)] rounded-lg p-2">
                <div className="text-lg font-bold">{events.filter((e) => e.status === "confirmed").length}</div>
                <div className="text-[10px] text-[var(--muted)]">Confirmed</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Modal */}
      {modalDate !== null && (
        <EventModal
          event={modalEvent}
          date={modalDate}
          onClose={closeModal}
          onSave={afterSave}
        />
      )}
    </div>
  );
}
