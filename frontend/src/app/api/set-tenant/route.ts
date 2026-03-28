import { NextResponse } from "next/server";

export async function POST() {
  // Single-tenant mode — no dynamic tenant configuration needed
  return NextResponse.json({ ok: true, message: "Single-tenant mode — tenant configured via env vars" });
}
