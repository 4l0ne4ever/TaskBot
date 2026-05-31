// Helpers shared between the conflicts page and its sub-components.
// Extracted 2026-05-31 (Stage B).

import type { MergeableField, Task } from "@/lib/types";

const RESOLUTION_LABELS: Record<string, string> = {
  accept_a: "Accepted A",
  accept_b: "Accepted B",
  dismiss: "Dismissed",
  dismiss_all: "Dismissed (bulk)",
};

// Parse the `[resolved:<kind>] <desc>` prefix the backend stamps onto a
// resolved conflict's description. Returns the human label + the stripped
// description so the UI can render them separately.
export function parseResolution(description: string | null): {
  label: string | null;
  cleanDesc: string | null;
} {
  if (!description) return { label: null, cleanDesc: null };
  const match = /^\[resolved:([^\]]+)\]\s*/.exec(description);
  if (!match) return { label: null, cleanDesc: description };
  const label = RESOLUTION_LABELS[match[1]] ?? `Resolved (${match[1]})`;
  const cleanDesc = description.slice(match[0].length).trim() || null;
  return { label, cleanDesc };
}

export const MERGEABLE_FIELDS: readonly MergeableField[] = [
  "title",
  "description",
  "assignee",
  "deadline",
  "priority",
];

export function fieldValue(t: Task, f: MergeableField): string | null {
  return (t[f] as string | null) ?? null;
}
