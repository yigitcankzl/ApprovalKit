import { NextRequest, NextResponse } from "next/server";
import { encryptTenantConfig, COOKIE_NAME } from "@/lib/auth0";

export async function POST(req: NextRequest) {
  try {
    const { domain, clientId, clientSecret } = await req.json();

    if (!domain || !clientId) {
      return NextResponse.json({ ok: false, error: "domain and clientId required" }, { status: 400 });
    }

    const encrypted = encryptTenantConfig({
      domain: domain || "",
      clientId: clientId || "",
      clientSecret: clientSecret || "",
    });

    const res = NextResponse.json({ ok: true });
    res.cookies.set(COOKIE_NAME, encrypted, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 24 * 30,
    });

    return res;
  } catch {
    return NextResponse.json({ ok: false }, { status: 400 });
  }
}
