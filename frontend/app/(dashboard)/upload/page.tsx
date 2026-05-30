"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

// ─── Steps ────────────────────────────────────────────────────────────────────
const STEPS = [
  { key: "uploading",  label: "Upload" },
  { key: "queued",     label: "Queue" },
  { key: "processing", label: "Extract" },
  { key: "done",       label: "Done" },
];
const STEP_KEYS = STEPS.map((s) => s.key);

// Round 14 (2026-05-31): the agent writes "done" / "failed" / "extracting";
// the frontend used to listen only for "completed" so polling never
// terminated and the result block never rendered (visible bug on screenshot
// from 2026-05-31). Treat both names as success for forward-compat.
const _DONE_STATUSES = new Set(["done", "completed"]);
const _FAIL_STATUSES = new Set(["failed", "error"]);

function statusToStepKey(uploading: boolean, status: string | null): string {
  if (uploading) return "uploading";
  if (!status) return "";
  if (status === "queued") return "queued";
  if (status === "processing" || status === "extracting") return "processing";
  return "done";
}

// ─── Step tracker ─────────────────────────────────────────────────────────────
function UploadStepTracker({ stepKey, failed }: { stepKey: string; failed: boolean }) {
  const currentIdx = STEP_KEYS.indexOf(stepKey);

  return (
    <div className="flex items-center gap-0 w-full">
      {STEPS.map((s, i) => {
        const isDone = !failed && currentIdx > i;
        const isCurrent = currentIdx === i;
        const isFailed = failed && stepKey === "done" && i === STEP_KEYS.length - 1;
        const isLast = i === STEPS.length - 1;

        return (
          <div key={s.key} className="flex items-center" style={{ flex: isLast ? "0 0 auto" : 1 }}>
            <div className="flex flex-col items-center gap-1">
              <div className={cn(
                "w-5 h-5 rounded-full flex items-center justify-center transition-all duration-300",
                isFailed && "bg-red-500",
                !isFailed && isDone && "bg-emerald-500",
                !isFailed && !isDone && isCurrent && "bg-[var(--accent)] ring-4 ring-[var(--accent)]/20",
                !isFailed && !isDone && !isCurrent && "bg-[var(--border)]",
              )}>
                {!isFailed && isDone ? (
                  <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                ) : isFailed ? (
                  <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                ) : isCurrent ? (
                  <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
                ) : null}
              </div>
              <span className={cn(
                "text-[9px] font-medium whitespace-nowrap",
                isFailed ? "text-red-400" : isDone ? "text-emerald-500" : isCurrent ? "text-[var(--accent)]" : "text-[var(--muted)]"
              )}>
                {s.label}
              </span>
            </div>
            {!isLast && (
              <div className={cn(
                "h-px flex-1 mb-4 transition-colors duration-300",
                isDone ? "bg-emerald-500/60" : "bg-[var(--border)]"
              )} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Result banner ─────────────────────────────────────────────────────────────
function ResultBanner({
  status,
  filename,
  extractedCount,
  extractedTasks,
}: {
  status: string;
  filename: string;
  extractedCount?: number;
  extractedTasks?: { id: string; title: string }[];
}) {
  if (_DONE_STATUSES.has(status)) {
    // Round 14: surface the actual outcome — how many tasks landed, with a
    // short preview list — so the user doesn't have to guess. Three cases:
    //   - extractedCount undefined  → backend didn't report (older agent)
    //   - extractedCount === 0      → pipeline ran clean, file simply had no
    //                                  deliverables (e.g. an FYI doc or an
    //                                  interview transcript). Don't shout
    //                                  "success" loudly — explain.
    //   - extractedCount > 0        → list the titles + link to Tasks.
    const count = extractedCount;
    const haveCount = typeof count === "number";
    const headline =
      !haveCount ? "Extraction complete"
      : count === 0 ? "No tasks found in this file"
      : count === 1 ? "1 task extracted"
      : `${count} tasks extracted`;
    const tone = haveCount && count === 0
      ? "bg-amber-500/10 border-amber-500/20 text-amber-300"
      : "bg-emerald-500/10 border-emerald-500/20 text-emerald-300";
    return (
      <div className={cn("rounded-lg border px-4 py-3 space-y-2", tone)}>
        <div className="flex items-start gap-2">
          <svg className="w-4 h-4 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div className="min-w-0">
            <p className="text-sm font-medium">{headline}</p>
            <p className="text-xs opacity-70 mt-0.5">
              From <span className="font-medium">{filename}</span>
              {haveCount && count === 0 && " — the pipeline ran cleanly but found no actionable deliverables in the text."}
            </p>
          </div>
        </div>
        {extractedTasks && extractedTasks.length > 0 && (
          <ul className="ml-6 text-xs opacity-90 space-y-0.5">
            {extractedTasks.map((t) => (
              <li key={t.id} className="truncate">
                •{" "}
                <Link href={`/tasks/${t.id}`} className="hover:underline">
                  {t.title}
                </Link>
              </li>
            ))}
          </ul>
        )}
        {haveCount && count > 0 && (
          <div className="ml-6">
            <Link
              href="/tasks?source=upload"
              className="inline-block text-xs underline opacity-80 hover:opacity-100"
            >
              View all in Tasks →
            </Link>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex items-start gap-2 rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3">
      <svg className="w-4 h-4 text-red-400 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <div>
        <p className="text-sm font-medium text-red-400">Pipeline failed</p>
        <p className="text-xs text-red-400/70 mt-0.5">
          Could not extract tasks from <span className="font-medium">{filename}</span>. Try again or check the file format.
        </p>
      </div>
    </div>
  );
}

// ─── Drop zone ─────────────────────────────────────────────────────────────────
function DropZone({ onFile, compact = false }: { onFile: (f: File) => void; compact?: boolean }) {
  const [drag, setDrag] = useState(false);

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        const f = e.dataTransfer.files[0];
        if (f) onFile(f);
      }}
      className={cn(
        "border-2 border-dashed text-center transition-all duration-200",
        compact ? "rounded-xl p-6" : "rounded-2xl p-14",
        drag
          ? "border-[var(--accent)] bg-[var(--accent-muted)]"
          : "border-[var(--border)] bg-[var(--surface)] hover:border-[var(--accent)]/40"
      )}
    >
      {!compact && (
        <svg className="w-10 h-10 mx-auto text-[var(--muted)] mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
      )}
      <p className="text-sm text-[var(--muted)] mb-3">
        {compact ? "Drop another file or" : "Drop a PDF or DOCX here, or choose a file"}
      </p>
      <label className="inline-block cursor-pointer">
        <input
          type="file"
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          className="hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); }}
        />
        {compact ? (
          <span className="text-sm text-[var(--accent)] hover:underline">browse files</span>
        ) : (
          <span className="cursor-pointer rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white px-6 py-2.5 text-sm font-medium inline-block transition-colors">
            Browse files
          </span>
        )}
      </label>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function UploadPage() {
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [status, setStatus]     = useState<string | null>(null);
  const [filename, setFilename] = useState("");
  const [uploading, setUploading] = useState(false);
  const [polling, setPolling]     = useState(false);
  // Round 14: extracted-task preview returned by the status endpoint when
  // status reaches "done". Drives the result block; null pre-completion.
  const [extractedCount, setExtractedCount] = useState<number | undefined>(undefined);
  const [extractedTasks, setExtractedTasks] = useState<{ id: string; title: string }[] | undefined>(undefined);

  const isDone   = status !== null && (_DONE_STATUSES.has(status) || _FAIL_STATUSES.has(status));
  const isFailed = status !== null && _FAIL_STATUSES.has(status);
  const stepKey  = statusToStepKey(uploading, status);
  const inProgress = uploading || polling;

  const pollStatus = useCallback(async (id: string) => {
    setPolling(true);
    try {
      for (let i = 0; i < 60; i++) {
        const r = await api.upload.status(id);
        setStatus(r.status);
        if (_DONE_STATUSES.has(r.status)) {
          setExtractedCount(r.extracted_count);
          setExtractedTasks(r.extracted_tasks);
          const n = r.extracted_count ?? 0;
          toast.success(n === 0 ? "Pipeline done — no tasks found" : `${n} task${n === 1 ? "" : "s"} extracted`);
          return;
        }
        if (_FAIL_STATUSES.has(r.status)) { toast.error("Pipeline failed — check file format"); return; }
        await new Promise((res) => setTimeout(res, 2000));
      }
      toast.error("Timed out waiting for pipeline");
    } finally {
      setPolling(false);
    }
  }, []);

  async function handleFile(file: File) {
    if (file.size > 10 * 1024 * 1024) { toast.error("Max file size 10 MB"); return; }
    setUploadId(null);
    setStatus(null);
    setExtractedCount(undefined);
    setExtractedTasks(undefined);
    setFilename(file.name);
    setUploading(true);
    let id = "";
    try {
      const r = await api.upload.file(file);
      id = r.upload_id;
      setUploadId(r.upload_id);
      setStatus(r.status);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Upload failed");
      setFilename("");
      return;
    } finally {
      setUploading(false);
    }
    void pollStatus(id);
  }

  function reset() {
    setUploadId(null);
    setStatus(null);
    setExtractedCount(undefined);
    setExtractedTasks(undefined);
    setFilename("");
  }

  return (
    <div className="max-w-xl space-y-5">
      {/* Drop zone — hide while processing */}
      {!inProgress && !isDone && <DropZone onFile={(f) => void handleFile(f)} />}

      {/* Progress / result card */}
      {(inProgress || isDone) && (
        <div className={cn(
          "rounded-xl border bg-[var(--surface)] p-5 space-y-4 transition-colors",
          isDone && isFailed ? "border-red-500/20" : isDone ? "border-emerald-500/20" : "border-[var(--accent)]/30"
        )}>
          {/* File info row */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[var(--accent)]/10 flex items-center justify-center shrink-0">
              <svg className="w-4 h-4 text-[var(--accent)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{filename}</p>
              {uploadId && <p className="text-[10px] text-[var(--muted)] font-mono truncate mt-0.5">{uploadId}</p>}
            </div>
            {isDone && (
              <button type="button" onClick={reset} className="text-xs text-[var(--muted)] hover:text-[var(--foreground)] transition-colors shrink-0">
                Upload another
              </button>
            )}
          </div>

          {/* Step tracker */}
          {stepKey && <UploadStepTracker stepKey={stepKey} failed={isFailed} />}

          {/* Status description while running */}
          {!isDone && (
            <p className="text-xs text-[var(--muted)]">
              {uploading && "Sending file to server…"}
              {polling && status === "queued" && "Waiting in queue — pipeline will pick this up shortly…"}
              {polling && status === "processing" && "Extracting tasks from document…"}
            </p>
          )}

          {/* Result banner */}
          {isDone && (
            <ResultBanner
              status={status!}
              filename={filename}
              extractedCount={extractedCount}
              extractedTasks={extractedTasks}
            />
          )}
        </div>
      )}

      {/* Compact drop zone after done */}
      {isDone && <DropZone onFile={(f) => void handleFile(f)} compact />}
    </div>
  );
}
