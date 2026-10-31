"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { CheckCircle2, FileText, Loader2, UploadCloud, XCircle } from "lucide-react";

import { uploadCandidate, type UploadResult } from "@/app/actions";
import { LongTask } from "@/components/long-task";
import { Badge, cx, focusRing } from "@/components/ui";
import { FLAG_LABELS } from "@/lib/enums";

type Item = { key: string; name: string; status: "queued" | "uploading" | "done" | "error"; result?: UploadResult };

const ACCEPT = ".pdf,.docx,.txt,.eml,application/pdf,message/rfc822";
const MAX_BYTES = 10 * 1024 * 1024;

export function UploadDropzone() {
  const [items, setItems] = useState<Item[]>([]);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const update = (key: string, patch: Partial<Item>) =>
    setItems((current) => current.map((item) => (item.key === key ? { ...item, ...patch } : item)));

  async function upload(files: FileList | File[]) {
    const queued = Array.from(files).map((file) => ({ file, key: `${file.name}-${file.size}-${Math.random()}` }));
    setItems((current) => [...queued.map(({ file, key }) => ({ key, name: file.name, status: "queued" as const })), ...current]);
    // One at a time: each upload runs an LLM extraction.
    for (const { file, key } of queued) {
      if (file.size > MAX_BYTES) {
        update(key, { status: "error", result: { ok: false, error: "larger than 10 MB" } });
        continue;
      }
      update(key, { status: "uploading" });
      const data = new FormData();
      data.append("file", file);
      const result = await uploadCandidate(data);
      update(key, { status: result.ok ? "done" : "error", result });
    }
  }

  const current = items.find((item) => item.status === "uploading");
  const waiting = items.filter((item) => item.status === "queued").length;

  return (
    <div className="space-y-3">
      <button
        type="button"
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          void upload(e.dataTransfer.files);
        }}
        className={cx(
          "flex w-full flex-col items-center gap-2 rounded-xl border-2 border-dashed px-4 py-8 text-sm transition-colors",
          dragging
            ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950/40"
            : "border-zinc-300 hover:border-indigo-400 hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-800/50",
          focusRing,
        )}
      >
        <UploadCloud className={cx("size-8", dragging ? "text-indigo-600" : "text-zinc-400")} aria-hidden />
        <span className="font-medium">Drop CVs here, or click to choose files</span>
        <span className="text-xs text-zinc-500">PDF, DOCX, text or .eml application emails · up to 10 MB each · several at once</span>
      </button>
      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        multiple
        hidden
        onChange={(e) => {
          if (e.target.files) void upload(e.target.files);
          e.target.value = "";
        }}
      />
      {current && (
        <LongTask
          label={`Reading ${current.name}${waiting ? ` (${waiting} more queued)` : ""}`}
          expected="about a minute per CV with the local model"
        />
      )}
      {items.length > 0 && (
        <ul className="divide-y divide-zinc-100 rounded-lg border border-zinc-200 text-sm dark:divide-zinc-800 dark:border-zinc-800">
          {items.map((item) => (
            <li key={item.key} className="flex items-start gap-2.5 px-3 py-2">
              {item.status === "done" ? (
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-hidden />
              ) : item.status === "error" ? (
                <XCircle className="mt-0.5 size-4 shrink-0 text-red-600" aria-hidden />
              ) : item.status === "uploading" ? (
                <Loader2 className="mt-0.5 size-4 shrink-0 animate-spin text-indigo-600" aria-hidden />
              ) : (
                <FileText className="mt-0.5 size-4 shrink-0 text-zinc-400" aria-hidden />
              )}
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate">{item.name}</span>
                  <span className="shrink-0 text-xs text-zinc-500">
                    {item.status === "uploading" ? "extracting…" : item.status === "queued" ? "waiting" : item.status === "done" ? "done" : "failed"}
                  </span>
                </div>
                {item.result?.ok === false && <p className="mt-0.5 text-xs text-red-600">{item.result.error}</p>}
                {item.result?.ok && (
                  <div className="mt-1 flex flex-wrap items-center gap-1 text-xs">
                    <Link href={`/candidates/${item.result.id}`} className="font-medium text-indigo-600 hover:underline dark:text-indigo-400">
                      Review {item.result.name} →
                    </Link>
                    {item.result.flags.map((flag) => (
                      <Badge key={flag} tone="amber">
                        {FLAG_LABELS[flag] ?? flag}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
