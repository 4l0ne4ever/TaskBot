"use client";

// Create/edit modal for a single calendar event. Opens from the calendar grid
// (date click → create) or from an existing event chip (edit).

import { useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import type { CalendarEvent } from "@/lib/types";

interface EventModalProps {
  event: CalendarEvent | null;
  date: string;
  onClose: () => void;
  onSave: () => void;
}

export function EventModal({ event, date, onClose, onSave }: EventModalProps) {
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
