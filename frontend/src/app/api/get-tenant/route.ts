import { NextRequest, NextResponse } from "next/server";
import { COOKIE_NAME } from "@/lib/auth0";
import * as crypto from "crypto";

const SECRET = process.env.AUTH0_SECRET || "";

function decrypt(data: string): string {
  try {
    const [ivB64, encB64] = data.split(".");
    if (!ivB64 || !encB64) return "";
    const key = crypto.createHash("sha256").update(SECRET).digest();
    const iv = Buffer.from(ivB64, "base64");
    const decipher = crypto.createDecipheriv("aes-256-cbc", key, iv);
    let decrypted = decipher.update(encB64, "base64", "utf8");
    decrypted += decipher.final("utf8");
    return decrypted;
  } catch {
    return "";
  }
}

export async function GET(req: NextRequest) {
  const cookie = req.cookies.get(COOKIE_NAME)?.value;
  if (!cookie || cookie === "default") {
    return NextResponse.json({ domain: "", clientId: "", hasConfig: false });
  }

  try {
    const json = decrypt(cookie);
    const config = JSON.parse(json);
    return NextResponse.json({
      domain: config.domain || "",
      clientId: config.clientId || "",
      hasConfig: true,
    });
  } catch {
    return NextResponse.json({ domain: "", clientId: "", hasConfig: false });
  }
}
