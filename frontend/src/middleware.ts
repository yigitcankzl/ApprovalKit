import type { NextRequest } from "next/server";
import { auth0 } from "@/lib/auth0";

export async function middleware(req: NextRequest) {
  return await auth0.middleware(req);
}
