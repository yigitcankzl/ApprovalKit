import { NextRequest, NextResponse } from "next/server";
import { COOKIE_NAME } from "@/lib/auth0";

function decrypt(data: string): string {
  try {
    return atob(data);
  } catch {
    return "";
  }
}

export async function GET(req: NextRequest) {
  const cookie = req.cookies.get(COOKIE_NAME)?.value;
  if (!cookie || cookie === "default") {
    return NextResponse.json({ domain: "", clientId: "", m2mClientId: "", hasConfig: false });
  }

  try {
    const json = decrypt(cookie);
    const config = JSON.parse(json);
    return NextResponse.json({
      domain: config.domain || "",
      clientId: config.clientId || "",
      clientSecret: config.clientSecret || "",
      m2mClientId: config.m2mClientId || "",
      m2mClientSecret: config.m2mClientSecret || "",
      hasConfig: true,
    });
  } catch {
    return NextResponse.json({ domain: "", clientId: "", hasConfig: false });
  }
}
