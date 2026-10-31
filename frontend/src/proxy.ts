// Optimistic redirect for visitors without a session cookie. The real check (is the session valid, is the role
// allowed) happens in each area's layout and in the API itself.
import { NextResponse, type NextRequest } from "next/server";

const SESSION_COOKIE = "ra_session";
const PUBLIC = ["/login", "/signup", "/careers", "/privacy"];

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (request.cookies.has(SESSION_COOKIE) || PUBLIC.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    return NextResponse.next();
  }
  // Visitors land on the job board; anything else asks them to sign in first.
  const target = pathname === "/" ? new URL("/careers", request.url) : new URL("/login", request.url);
  if (pathname !== "/") target.searchParams.set("next", `${pathname}${search}`);
  return NextResponse.redirect(target);
}

export const config = {
  // Everything except Next.js internals and static files.
  matcher: ["/((?!_next/|favicon.ico|.*\\.[a-z0-9]+$).*)"],
};
