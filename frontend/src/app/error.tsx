"use client";

import { RotateCcw, ServerCrash } from "lucide-react";

import { Button, Card, Empty } from "@/components/ui";

export default function ErrorPage({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return (
    <Card>
      <Empty
        icon={<ServerCrash />}
        title="Could not load this page"
        action={
          <Button variant="secondary" onClick={() => retry()} icon={<RotateCcw className="size-4" />}>
            Try again
          </Button>
        }
      >
        <p>{error.message}</p>
        <p className="mt-2 text-xs">
          Is the backend running? Start it with <code>docker compose up -d</code>, or <code>uv run uvicorn app.main:app</code> in{" "}
          <code>backend/</code>.
        </p>
      </Empty>
    </Card>
  );
}
