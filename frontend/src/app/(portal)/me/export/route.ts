// Downloads everything held about the signed-in candidate (GDPR access / portability) from the backend.
import { authHeaders } from "@/lib/api";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

export async function GET() {
  const upstream = await fetch(`${API_URL}/api/portal/export`, { cache: "no-store", headers: await authHeaders() });
  if (!upstream.ok || !upstream.body) {
    return new Response("Export not available", { status: upstream.status === 401 || upstream.status === 403 ? 403 : 502 });
  }
  return new Response(upstream.body, {
    headers: {
      "Content-Type": "application/json",
      "Content-Disposition": upstream.headers.get("content-disposition") ?? 'attachment; filename="my-recruitai-data.json"',
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
