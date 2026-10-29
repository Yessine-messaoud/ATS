"use client";

import { Button, Notice } from "@/components/ui";

export default function ErrorPage({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return (
    <div className="space-y-3">
      <Notice tone="red">
        <strong>Could not load this page.</strong> {error.message}
      </Notice>
      <p className="text-sm text-zinc-500">
        Is the backend running? Start it with <code>docker compose up -d</code> or{" "}
        <code>uv run uvicorn app.main:app</code> in <code>backend/</code>.
      </p>
      <Button variant="secondary" onClick={() => retry()}>
        Retry
      </Button>
    </div>
  );
}
