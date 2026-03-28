import { Auth0Client } from "@auth0/nextjs-auth0/server";
import { cookies } from "next/headers";
import * as crypto from "crypto";

// ── Encryption helpers (AES-256-CBC via Node crypto) ─────────────────────────

const COOKIE_NAME = "ak_tenant";
const SECRET = process.env.AUTH0_SECRET || "";

function encrypt(data: string): string {
  const key = crypto.createHash("sha256").update(SECRET).digest();
  const iv = crypto.randomBytes(16);
  const cipher = crypto.createCipheriv("aes-256-cbc", key, iv);
  let encrypted = cipher.update(data, "utf8", "base64");
  encrypted += cipher.final("base64");
  return iv.toString("base64") + "." + encrypted;
}

function decrypt(data: string): string {
  const [ivB64, encB64] = data.split(".");
  if (!ivB64 || !encB64) return "";
  const key = crypto.createHash("sha256").update(SECRET).digest();
  const iv = Buffer.from(ivB64, "base64");
  const decipher = crypto.createDecipheriv("aes-256-cbc", key, iv);
  let decrypted = decipher.update(encB64, "base64", "utf8");
  decrypted += decipher.final("utf8");
  return decrypted;
}

// ── Tenant Config Type ───────────────────────────────────────────────────────

export interface TenantConfig {
  domain: string;
  clientId: string;
  clientSecret: string;
  m2mClientId?: string;
  m2mClientSecret?: string;
}

// ── Auth0 Client Cache ───────────────────────────────────────────────────────

const clientCache = new Map<string, Auth0Client>();

function buildAuth0Client(config: TenantConfig): Auth0Client {
  return new Auth0Client({
    domain: config.domain,
    clientId: config.clientId,
    clientSecret: config.clientSecret,
    appBaseUrl: process.env.AUTH0_BASE_URL || "http://localhost:3000",
    secret: SECRET,
    authorizationParameters: {
      audience: `https://${config.domain}/me/`,
      scope: "openid profile email offline_access create:me:connected_accounts read:me:connected_accounts delete:me:connected_accounts",
    },
  });
}

// ── Default client (from env — used as fallback when no tenant cookie) ──────

const defaultDomain = process.env.AUTH0_DOMAIN || process.env.NEXT_PUBLIC_AUTH0_DOMAIN || "";
const defaultConfig: TenantConfig = {
  domain: defaultDomain,
  clientId: process.env.AUTH0_CLIENT_ID || "",
  clientSecret: process.env.AUTH0_CLIENT_SECRET || "",
};

// Only build if env vars are actually set — otherwise defer to cookie-based client
export const auth0: Auth0Client = defaultDomain
  ? buildAuth0Client(defaultConfig)
  : (null as unknown as Auth0Client);

// ── Dynamic client from cookie ───────────────────────────────────────────────

export function getAuth0ClientFromCookieValue(cookieValue: string): Auth0Client {
  if (!cookieValue || cookieValue === "default") {
    return auth0 || buildAuth0Client({ domain: "noop", clientId: "noop", clientSecret: "noop" });
  }

  try {
    const json = decrypt(cookieValue);
    const config: TenantConfig = JSON.parse(json);
    console.log(`[auth0] Cookie decoded: domain=${config.domain} clientId=${config.clientId ? 'present' : 'MISSING'}`);

    if (!config.domain || !config.clientId) {
      console.warn("[auth0] Cookie missing domain or clientId, falling back to default");
      return auth0 || buildAuth0Client({ domain: "noop", clientId: "noop", clientSecret: "noop" });
    }

    const cacheKey = config.domain;
    if (clientCache.has(cacheKey)) {
      return clientCache.get(cacheKey)!;
    }

    const client = buildAuth0Client(config);
    clientCache.set(cacheKey, client);

    // Evict old entries
    if (clientCache.size > 50) {
      const first = clientCache.keys().next().value;
      if (first) clientCache.delete(first);
    }

    return client;
  } catch {
    return auth0 || buildAuth0Client({ domain: "noop", clientId: "noop", clientSecret: "noop" });
  }
}

export async function getAuth0ClientFromRequest(): Promise<Auth0Client> {
  try {
    const cookieStore = await cookies();
    const tenantCookie = cookieStore.get(COOKIE_NAME)?.value;
    if (tenantCookie) {
      return getAuth0ClientFromCookieValue(tenantCookie);
    }
  } catch {
    // cookies() not available (e.g., during build)
  }
  return auth0;
}

// ── Cookie helpers (for login page) ──────────────────────────────────────────

export function encryptTenantConfig(config: TenantConfig): string {
  return encrypt(JSON.stringify(config));
}

export { COOKIE_NAME, defaultConfig };
