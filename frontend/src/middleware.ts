import { NextRequest } from "next/server";
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

  return await auth0.middleware(req);
}
