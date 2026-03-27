import { NextRequest, NextResponse } from "next/server";
import { encryptTenantConfig, COOKIE_NAME } from "@/lib/auth0";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { domain, clientId, clientSecret, useDefault } = body;

    const res = NextResponse.json({ ok: true });

    if (useDefault) {
      // Set "default" marker — middleware will use default Auth0Client
      res.cookies.set(COOKIE_NAME, "default", {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        path: "/",
        maxAge: 60 * 60 * 24 * 30, // 30 days
      });
    } else {
      // Encrypt tenant config and store in cookie
      const encrypted = encryptTenantConfig({
        domain: domain || "",
        clientId: clientId || "",
        clientSecret: clientSecret || "",
      });

      res.cookies.set(COOKIE_NAME, encrypted, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        path: "/",
        maxAge: 60 * 60 * 24 * 30,
      });
    }

    return res;
  } catch {
    return NextResponse.json({ ok: false }, { status: 400 });
  }
}
