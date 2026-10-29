"use client";

import Link from "next/link";
import { useRef, useState } from "react";

import { uploadCandidate, type UploadResult } from "@/app/actions";
import { Badge, cx } from "@/components/ui";
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
          "flex w-full flex-col items-center gap-1 rounded-lg border-2 border-dashed px-4 py-8 text-sm",
          dragging ? "border-zinc-500 bg-zinc-100 dark:bg-zinc-800" : "border-zinc-300 dark:border-zinc-700",
        )}
      >
        <span className="font-medium">Drop CVs here or click to choose</span>
        <span className="text-xs text-zinc-500">PDF, DOCX, text or .eml application emails, up to 10 MB each</span>
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
      <ul className="space-y-2 text-sm">
        {items.map((item) => (
          <li key={item.key} className="rounded-md border border-zinc-200 px-3 py-2 dark:border-zinc-800">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate">{item.name}</span>
              <Badge tone={item.status === "done" ? "green" : item.status === "error" ? "red" : "neutral"}>
                {item.status === "uploading" ? "extracting…" : item.status}
              </Badge>
            </div>
            {item.result?.ok === false && <p className="mt-1 text-xs text-red-600">{item.result.error}</p>}
            {item.result?.ok && (
              <div className="mt-1 flex flex-wrap items-center gap-1 text-xs">
                <Link href={`/candidates/${item.result.id}`} className="font-medium underline">
                  Review {item.result.name}
                </Link>
                {item.result.flags.map((flag) => (
                  <Badge key={flag} tone="amber">
                    {FLAG_LABELS[flag] ?? flag}
                  </Badge>
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
