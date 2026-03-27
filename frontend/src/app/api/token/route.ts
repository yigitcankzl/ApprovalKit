import { getAuth0ClientFromRequest } from "@/lib/auth0";
import { NextResponse } from "next/server";

export async function GET() {
  try {
    const client = await getAuth0ClientFromRequest();
    const session = await client.getSession();
    if (!session) {
      return NextResponse.json({ accessToken: null, refreshToken: null }, { status: 401 });
    }
    const tokenSet = await client.getAccessToken();
    return NextResponse.json({
      accessToken: tokenSet.token,
      refreshToken: session.tokenSet?.refreshToken || null,
    });
  } catch {
    return NextResponse.json({ accessToken: null, refreshToken: null }, { status: 401 });
  }
}
