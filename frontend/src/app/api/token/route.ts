import { auth0 } from "@/lib/auth0";
import { NextResponse } from "next/server";

export async function GET() {
  try {
    const session = await auth0.getSession();
    if (!session) {
      return NextResponse.json({ accessToken: null, refreshToken: null }, { status: 401 });
    }
    const tokenSet = await auth0.getAccessToken();
    return NextResponse.json({
      accessToken: tokenSet.token,
      refreshToken: session.tokenSet?.refreshToken || null,
    });
  } catch {
    return NextResponse.json({ accessToken: null, refreshToken: null }, { status: 401 });
  }
}
