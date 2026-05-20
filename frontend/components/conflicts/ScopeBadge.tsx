import type { ConflictScope } from "@/lib/types";

type ScopeMeta = {
  label: string;
  classes: string;
  tooltip: string;
  iconPath: string;
};

const SCOPE_META: Record<ConflictScope, ScopeMeta> = {
  multi_source: {
    label: "Multi-source",
    classes: "bg-red-500/15 text-red-600 dark:text-red-300",
    tooltip: "Same task appears in two different platforms (Gmail and Drive)",
    iconPath:
      "M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244",
  },
  thread_update: {
    label: "Thread update",
    classes: "bg-orange-500/15 text-orange-600 dark:text-orange-300",
    tooltip: "A later message in this thread changed the task",
    iconPath:
      "M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99",
  },
  inter_doc: {
    label: "Inter-doc",
    classes: "bg-yellow-500/15 text-yellow-600 dark:text-yellow-300",
    tooltip: "Same task referenced across different documents",
    iconPath: "M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5",
  },
  intra_batch: {
    label: "Intra-batch",
    classes: "bg-gray-500/15 text-gray-600 dark:text-gray-300",
    tooltip: "Multiple versions extracted from the same source document",
    iconPath:
      "M6.429 9.75L2.25 12l4.179 2.25m0-4.5l5.571 3 5.571-3m-11.142 0L2.25 7.5 12 2.25l9.75 5.25-4.179 2.25m0 0L21.75 12l-4.179 2.25m0 0l4.179 2.25L12 21.75 2.25 16.5l4.179-2.25m11.142 0l-5.571 3-5.571-3",
  },
};

export function ScopeBadge({ scope }: { scope: ConflictScope | null }) {
  if (!scope) return null;
  const meta = SCOPE_META[scope];
  if (!meta) return null;
  return (
    <span
      title={meta.tooltip}
      className={`inline-flex items-center gap-1 rounded-full ${meta.classes} text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5`}
    >
      <svg
        className="w-3 h-3"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
        aria-hidden="true"
      >
        <path strokeLinecap="round" strokeLinejoin="round" d={meta.iconPath} />
      </svg>
      {meta.label}
    </span>
  );
}

export const SCOPE_OPTIONS: ReadonlyArray<{ value: ConflictScope; label: string }> = [
  { value: "multi_source", label: "Multi-source" },
  { value: "thread_update", label: "Thread update" },
  { value: "inter_doc", label: "Inter-doc" },
  { value: "intra_batch", label: "Intra-batch" },
];
