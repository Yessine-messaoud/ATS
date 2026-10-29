// Streams the original uploaded document from the backend (which is not reachable from the browser).
const API_URL = process.env.API_URL ?? "http://localhost:8000";

export async function GET(_request: Request, ctx: RouteContext<"/candidates/[id]/file">) {
  const { id } = await ctx.params;
  const upstream = await fetch(`${API_URL}/api/candidates/${encodeURIComponent(id)}/document/file`, { cache: "no-store" });
  if (!upstream.ok || !upstream.body) {
    return new Response("Document not available", { status: upstream.status === 404 ? 404 : 502 });
  }
  return new Response(upstream.body, {
    headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "application/octet-stream",
      "Content-Disposition": "inline",
      "X-Content-Type-Options": "nosniff",
      // Uploaded files are untrusted: never let them run scripts in our origin.
      "Content-Security-Policy": "sandbox",
    },
  });
}
