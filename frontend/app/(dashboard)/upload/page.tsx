"use client";

import { useCallback, useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function UploadPage() {
  const [drag, setDrag] = useState(false);
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const pollStatus = useCallback(async (id: string) => {
    const max = 40;
    for (let i = 0; i < max; i++) {
      const r = await api.upload.status(id);
      setStatus(r.status);
      if (r.status === "completed" || r.status === "failed" || r.status === "error") {
        if (r.status === "completed") toast.success("Processing complete");
        else toast.error(`Upload pipeline: ${r.status}`);
        return;
      }
      await new Promise((res) => setTimeout(res, 2000));
    }
    toast.error("Status polling timed out");
  }, []);

  async function handleFile(file: File) {
    if (file.size > 10 * 1024 * 1024) {
      toast.error("Max file size 10 MB");
      return;
    }
    setBusy(true);
    setUploadId(null);
    setStatus(null);
    try {
      const r = await api.upload.file(file);
      setUploadId(r.upload_id);
      setStatus(r.status);
      toast.success("Uploaded — processing");
      void pollStatus(r.upload_id);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-xl space-y-6">
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          const f = e.dataTransfer.files[0];
          if (f) void handleFile(f);
        }}
        className={cn(
          "border-2 border-dashed rounded-2xl p-14 text-center transition-all duration-200",
          drag
            ? "border-[var(--accent)] bg-[var(--accent-muted)] scale-[1.01]"
            : "border-[var(--border)] bg-[var(--surface)]"
        )}
      >
        <svg className="w-10 h-10 mx-auto text-[var(--muted)] mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
        <p className="text-[var(--muted)] text-sm mb-4">
          Drop a PDF or DOCX here, or choose a file
        </p>
        <label className="inline-block">
          <input
            type="file"
            accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            className="hidden"
            disabled={busy}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void handleFile(f);
            }}
          />
          <span className="cursor-pointer rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white px-6 py-2.5 text-sm font-medium inline-block transition-colors">
            {busy ? "Uploading\u2026" : "Browse files"}
          </span>
        </label>
      </div>

      {uploadId && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm flex items-center gap-3">
          <span className="text-[var(--muted)]">ID:</span>
          <code className="text-xs bg-[var(--surface-2)] px-2 py-0.5 rounded">{uploadId}</code>
          {status && (
            <>
              <span className="text-[var(--muted)]">Status:</span>
              <span className={cn(
                "text-xs font-medium",
                status === "completed" && "text-emerald-600 dark:text-emerald-400",
                status === "failed" && "text-red-600 dark:text-red-400",
                !["completed", "failed"].includes(status) && "text-amber-600 dark:text-amber-400"
              )}>
                {status}
              </span>
            </>
          )}
        </div>
      )}
    </div>
  );
}
