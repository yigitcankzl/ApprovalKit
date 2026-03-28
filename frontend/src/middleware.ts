import { NextRequest, NextResponse } from "next/server";
import { auth0, getAuth0ClientFromCookieValue, COOKIE_NAME } from "@/lib/auth0";

export async function middleware(req: NextRequest) {
  // 1. Try tenant-specific client from cookie (multi-tenant)
  const tenantCookie = req.cookies.get(COOKIE_NAME)?.value;
  if (tenantCookie && tenantCookie !== "default") {
    try {
      const client = getAuth0ClientFromCookieValue(tenantCookie);
      return await client.middleware(req);
    } catch (e) {
      console.error("[middleware] tenant client error:", e);
    }
  }

  // 2. Try default client from env vars
  if (auth0) {
    return await auth0.middleware(req);
  }

  // 3. No client available — redirect auth routes to login
  if (req.nextUrl.pathname.startsWith("/auth/")) {
    return NextResponse.redirect(new URL("/login", req.url));
  }

  return NextResponse.next();
}
