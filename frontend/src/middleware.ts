import { NextRequest, NextResponse } from "next/server";
import { auth0, getAuth0ClientFromCookieValue, COOKIE_NAME } from "@/lib/auth0";

export async function middleware(req: NextRequest) {
  const tenantCookie = req.cookies.get(COOKIE_NAME)?.value;

  if (tenantCookie && tenantCookie !== "default") {
    try {
      const client = getAuth0ClientFromCookieValue(tenantCookie);
      return await client.middleware(req);
    } catch {
      // Fall through to default
    }
  }

  // No tenant cookie and no env config — can't use Auth0 SDK
  const isAuthRoute = req.nextUrl.pathname.startsWith("/auth/");
  if (isAuthRoute) {
    // No way to handle auth without a configured client
    return NextResponse.redirect(new URL("/login", req.url));
  }

  return NextResponse.next();
}
