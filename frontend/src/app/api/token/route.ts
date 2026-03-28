import { getAuth0ClientFromRequest, auth0, COOKIE_NAME } from "@/lib/auth0";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";

export async function GET() {
  try {
    // Debug: check which client is used
    const cookieStore = await cookies();
    const tenantCookie = cookieStore.get(COOKIE_NAME)?.value;
    console.log(`[token] ak_tenant cookie: ${tenantCookie ? tenantCookie.substring(0, 20) + '...' : 'MISSING'}`);

    // Try dynamic client first
    const client = await getAuth0ClientFromRequest();
    let session = await client.getSession();

    // If dynamic client has no session, try default client
    if (!session && tenantCookie && auth0) {
      console.log("[token] Dynamic client has no session, trying default auth0 client");
      session = await auth0.getSession();
    }

    if (!session) {
      console.log("[token] No session found with any client");
      return NextResponse.json({ accessToken: null, refreshToken: null }, { status: 401 });
    }

    // Get token from whichever client has the session
    let tokenSet;
    try {
      tokenSet = await client.getAccessToken();
    } catch {
      if (auth0) tokenSet = await auth0.getAccessToken();
      else throw new Error("No Auth0 client available");
    }

    console.log(`[token] Success: token=${tokenSet.token?.substring(0, 20)}...`);
    return NextResponse.json({
      accessToken: tokenSet.token,
      refreshToken: session.tokenSet?.refreshToken || null,
    });
  } catch (e) {
    console.error("[token] Error:", e);
    return NextResponse.json({ accessToken: null, refreshToken: null }, { status: 401 });
  }
}
