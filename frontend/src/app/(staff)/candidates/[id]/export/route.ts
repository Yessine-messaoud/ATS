// Downloads everything held about a candidate (GDPR access / portability) from the backend.
import { authHeaders } from "@/lib/api";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

export async function GET(_request: Request, ctx: RouteContext<"/candidates/[id]/export">) {
  const { id } = await ctx.params;
  const upstream = await fetch(`${API_URL}/api/candidates/${encodeURIComponent(id)}/export`, { cache: "no-store", headers: await authHeaders() });
  if (!upstream.ok || !upstream.body) {
    return new Response("Export not available", { status: upstream.status === 404 ? 404 : 502 });
  }
  return new Response(upstream.body, {
    headers: {
      "Content-Type": "application/json",
      "Content-Disposition": upstream.headers.get("content-disposition") ?? `attachment; filename="candidate-${id}.json"`,
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
