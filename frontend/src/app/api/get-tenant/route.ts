import { NextResponse } from "next/server";

export async function GET() {
  // Single-tenant mode — always return configured
  return NextResponse.json({
    domain: process.env.AUTH0_DOMAIN || "",
    hasConfig: !!process.env.AUTH0_DOMAIN,
  });
}
